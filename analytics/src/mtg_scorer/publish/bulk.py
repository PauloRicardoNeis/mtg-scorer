"""Disk-backed serving export using the same face-aware projection as the seed.

SQLite sorts retained source rows; projection holds one printing at a time.
DuckDB's bounded buffer pool converts the resulting JSONL tables to Parquet.
"""

import json
import os
import shutil
import sqlite3
import tempfile
from collections import Counter
from collections.abc import Callable
from contextlib import ExitStack, closing
from hashlib import sha256
from pathlib import Path

import duckdb

from mtg_scorer.ingest.scryfall import _file_sha256, _iter_cards
from mtg_scorer.normalize.catalog import PARSER_VERSION as NORMALIZER_VERSION
from mtg_scorer.normalize.catalog import SCHEMA_VERSION, project_catalog
from mtg_scorer.publish.artifact import TABLES, canonical_bytes

PARSER_VERSION = NORMALIZER_VERSION + "-bulk-v1"

SELECTION = {
    "kind": "bulk",
    "description": (
        "Scryfall default-cards bulk: each printing in English, or its printed language "
        "when English is unavailable. Retains supported Oracle identities, faces, images "
        "and source game availability, including legacy digital games. "
        "Not all languages or all Scryfall objects; "
        "exclusions are counted explicitly. No tournament dataset."
    ),
}


def bulk_identity(manifest: dict, parser_version: str) -> str:
    """Retrieval time and transport URL cannot change the identity of source content."""
    return (
        "catalog-"
        + sha256(
            canonical_bytes(
                {
                    "source": "scryfall",
                    "source_type": manifest["source_type"],
                    "source_updated_at": manifest["source_updated_at"],
                    "content_sha256": manifest["content_sha256"],
                    "parser_version": parser_version,
                    "publication_schema_version": SCHEMA_VERSION,
                    "selection": SELECTION,
                }
            )
        ).hexdigest()
    )


def bulk_source(source_dir: Path):
    source_bytes = (source_dir / "manifest.json").read_bytes()
    manifest = json.loads(source_bytes)
    filename = manifest["raw_file"]
    if Path(filename).name != filename:
        raise ValueError("invalid raw filename")
    raw = source_dir / filename
    if _file_sha256(raw) != manifest["content_sha256"]:
        raise ValueError("raw snapshot checksum mismatch")
    provenance = {
        "raw_sha256": manifest["content_sha256"],
        "raw_snapshot_ref": "sha256:" + manifest["content_sha256"],
        "retrieved_at": manifest["retrieved_at"],
    }
    return source_bytes, ((card, provenance) for card in _iter_cards(raw))


