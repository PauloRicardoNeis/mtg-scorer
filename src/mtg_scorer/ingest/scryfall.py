"""Immutable Scryfall bulk snapshots and Parquet canonicalization."""

from __future__ import annotations

import gzip
import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, BinaryIO, TextIO
from urllib.request import Request, urlopen

import duckdb
import ijson

BULK_METADATA_URL = "https://api.scryfall.com/bulk-data/default-cards"
PARSER_VERSION = "scryfall-default-cards-v1"
USER_AGENT = "mtg-scorer/0.2 (+https://github.com/PauloRicardoNeis/mtg-scorer)"


@dataclass(frozen=True, slots=True)
class ScryfallSnapshot:
    snapshot_id: str
    raw_file: Path
    manifest_file: Path
    retrieved_at: str
    content_sha256: str
    source_updated_at: str


@dataclass(frozen=True, slots=True)
class ScryfallIngestResult:
    snapshot: ScryfallSnapshot
    oracle_cards_file: Path
    printings_file: Path
    silver_manifest_file: Path
    oracle_card_count: int
    printing_count: int
    skipped_without_oracle_id: int


def ingest_scryfall(data_dir: Path) -> ScryfallIngestResult:
    """Download the current bulk file, preserve it, and emit analytical Parquet."""

    snapshot = download_default_cards_snapshot(data_dir / "raw" / "scryfall")
    return normalize_snapshot(
        snapshot,
        output_root=data_dir / "silver" / "scryfall",
    )


def download_default_cards_snapshot(raw_root: Path) -> ScryfallSnapshot:
    """Download one immutable Scryfall default-cards snapshot with a checksum."""

    metadata = _fetch_json(BULK_METADATA_URL)
    updated_at = _required_string(metadata, "updated_at")
    download_uri = _bulk_download_uri(metadata)
    timestamp = _parse_timestamp(updated_at).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = raw_root / timestamp
    raw_file = snapshot_dir / "default-cards.bulk"
    manifest_file = snapshot_dir / "manifest.json"

    if manifest_file.exists() and raw_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        actual_digest = _file_sha256(raw_file)
        if actual_digest != manifest.get("content_sha256"):
            raise ValueError(f"existing snapshot checksum mismatch: {raw_file}")
        return _snapshot_from_manifest(manifest, raw_file, manifest_file)

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    temporary_file = snapshot_dir / "default-cards.bulk.part"
    request = Request(
        download_uri,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=120) as response, temporary_file.open("wb") as destination:
        shutil.copyfileobj(response, destination)
    os.replace(temporary_file, raw_file)

    retrieved_at = datetime.now(UTC).isoformat()
    content_digest = _file_sha256(raw_file)
    snapshot_id = f"scryfall-default-cards-{timestamp}-{content_digest[:12]}"
    manifest = {
        "snapshot_id": snapshot_id,
        "source": "scryfall",
        "source_type": metadata.get("type", "default_cards"),
        "source_updated_at": updated_at,
        "retrieved_at": retrieved_at,
        "metadata_url": BULK_METADATA_URL,
        "download_uri": download_uri,
        "content_type": metadata.get("content_type"),
        "content_encoding": metadata.get("content_encoding"),
        "content_sha256": content_digest,
        "raw_file": raw_file.name,
        "parser_version": PARSER_VERSION,
    }
    _write_json_atomic(manifest_file, manifest)
    return _snapshot_from_manifest(manifest, raw_file, manifest_file)


def normalize_snapshot(
    snapshot: ScryfallSnapshot,
    *,
    output_root: Path,
) -> ScryfallIngestResult:
    """Project a Scryfall snapshot into Oracle-card and printing Parquet tables."""

    output_dir = output_root / snapshot.snapshot_id / PARSER_VERSION
    oracle_cards_file = output_dir / "oracle_cards.parquet"
    printings_file = output_dir / "card_printings.parquet"
    silver_manifest_file = output_dir / "manifest.json"

    if silver_manifest_file.exists() and oracle_cards_file.exists() and printings_file.exists():
        manifest = json.loads(silver_manifest_file.read_text(encoding="utf-8"))
        if manifest.get("source_content_sha256") != snapshot.content_sha256:
            raise ValueError("silver manifest refers to a different source snapshot")
        if _file_sha256(oracle_cards_file) != manifest.get("oracle_cards_sha256"):
            raise ValueError(f"existing Parquet checksum mismatch: {oracle_cards_file}")
        if _file_sha256(printings_file) != manifest.get("card_printings_sha256"):
            raise ValueError(f"existing Parquet checksum mismatch: {printings_file}")
        return ScryfallIngestResult(
            snapshot=snapshot,
            oracle_cards_file=oracle_cards_file,
            printings_file=printings_file,
            silver_manifest_file=silver_manifest_file,
            oracle_card_count=manifest["oracle_card_count"],
            printing_count=manifest["printing_count"],
            skipped_without_oracle_id=manifest["skipped_without_oracle_id"],
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(":memory:")
    skipped_without_oracle_id = 0
    try:
        _create_staging_table(connection)
        batch: list[tuple[Any, ...]] = []
        for card in _iter_cards(snapshot.raw_file):
            projected = _project_card(card)
            if projected is None:
                skipped_without_oracle_id += 1
                continue
            batch.append(projected)
            if len(batch) >= 5_000:
                _insert_batch(connection, batch)
                batch.clear()
        if batch:
            _insert_batch(connection, batch)

        _materialize_tables(connection)
        oracle_card_count = connection.execute("SELECT count(*) FROM oracle_cards").fetchone()[0]
        printing_count = connection.execute("SELECT count(*) FROM card_printings").fetchone()[0]
        connection.execute(
            "COPY oracle_cards TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(oracle_cards_file)],
        )
        connection.execute(
            "COPY card_printings TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(printings_file)],
        )
    finally:
        connection.close()

    manifest = {
        "dataset_snapshot_id": snapshot.snapshot_id,
        "source_manifest": str(snapshot.manifest_file),
        "source_content_sha256": snapshot.content_sha256,
        "parser_version": PARSER_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "oracle_cards_file": oracle_cards_file.name,
        "card_printings_file": printings_file.name,
        "oracle_cards_sha256": _file_sha256(oracle_cards_file),
        "card_printings_sha256": _file_sha256(printings_file),
        "oracle_card_count": oracle_card_count,
        "printing_count": printing_count,
        "skipped_without_oracle_id": skipped_without_oracle_id,
    }
    _write_json_atomic(silver_manifest_file, manifest)
    return ScryfallIngestResult(
        snapshot=snapshot,
        oracle_cards_file=oracle_cards_file,
        printings_file=printings_file,
        silver_manifest_file=silver_manifest_file,
        oracle_card_count=oracle_card_count,
        printing_count=printing_count,
        skipped_without_oracle_id=skipped_without_oracle_id,
    )


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"expected an object from {url}")
    return payload


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Scryfall bulk metadata omitted {key}")
    return value


