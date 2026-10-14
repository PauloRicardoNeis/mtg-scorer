"""Bulk uses retained real card fixtures; these tests never call Scryfall."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from mtg_scorer.ingest.scryfall import _snapshot_from_manifest
from mtg_scorer.publish.artifact import export_catalog, verify_artifact
from mtg_scorer.publish.bulk import PARSER_VERSION, bulk_identity, export_bulk_catalog
from mtg_scorer.publish.stream import rows, verify_publication

SEED = Path(__file__).resolve().parents[1] / "seeds/scryfall-layouts-v1"


def bulk_fixture(directory, *, extra=None):
    directory.mkdir(parents=True)
    records = [json.loads(path.read_bytes()) for path in sorted(SEED.glob("[0-9][0-9].json"))]
    records.extend(extra or [])
    raw = directory / "default-cards.bulk"
    raw.write_text(json.dumps(records), encoding="utf-8")
    manifest = {
        "snapshot_id": "retained-bulk-fixture",
        "source": "scryfall",
        "source_type": "default_cards",
        "source_updated_at": "2026-09-08T00:00:00Z",
        "retrieved_at": "2026-09-08T00:46:15Z",
        "raw_file": raw.name,
        "content_sha256": sha256(raw.read_bytes()).hexdigest(),
    }
    file = directory / "manifest.json"
    file.write_text(json.dumps(manifest), encoding="utf-8")
    return _snapshot_from_manifest(manifest, raw, file)


def test_bulk_preserves_seed_projection_reuse_versions_and_corruption(tmp_path, monkeypatch):
    import mtg_scorer.publish.bulk as bulk

    source = bulk_fixture(tmp_path / "raw", extra=[{"id": "excluded", "name": "No oracle"}])
    output = export_bulk_catalog(source.raw_file.parent, tmp_path / "out")
    header, manifest = verify_publication(output, source.raw_file.parent)
    assert header["selection"]["kind"] == "bulk"
    assert manifest["excluded_record_counts"] == {"missing_oracle_id": 1}
    assert manifest["row_counts"] == {"cards": 7, "faces": 10, "printings": 8, "aliases": 17}
    seed, _ = verify_artifact(export_catalog(SEED, tmp_path / "seed"), SEED)
    for table in ("cards", "faces", "aliases"):
        assert list(rows(output / "catalog.json", table)) == seed[table]
    assert export_bulk_catalog(source.raw_file.parent, tmp_path / "out") == output
    monkeypatch.setattr(bulk, "PARSER_VERSION", "fixture-next-version")
    rebuilt = export_bulk_catalog(source.raw_file.parent, tmp_path / "out")
    assert rebuilt != output
    source.raw_file.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        verify_publication(output, source.raw_file.parent)


def test_failed_export_can_retry_without_success_directory(tmp_path, monkeypatch):
    import mtg_scorer.publish.bulk as bulk

    source = bulk_fixture(tmp_path / "raw")
    original = bulk.project_catalog
    with monkeypatch.context() as patch:

        def fail(_):
            raise ValueError("fixture failure")

        patch.setattr(bulk, "project_catalog", fail)
        with pytest.raises(ValueError, match="fixture failure"):
            export_bulk_catalog(source.raw_file.parent, tmp_path / "out")
    assert list((tmp_path / "out").iterdir()) == []
    assert bulk.project_catalog is original
    assert export_bulk_catalog(source.raw_file.parent, tmp_path / "out").exists()


def test_bulk_identity_ignores_retrieval_but_tracks_content_and_versions(tmp_path):
    source = bulk_fixture(tmp_path / "raw")
    manifest = json.loads(source.manifest_file.read_bytes())
    identity = bulk_identity(manifest, PARSER_VERSION)
    manifest["retrieved_at"] = "2026-09-09T00:00:00Z"
    manifest["download_uri"] = "https://example.invalid/new-transport-url"
    assert bulk_identity(manifest, PARSER_VERSION) == identity
    assert bulk_identity(manifest, "parser-v2") != identity
    manifest["content_sha256"] = "0" * 64
    assert bulk_identity(manifest, PARSER_VERSION) != identity


def test_bulk_preserves_legacy_games(tmp_path):
    from uuid import uuid4

    source_card = json.loads((SEED / "00.json").read_bytes())
    source_card.update(id=str(uuid4()), games=["astral", "sega"])
    source = bulk_fixture(tmp_path / "raw", extra=[source_card])
    output = export_bulk_catalog(source.raw_file.parent, tmp_path / "out")
    assert any(
        row["games"] == ["astral", "sega"] for row in rows(output / "catalog.json", "printings")
    )