def export_bulk_catalog(
    source_dir: Path, output_root: Path, *, before_validate: Callable[[dict], None] | None = None
) -> Path:
    # Lazy import avoids artifact -> stream -> bulk cycles.
    from mtg_scorer.publish.stream import verify_publication

    source_bytes, records = bulk_source(source_dir)
    source_hash = sha256(source_bytes).hexdigest()
    identity = bulk_identity(json.loads(source_bytes), PARSER_VERSION)
    destination = output_root / identity
    if destination.exists():
        if before_validate:
            before_validate(json.loads((destination / "manifest.json").read_bytes()))
        verify_publication(destination, source_dir)
        return destination
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".bulk-", dir=output_root))
    try:
        counts = dict.fromkeys(TABLES, 0)
        excluded = Counter()
        with closing(sqlite3.connect(temporary / "stage.sqlite")) as db, ExitStack() as stack:
            db.execute("PRAGMA cache_size=-8192")
            db.execute("PRAGMA temp_store=FILE")
            db.execute(
                "CREATE TABLE source(id TEXT PRIMARY KEY, oracle TEXT, english INTEGER, "
                "released TEXT, payload TEXT)"
            )
            for source, _ in records:
                raw = canonical_bytes(source).decode()
                existing = db.execute(
                    "SELECT payload FROM source WHERE id=?", (source["id"],)
                ).fetchone()
                if existing:
                    if existing[0] != raw:
                        raise ValueError("conflicting duplicate printing")
                    continue
                db.execute(
                    "INSERT INTO source VALUES(?,?,?,?,?)",
                    (
                        source["id"],
                        source.get("oracle_id"),
                        source.get("lang") == "en",
                        source.get("released_at"),
                        raw,
                    ),
                )
            db.execute(
                "CREATE INDEX representative ON source(oracle,english DESC,released DESC,id)"
            )
            db.commit()
            outputs = {
                table: stack.enter_context((temporary / f"{table}.jsonl").open("wb"))
                for table in TABLES
            }
            meta = json.loads(source_bytes)
            provenance = {
                "raw_sha256": meta["content_sha256"],
                "raw_snapshot_ref": "sha256:" + meta["content_sha256"],
                "retrieved_at": meta["retrieved_at"],
            }
            previous = None
            for (raw,) in db.execute(
                "SELECT payload FROM source ORDER BY oracle,english DESC,released DESC,id"
            ):
                tables, exclusions = project_catalog([(json.loads(raw), provenance)])
                excluded.update(exclusions)
                if not tables["cards"]:
                    continue
                oracle = tables["cards"][0]["oracle_id"]
                for table in TABLES:
                    if table != "printings" and oracle == previous:
                        continue
                    for row in tables[table]:
                        outputs[table].write(canonical_bytes(row) + b"\n")
                        counts[table] += 1
                previous = oracle
        (temporary / "stage.sqlite").unlink()
        header = {
            "schema_version": SCHEMA_VERSION,
            "catalog_snapshot_id": identity,
            "source": "scryfall",
            "parser_version": PARSER_VERSION,
            # Stable across rebuilds, including a lost artifact directory.
            "created_at": meta["retrieved_at"],
            "selection": SELECTION,
        }
        with (temporary / "catalog.json").open("wb") as out:
            out.write(canonical_bytes(header)[:-1])
            for table in TABLES:
                out.write(b',"' + table.encode() + b'":[')
                with (temporary / f"{table}.jsonl").open("rb") as rows:
                    for index, row in enumerate(rows):
                        out.write((b"," if index else b"") + row.rstrip(b"\n"))
                out.write(b"]")
            out.write(b"}")
        with duckdb.connect(config={"memory_limit": "128MB", "threads": 2}) as db:
            for table in TABLES:
                if counts[table]:
                    db.read_json(
                        str(temporary / f"{table}.jsonl"), format="newline_delimited"
                    ).write_parquet(str(temporary / f"{table}.parquet"), compression="zstd")
                (temporary / f"{table}.jsonl").unlink()
        (temporary / "analytical-manifest.json").write_bytes(
            canonical_bytes(
                {
                    f"{table}.parquet": _file_sha256(temporary / f"{table}.parquet")
                    for table in TABLES
                    if counts[table]
                }
            )
        )
        (temporary / "source-manifest.json").write_bytes(source_bytes)
        (temporary / "manifest.json").write_bytes(
            canonical_bytes(
                {
                    "schema_version": "catalog-manifest-v1",
                    "catalog_snapshot_id": identity,
                    "publication_schema_version": SCHEMA_VERSION,
                    "export_file": "catalog.json",
                    "export_sha256": _file_sha256(temporary / "catalog.json"),
                    "export_bytes": (temporary / "catalog.json").stat().st_size,
                    "row_counts": counts,
                    "source_manifest_sha256": source_hash,
                    "excluded_record_counts": dict(sorted(excluded.items())),
                }
            )
        )
        if before_validate:
            before_validate(json.loads((temporary / "manifest.json").read_bytes()))
        verify_publication(temporary, source_dir)
        os.rename(temporary, destination)
        return destination
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
