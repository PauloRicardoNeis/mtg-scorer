"""Tampered artifacts are rejected by the in-memory and streaming verifiers alike."""

import json
import shutil
from hashlib import sha256
from pathlib import Path

import pytest
from test_bulk_catalog import bulk_fixture

from mtg_scorer.publish import postgres
from mtg_scorer.publish.artifact import canonical_bytes, export_catalog, verify_artifact
from mtg_scorer.publish.bulk import export_bulk_catalog
from mtg_scorer.publish.stream import verify_publication

SEED = Path(__file__).resolve().parents[1] / "seeds/scryfall-layouts-v1"


@pytest.fixture(scope="module")
def pristine(tmp_path_factory):
    return export_catalog(SEED, tmp_path_factory.mktemp("pristine"))


@pytest.fixture
def artifact(pristine, tmp_path):
    """A private copy of the verified seed export that one test may damage."""
    return Path(shutil.copytree(pristine, tmp_path / pristine.name))


def read(directory, name):
    return json.loads((directory / name).read_bytes())


def write(directory, name, value):
    (directory / name).write_bytes(canonical_bytes(value))


def reseal(directory, raw):
    """Replace the export and its manifest digest, so only deeper checks can object."""
    (directory / "catalog.json").write_bytes(raw)
    manifest = read(directory, "manifest.json")
    manifest.update(export_sha256=sha256(raw).hexdigest(), export_bytes=len(raw))
    write(directory, "manifest.json", manifest)


def edit_export(change):
    def tamper(directory):
        payload = read(directory, "catalog.json")
        change(payload)
        reseal(directory, canonical_bytes(payload))

    return tamper


def edit_file(name, change):
    def tamper(directory):
        value = read(directory, name)
        change(value)
        write(directory, name, value)

    return tamper


def prepend_field(field):
    def tamper(directory):
        raw = (directory / "catalog.json").read_bytes()
        reseal(directory, b"{" + field + b"," + raw[1:])

    return tamper


def flip_export_byte(directory):
    raw = (directory / "catalog.json").read_bytes()
    (directory / "catalog.json").write_bytes(raw.replace(b'"scryfall"', b'"scryfalL"', 1))


def rename_one_set(payload):
    same_set = [row for row in payload["printings"] if row["set_code"] == "inr"]
    same_set[1]["set_name"] = "Innistrad Remastered (renamed)"


@pytest.mark.parametrize(
    ("tamper", "artifact_error", "stream_error"),
    [
        pytest.param(
            flip_export_byte,
            "export checksum mismatch",
            "export integrity mismatch",
            id="export-bytes",
        ),
        pytest.param(
            lambda directory: (directory / "source-manifest.json").write_bytes(b"{}"),
            "retained source manifest checksum mismatch",
            "source manifest checksum mismatch",
            id="retained-source-manifest",
        ),
        pytest.param(
            edit_export(lambda payload: payload.update(parser_version="scryfall-catalog-v2")),
            "invalid production snapshot identity",
            "publication identity mismatch",
            id="relabelled-parser",
        ),
        pytest.param(
            edit_file(
                "manifest.json",
                lambda manifest: manifest.update(catalog_snapshot_id="catalog-" + "0" * 64),
            ),
            "snapshot mismatch",
            "publication identity mismatch",
            id="manifest-snapshot",
        ),
        pytest.param(
            edit_file("manifest.json", lambda manifest: manifest["row_counts"].update(faces=11)),
            "faces count mismatch",
            "row count mismatch",
            id="manifest-row-count",
        ),
        pytest.param(
            edit_export(
                lambda payload: payload["printings"][0].update(
                    retrieved_at="2026-09-09T00:00:00+00:00"
                )
            ),
            "printing provenance mismatch",
            "printing provenance mismatch",
            id="printing-retrieval-time",
        ),
        pytest.param(
            edit_export(rename_one_set),
            "conflicting set names",
            "conflicting set names",
            id="set-name",
        ),
        pytest.param(
            edit_file("analytical-manifest.json", lambda files: files.pop("faces.parquet")),
            "missing analytical artifact",
            "missing analytical artifact",
            id="analytical-file-dropped",
        ),
        pytest.param(
            edit_file(
                "analytical-manifest.json",
                lambda files: files.update({"notes.parquet": "0" * 64}),
            ),
            "invalid analytical artifact filename",
            "missing analytical artifact",
            id="analytical-file-added",
        ),
        pytest.param(
            lambda directory: (directory / "faces.parquet").write_bytes(b"damaged"),
            "analytical artifact checksum mismatch",
            "analytical artifact checksum mismatch",
            id="parquet-bytes",
        ),
    ],
)
def test_in_memory_and_streaming_verifiers_reject_the_same_tampering(
    artifact, tamper, artifact_error, stream_error
):
    tamper(artifact)

    with pytest.raises(ValueError, match=artifact_error):
        verify_artifact(artifact, SEED)
    with pytest.raises(ValueError, match=stream_error):
        verify_publication(artifact, SEED)


