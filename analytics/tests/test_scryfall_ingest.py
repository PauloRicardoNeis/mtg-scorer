import gzip
import hashlib
import json
from pathlib import Path

import duckdb
import pytest

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
    assert adapter.download_default_cards_snapshot(tmp_path) == first
    first.raw_file.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        adapter.download_default_cards_snapshot(tmp_path)


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
