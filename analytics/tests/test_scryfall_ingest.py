import gzip
import hashlib
import io
import json
import shutil
from dataclasses import replace
from pathlib import Path

import duckdb
import pytest

import mtg_scorer.ingest.scryfall as adapter
from mtg_scorer.ingest.scryfall import (
    ScryfallSnapshot,
    _bulk_download_uri,
    normalize_snapshot,
)

FIXTURE = Path(__file__).parent / "fixtures" / "scryfall" / "default-cards.json"


def test_current_jsonl_download_uri_is_preferred_with_legacy_fallback() -> None:
    assert (
        _bulk_download_uri(
            {
                "jsonl_download_uri": "https://data.scryfall.io/current.jsonl.gz",
                "download_uri": "https://data.scryfall.io/legacy.json",
            }
        )
        == "https://data.scryfall.io/current.jsonl.gz"
    )
    assert (
        _bulk_download_uri({"download_uri": "https://data.scryfall.io/legacy.json"})
        == "https://data.scryfall.io/legacy.json"
    )


def test_snapshot_normalization_preserves_oracle_and_printing_granularity(tmp_path: Path) -> None:
    snapshot = ScryfallSnapshot(
        snapshot_id="scryfall-fixture-001",
        raw_file=FIXTURE,
        manifest_file=tmp_path / "raw-manifest.json",
        retrieved_at="2026-08-28T12:00:00+00:00",
        content_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        source_updated_at="2026-08-28T00:00:00+00:00",
    )

    result = normalize_snapshot(snapshot, output_root=tmp_path / "silver")

    assert result.oracle_card_count == 2
    assert result.printing_count == 3
    assert result.skipped_without_oracle_id == 1
    assert result.oracle_cards_file.exists()
    assert result.printings_file.exists()

    connection = duckdb.connect(":memory:")
    try:
        oracle_rows = connection.execute(
            "SELECT oracle_id, oracle_text FROM read_parquet(?) ORDER BY oracle_id",
            [str(result.oracle_cards_file)],
        ).fetchall()
        printing_rows = connection.execute(
            "SELECT oracle_id, set_code, rarity FROM read_parquet(?) ORDER BY scryfall_id",
            [str(result.printings_file)],
        ).fetchall()
    finally:
        connection.close()

    assert oracle_rows == [
        ("oracle-bolt", "Example Bolt deals 3 damage to any target."),
        ("oracle-engine", "Whenever you draw a card, create a token."),
    ]
    assert len(printing_rows) == 3
    assert ("oracle-bolt", "old", "common") in printing_rows
    assert ("oracle-bolt", "new", "uncommon") in printing_rows


def test_current_gzipped_jsonl_bulk_format_is_streamed(tmp_path: Path) -> None:
    raw_file = tmp_path / "default-cards.jsonl.gz"
    cards = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with gzip.open(raw_file, "wt", encoding="utf-8") as stream:
        for card in cards:
            stream.write(json.dumps(card) + "\n")
    snapshot = ScryfallSnapshot(
        snapshot_id="scryfall-jsonl-fixture-001",
        raw_file=raw_file,
        manifest_file=tmp_path / "raw-manifest.json",
        retrieved_at="2026-08-28T12:00:00+00:00",
        content_sha256=hashlib.sha256(raw_file.read_bytes()).hexdigest(),
        source_updated_at="2026-08-28T00:00:00+00:00",
    )

    result = normalize_snapshot(snapshot, output_root=tmp_path / "silver")

    assert result.oracle_card_count == 2
    assert result.printing_count == 3
    assert result.skipped_without_oracle_id == 1


def test_snapshot_normalization_is_idempotent(tmp_path: Path) -> None:
    snapshot = ScryfallSnapshot(
        snapshot_id="scryfall-fixture-001",
        raw_file=FIXTURE,
        manifest_file=tmp_path / "raw-manifest.json",
        retrieved_at="2026-08-28T12:00:00+00:00",
        content_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        source_updated_at="2026-08-28T00:00:00+00:00",
    )

    first = normalize_snapshot(snapshot, output_root=tmp_path / "silver")
    second = normalize_snapshot(snapshot, output_root=tmp_path / "silver")

    assert second == first


def test_existing_silver_output_must_match_its_manifest(tmp_path: Path) -> None:
    snapshot = ScryfallSnapshot(
        snapshot_id="scryfall-fixture-001",
        raw_file=FIXTURE,
        manifest_file=tmp_path / "raw-manifest.json",
        retrieved_at="2026-08-28T12:00:00+00:00",
        content_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        source_updated_at="2026-08-28T00:00:00+00:00",
    )
    result = normalize_snapshot(snapshot, output_root=tmp_path / "silver")
    result.oracle_cards_file.write_bytes(b"corrupted")

    with pytest.raises(ValueError, match="checksum mismatch"):
        normalize_snapshot(snapshot, output_root=tmp_path / "silver")