def _bulk_download_uri(payload: dict[str, Any]) -> str:
    """Prefer Scryfall's current JSONL export while accepting legacy metadata."""

    for key in ("jsonl_download_uri", "download_uri"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    raise ValueError("Scryfall bulk metadata omitted a download URI")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Scryfall updated_at must include a timezone")
    return parsed.astimezone(UTC)


def _snapshot_from_manifest(
    manifest: dict[str, Any],
    raw_file: Path,
    manifest_file: Path,
) -> ScryfallSnapshot:
    return ScryfallSnapshot(
        snapshot_id=manifest["snapshot_id"],
        raw_file=raw_file,
        manifest_file=manifest_file,
        retrieved_at=manifest["retrieved_at"],
        content_sha256=manifest["content_sha256"],
        source_updated_at=manifest["source_updated_at"],
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".part")
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


@contextmanager
def _open_binary(path: Path) -> Iterator[BinaryIO]:
    with path.open("rb") as probe:
        compressed = probe.read(2) == b"\x1f\x8b"
    if compressed:
        with gzip.open(path, "rb") as stream:
            yield stream
    else:
        with path.open("rb") as stream:
            yield stream


@contextmanager
def _open_text(path: Path) -> Iterator[TextIO]:
    with path.open("rb") as probe:
        compressed = probe.read(2) == b"\x1f\x8b"
    if compressed:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            yield stream
    else:
        with path.open("rt", encoding="utf-8") as stream:
            yield stream


def _iter_cards(path: Path) -> Iterator[dict[str, Any]]:
    with _open_text(path) as probe:
        first_character = ""
        while not first_character:
            first_character = probe.read(1)
            if first_character == "":
                return
            first_character = first_character.strip()

    if first_character == "[":
        with _open_binary(path) as stream:
            for card in ijson.items(stream, "item"):
                if isinstance(card, dict):
                    yield card
        return

    with _open_text(path) as stream:
        for line in stream:
            if line.strip():
                card = json.loads(line)
                if isinstance(card, dict):
                    yield card


def _project_card(card: dict[str, Any]) -> tuple[Any, ...] | None:
    oracle_id = card.get("oracle_id")
    if not isinstance(oracle_id, str) or not oracle_id:
        return None
    return (
        card.get("id"),
        oracle_id,
        card.get("name"),
        card.get("released_at"),
        card.get("set"),
        card.get("collector_number"),
        card.get("rarity"),
        card.get("mana_cost"),
        float(card.get("cmc", 0.0)),
        card.get("type_line"),
        card.get("oracle_text"),
        json.dumps(card.get("colors", []), separators=(",", ":")),
        json.dumps(card.get("color_identity", []), separators=(",", ":")),
        card.get("lang"),
        bool(card.get("digital", False)),
        json.dumps(card.get("games", []), separators=(",", ":")),
    )


def _create_staging_table(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE staging_cards (
            scryfall_id VARCHAR NOT NULL,
            oracle_id VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            released_on DATE,
            set_code VARCHAR NOT NULL,
            collector_number VARCHAR NOT NULL,
            rarity VARCHAR NOT NULL,
            mana_cost VARCHAR,
            mana_value DOUBLE,
            type_line VARCHAR,
            oracle_text VARCHAR,
            colors_json VARCHAR NOT NULL,
            color_identity_json VARCHAR NOT NULL,
            language VARCHAR,
            digital BOOLEAN NOT NULL,
            games_json VARCHAR NOT NULL
        )
        """
    )


def _insert_batch(connection: duckdb.DuckDBPyConnection, batch: list[tuple[Any, ...]]) -> None:
    placeholders = ", ".join("?" for _ in range(16))
    connection.executemany(f"INSERT INTO staging_cards VALUES ({placeholders})", batch)


def _materialize_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE oracle_cards AS
        SELECT
            oracle_id,
            name,
            mana_cost,
            mana_value,
            type_line,
            oracle_text,
            colors_json,
            color_identity_json
        FROM staging_cards
        QUALIFY row_number() OVER (
            PARTITION BY oracle_id
            ORDER BY released_on DESC NULLS LAST, scryfall_id
        ) = 1
        """
    )
    connection.execute(
        """
        CREATE TABLE card_printings AS
        SELECT
            scryfall_id,
            oracle_id,
            name,
            set_code,
            collector_number,
            rarity,
            released_on,
            language,
            digital,
            games_json
        FROM staging_cards
        ORDER BY set_code, collector_number, scryfall_id
        """
    )