def test_artifact_only_verifies_against_the_source_manifest_it_retained(artifact, tmp_path):
    source = Path(shutil.copytree(SEED, tmp_path / "source"))
    # Same records and checksums, different manifest bytes: a different source identity.
    manifest = json.loads((source / "manifest.json").read_bytes())
    (source / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    with pytest.raises(ValueError, match="source manifest checksum mismatch"):
        verify_artifact(artifact, source)
    with pytest.raises(ValueError, match="source manifest checksum mismatch"):
        verify_publication(artifact, source)


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        pytest.param(
            prepend_field(b'"extra":1'), "duplicate or unknown export field", id="unknown-field"
        ),
        pytest.param(
            prepend_field(b'"parser_version":"shadowed"'),
            "duplicate or unknown export field",
            id="duplicate-field",
        ),
        pytest.param(
            edit_export(lambda payload: payload.update(faces={})),
            "catalog table must be an array",
            id="table-object",
        ),
        pytest.param(
            edit_export(lambda payload: payload.pop("created_at")),
            "missing export field",
            id="missing-field",
        ),
        pytest.param(
            edit_export(
                lambda payload: payload["printings"][0].update(
                    raw_snapshot_ref="sha256:" + "0" * 64
                )
            ),
            "printing provenance mismatch",
            id="raw-snapshot-ref",
        ),
    ],
)
def test_streaming_verifier_rejects_framing_and_provenance_drift(artifact, tamper, message):
    tamper(artifact)

    with pytest.raises(ValueError, match=message):
        verify_publication(artifact, SEED)


def test_streaming_verifier_reports_missing_selection_as_a_missing_field(artifact):
    edit_export(lambda payload: payload.pop("selection"))(artifact)

    with pytest.raises(ValueError, match="missing export field"):
        verify_publication(artifact, SEED)


def test_bulk_publication_must_keep_the_fixed_bulk_selection(tmp_path):
    source = bulk_fixture(tmp_path / "raw")
    output = export_bulk_catalog(source.raw_file.parent, tmp_path / "out")
    edit_export(
        lambda payload: payload.update(selection={"kind": "bulk", "description": "Other subset"})
    )(output)

    with pytest.raises(ValueError, match="invalid bulk selection"):
        verify_publication(output, source.raw_file.parent)


def test_publication_rejects_tampered_bytes_before_connecting(artifact, monkeypatch):
    flip_export_byte(artifact)
    monkeypatch.setattr(
        postgres.psycopg, "connect", lambda *args, **kwargs: pytest.fail("connected")
    )

    with pytest.raises(ValueError, match="export integrity mismatch"):
        postgres.publish_catalog(
            artifact,
            SEED,
            "dbname=never_used",
            before_load=lambda: pytest.fail("load stage reported for invalid bytes"),
        )