def test_interrupted_download_has_no_success_manifest_and_retry_works(tmp_path, monkeypatch):
    import io

    import mtg_scorer.ingest.scryfall as adapter

    monkeypatch.setattr(
        adapter,
        "_fetch_json",
        lambda _: {
            "updated_at": "2026-09-08T00:00:00Z",
            "download_uri": "https://example.invalid/bulk",
        },
    )

    class Interrupted(io.BytesIO):
        def read(self, size=-1):
            raise OSError("interrupted stream")

    monkeypatch.setattr(adapter, "urlopen", lambda *a, **k: Interrupted(b"partial"))
    with pytest.raises(OSError, match="interrupted"):
        adapter.download_default_cards_snapshot(tmp_path)
    assert not list(tmp_path.rglob("manifest.json"))
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(adapter, "urlopen", lambda *a, **k: io.BytesIO(FIXTURE.read_bytes()))
    first = adapter.download_default_cards_snapshot(tmp_path)
    monkeypatch.setattr(
        adapter, "urlopen", lambda *a, **k: pytest.fail("unchanged snapshot downloaded again")
    )
    assert adapter.download_default_cards_snapshot(tmp_path) == first
    monkeypatch.setattr(
        adapter,
        "_fetch_json",
        lambda _: {
            "updated_at": "2026-09-08T00:00:00Z",
            "download_uri": "https://example.invalid/new-url",
        },
    )
    assert adapter.download_default_cards_snapshot(tmp_path) == first
    first.raw_file.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        adapter.download_default_cards_snapshot(tmp_path)


def test_truncated_gzip_is_not_retained_as_a_completed_download(tmp_path, monkeypatch):
    import io

    import mtg_scorer.ingest.scryfall as adapter

    monkeypatch.setattr(
        adapter,
        "_fetch_json",
        lambda _: {
            "updated_at": "2026-09-08T00:00:00Z",
            "download_uri": "https://example.invalid/data",
        },
    )
    compressed = gzip.compress(FIXTURE.read_bytes())
    monkeypatch.setattr(adapter, "urlopen", lambda *a, **k: io.BytesIO(compressed[:-10]))
    with pytest.raises((EOFError, OSError)):
        adapter.download_default_cards_snapshot(tmp_path)
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(adapter, "urlopen", lambda *a, **k: io.BytesIO(compressed))
    assert adapter.download_default_cards_snapshot(tmp_path).raw_file.exists()


def test_failed_legacy_normalization_never_publishes_partial_files(tmp_path, monkeypatch):
    import mtg_scorer.ingest.scryfall as adapter

    snapshot = ScryfallSnapshot(
        "failure-fixture",
        FIXTURE,
        tmp_path / "raw.json",
        "2026-09-08T00:00:00Z",
        hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "2026-09-08T00:00:00Z",
    )
    original = adapter._materialize_tables
    with monkeypatch.context() as patch:

        def fail(_):
            raise ValueError("normalization failure")

        patch.setattr(adapter, "_materialize_tables", fail)
        with pytest.raises(ValueError, match="normalization failure"):
            normalize_snapshot(snapshot, output_root=tmp_path / "output")
    assert not list((tmp_path / "output").rglob("manifest.json"))
    assert not list((tmp_path / "output").rglob("*.parquet"))
    assert adapter._materialize_tables is original
    assert normalize_snapshot(snapshot, output_root=tmp_path / "output").printing_count == 3


METADATA = {"updated_at": "2026-09-08T00:00:00Z", "download_uri": "https://example.invalid/bulk"}


class Response(io.BytesIO):
    """A urlopen response, optionally carrying transport headers."""

    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        super().__init__(body)
        self.headers = headers or {}


def serve(monkeypatch, body: bytes, *, metadata=METADATA, headers=None) -> None:
    monkeypatch.setattr(adapter, "_fetch_json", lambda _: dict(metadata))
    monkeypatch.setattr(adapter, "urlopen", lambda *a, **k: Response(body, headers))


def fixture_snapshot(raw_file: Path = FIXTURE, snapshot_id: str = "scryfall-fixture-001"):
    return ScryfallSnapshot(
        snapshot_id=snapshot_id,
        raw_file=raw_file,
        manifest_file=raw_file.parent / "raw-manifest.json",
        retrieved_at="2026-08-28T12:00:00+00:00",
        content_sha256=hashlib.sha256(raw_file.read_bytes()).hexdigest(),
        source_updated_at="2026-08-28T00:00:00+00:00",
    )


def test_metadata_request_identifies_the_client_and_requires_an_object(monkeypatch) -> None:
    requests = []

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return io.BytesIO(b'{"type": "default_cards"}' if len(requests) == 1 else b"[]")

    monkeypatch.setattr(adapter, "urlopen", urlopen)

    assert adapter._fetch_json(adapter.BULK_METADATA_URL) == {"type": "default_cards"}
    with pytest.raises(ValueError, match="expected an object"):
        adapter._fetch_json(adapter.BULK_METADATA_URL)
    request, timeout = requests[0]
    assert request.full_url == adapter.BULK_METADATA_URL
    assert request.get_header("User-agent") == adapter.USER_AGENT
    assert timeout == 30


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        pytest.param(
            {"download_uri": "https://example.invalid/bulk"},
            "omitted updated_at",
            id="missing-updated",
        ),
        pytest.param({**METADATA, "updated_at": ""}, "omitted updated_at", id="blank-updated"),
        pytest.param(
            {"updated_at": "2026-09-08T00:00:00Z"}, "omitted a download URI", id="missing-uri"
        ),
        pytest.param(
            {**METADATA, "updated_at": "2026-09-08T00:00:00"},
            "must include a timezone",
            id="naive-updated",
        ),
    ],
)
def test_incomplete_metadata_is_rejected_before_downloading(
    tmp_path, monkeypatch, metadata, message
) -> None:
    monkeypatch.setattr(adapter, "_fetch_json", lambda _: metadata)
    monkeypatch.setattr(adapter, "urlopen", lambda *a, **k: pytest.fail("downloaded"))

    with pytest.raises(ValueError, match=message):
        adapter.download_default_cards_snapshot(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_shorter_than_content_length_is_not_retained(tmp_path, monkeypatch) -> None:
    body = FIXTURE.read_bytes()
    serve(monkeypatch, body, headers={"Content-Length": str(len(body) + 1)})

    with pytest.raises(ValueError, match="incomplete bulk download"):
        adapter.download_default_cards_snapshot(tmp_path)
    assert list(tmp_path.iterdir()) == []

    serve(monkeypatch, body, headers={"Content-Length": str(len(body))})
    snapshot = adapter.download_default_cards_snapshot(tmp_path)
    assert snapshot.raw_file.read_bytes() == body


@pytest.mark.parametrize(
    "body",
    [b"", b" \n\t", b"[]", gzip.compress(b"")],
    ids=["zero-bytes", "whitespace", "empty-array", "empty-gzip"],
)
def test_download_without_cards_is_not_retained(tmp_path, monkeypatch, body) -> None:
    serve(monkeypatch, body)

    with pytest.raises(ValueError, match="empty bulk download"):
        adapter.download_default_cards_snapshot(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_retained_snapshot_is_not_reused_for_another_source_type(tmp_path, monkeypatch) -> None:
    serve(monkeypatch, FIXTURE.read_bytes())
    adapter.download_default_cards_snapshot(tmp_path)

    serve(monkeypatch, FIXTURE.read_bytes(), metadata={**METADATA, "type": "all_cards"})
    with pytest.raises(ValueError, match="conflicts with retained snapshot"):
        adapter.download_default_cards_snapshot(tmp_path)


def competing_rename(*, retrieved_at: str, raw: bytes | None = None):
    """Simulate another downloader finalizing the same snapshot directory first."""

    def rename(source, destination) -> None:
        shutil.copytree(source, destination)
        manifest_file = Path(destination) / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["retrieved_at"] = retrieved_at
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        if raw is not None:
            (Path(destination) / "default-cards.bulk").write_bytes(raw)
        raise FileExistsError(destination)

    return rename


def test_concurrent_identical_download_returns_the_snapshot_retained_first(
    tmp_path, monkeypatch
) -> None:
    serve(monkeypatch, FIXTURE.read_bytes())
    monkeypatch.setattr(adapter.os, "rename", competing_rename(retrieved_at="competitor-time"))

    snapshot = adapter.download_default_cards_snapshot(tmp_path)

    assert snapshot.retrieved_at == "competitor-time"
    assert [path.name for path in tmp_path.iterdir()] == ["20260908T000000Z"]


def test_concurrent_download_with_other_bytes_is_a_conflict(tmp_path, monkeypatch) -> None:
    serve(monkeypatch, FIXTURE.read_bytes())
    monkeypatch.setattr(
        adapter.os, "rename", competing_rename(retrieved_at="competitor-time", raw=b"[{}]")
    )

    with pytest.raises(ValueError, match="concurrent source snapshot conflict"):
        adapter.download_default_cards_snapshot(tmp_path)
    assert [path.name for path in tmp_path.iterdir()] == ["20260908T000000Z"]


def test_failed_snapshot_finalize_without_a_competitor_propagates(tmp_path, monkeypatch) -> None:
    serve(monkeypatch, FIXTURE.read_bytes())

    def denied(source, destination) -> None:
        raise PermissionError(destination)

    with monkeypatch.context() as patch:
        patch.setattr(adapter.os, "rename", denied)
        with pytest.raises(PermissionError):
            adapter.download_default_cards_snapshot(tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert adapter.download_default_cards_snapshot(tmp_path).raw_file.exists()


def test_normalization_verifies_the_raw_checksum_first(tmp_path) -> None:
    snapshot = replace(fixture_snapshot(), content_sha256="0" * 64)

    with pytest.raises(ValueError, match="raw snapshot checksum mismatch"):
        normalize_snapshot(snapshot, output_root=tmp_path / "silver")
    assert not (tmp_path / "silver").exists()


def test_snapshot_id_cannot_be_reused_for_other_source_bytes(tmp_path) -> None:
    normalize_snapshot(fixture_snapshot(), output_root=tmp_path / "silver")
    other_raw = tmp_path / "other.json"
    other_raw.write_text(json.dumps(json.loads(FIXTURE.read_text(encoding="utf-8"))[:1]))

    with pytest.raises(ValueError, match="different source snapshot"):
        normalize_snapshot(fixture_snapshot(other_raw), output_root=tmp_path / "silver")


def test_existing_printing_parquet_must_match_its_manifest(tmp_path) -> None:
    result = normalize_snapshot(fixture_snapshot(), output_root=tmp_path / "silver")
    result.printings_file.write_bytes(b"corrupted")

    with pytest.raises(ValueError, match=r"checksum mismatch: .*card_printings\.parquet"):
        normalize_snapshot(fixture_snapshot(), output_root=tmp_path / "silver")


def test_concurrent_identical_normalization_reuses_the_finalized_output(
    tmp_path, monkeypatch
) -> None:
    def finish_first(source, destination) -> None:
        shutil.copytree(source, destination)
        raise FileExistsError(destination)

    with monkeypatch.context() as patch:
        patch.setattr(adapter.os, "rename", finish_first)
        result = normalize_snapshot(fixture_snapshot(), output_root=tmp_path / "silver")

    assert result == normalize_snapshot(fixture_snapshot(), output_root=tmp_path / "silver")
    snapshot_dir = tmp_path / "silver" / "scryfall-fixture-001"
    assert [path.name for path in snapshot_dir.iterdir()] == [adapter.PARSER_VERSION]


def test_failed_normalization_finalize_without_a_competitor_propagates(
    tmp_path, monkeypatch
) -> None:
    def denied(source, destination) -> None:
        raise PermissionError(destination)

    with monkeypatch.context() as patch:
        patch.setattr(adapter.os, "rename", denied)
        with pytest.raises(PermissionError):
            normalize_snapshot(fixture_snapshot(), output_root=tmp_path / "silver")
    assert list((tmp_path / "silver" / "scryfall-fixture-001").iterdir()) == []


@pytest.mark.parametrize(("card_count", "batches"), [(5_000, [5_000]), (5_001, [5_000, 1])])
def test_normalization_flushes_bounded_batches_without_dropping_a_remainder(
    tmp_path, monkeypatch, card_count, batches
) -> None:
    raw = tmp_path / "cards.jsonl"
    with raw.open("w", encoding="utf-8") as stream:
        for index in range(card_count):
            stream.write(json.dumps({"id": f"printing-{index}", "oracle_id": "oracle"}) + "\n")
    sizes = []
    # DuckDB executemany is slow (~14 ms/row), so record batch sizes instead of inserting.
    monkeypatch.setattr(adapter, "_insert_batch", lambda _, batch: sizes.append(len(batch)))

    normalize_snapshot(fixture_snapshot(raw), output_root=tmp_path / "silver")

    assert sizes == batches


@pytest.mark.parametrize("encoding", ["array", "jsonl", "jsonl-gzip"])
def test_bulk_reader_skips_blank_lines_and_non_object_entries(tmp_path, encoding) -> None:
    cards = [{"id": "a", "oracle_id": "o"}, {"id": "b", "oracle_id": "o"}]
    entries = [1, cards[0], "token", cards[1], None]
    if encoding == "array":
        content = b" \n" + json.dumps(entries).encode()
    else:
        lines = "\n\n".join(json.dumps(entry) for entry in entries)
        content = ("\n" + lines + "\n").encode()
        if encoding == "jsonl-gzip":
            content = gzip.compress(content)
    path = tmp_path / "bulk"
    path.write_bytes(content)

    assert list(adapter._iter_cards(path)) == cards
