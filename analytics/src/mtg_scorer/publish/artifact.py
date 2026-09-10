"""Immutable bounded-source export, finalized by a directory rename."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import duckdb

from mtg_scorer.normalize.catalog import PARSER_VERSION, SCHEMA_VERSION, project_catalog
from mtg_scorer.publish.validation import validate_catalog, validate_manifest

TABLES = ("cards", "faces", "printings", "aliases")
SELECTION = {
    "kind": "bounded_sample",
    "description": (
        "Real Scryfall layout sample: 8 printings, 7 Oracle cards; purposefully selected, "
        "incomplete catalog. Retrieved 2026-09-08; no tournament dataset."
    ),
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def snapshot_identity(source_hash: str, parser_version: str, selection: dict[str, str]) -> str:
    return (
        "catalog-"
        + sha256(
            canonical_bytes(
                {
                    "source_manifest_sha256": source_hash,
                    "parser_version": parser_version,
                    "publication_schema_version": SCHEMA_VERSION,
                    "selection": selection,
                }
            )
        ).hexdigest()
    )


def verified_source(source_dir: Path) -> tuple[bytes, list[tuple[dict[str, Any], dict[str, str]]]]:
    manifest_bytes = (source_dir / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    records = []
    for record in manifest["records"]:
        filename = record["raw_file"]
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise ValueError("invalid raw filename")
        raw = (source_dir / filename).read_bytes()
        if sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("raw checksum mismatch")
        card = json.loads(raw)
        if card["id"] != record["scryfall_id"]:
            raise ValueError("source record identity mismatch")
        records.append(
            (
                card,
                {
                    "retrieved_at": record["retrieved_at"],
                    "raw_snapshot_ref": "sha256:" + record["sha256"],
                    "raw_sha256": record["sha256"],
                },
            )
        )
    return manifest_bytes, records


def verify_artifact(directory: Path, source_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = (directory / "catalog.json").read_bytes()
    manifest = json.loads((directory / "manifest.json").read_bytes())
    validate_manifest(manifest, raw)
    source_bytes, records = verified_source(source_dir)
    source_hash = sha256(source_bytes).hexdigest()
    if source_hash != manifest["source_manifest_sha256"]:
        raise ValueError("source manifest checksum mismatch")
    if (directory / "source-manifest.json").read_bytes() != source_bytes:
        raise ValueError("retained source manifest checksum mismatch")
    payload = json.loads(raw)
    if payload["catalog_snapshot_id"] != snapshot_identity(
        source_hash, payload["parser_version"], payload["selection"]
    ):
        raise ValueError("invalid production snapshot identity")
    provenance = {(p["raw_sha256"], p["retrieved_at"], s["id"]) for s, p in records}
    if any(
        (p["raw_sha256"], p["retrieved_at"], p["scryfall_id"]) not in provenance
        for p in payload["printings"]
    ):
        raise ValueError("printing provenance mismatch")
    analytical = json.loads((directory / "analytical-manifest.json").read_bytes())
    for filename, checksum in analytical.items():
        if filename not in {f"{table}.parquet" for table in TABLES}:
            raise ValueError("invalid analytical artifact filename")
        if sha256((directory / filename).read_bytes()).hexdigest() != checksum:
            raise ValueError("analytical artifact checksum mismatch")
    expected_files = {f"{table}.parquet" for table in TABLES if payload[table]}
    if set(analytical) != expected_files:
        raise ValueError("missing analytical artifact")
    return payload, manifest


def export_catalog(
    source_dir: Path,
    output_root: Path,
    *,
    created_at: str | None = None,
    selection: dict[str, str] | None = None,
) -> Path:
    source_bytes, records = verified_source(source_dir)
    source_hash = sha256(source_bytes).hexdigest()
    selection = SELECTION if selection is None else selection
    identity = snapshot_identity(source_hash, PARSER_VERSION, selection)
    destination = output_root / identity
    if destination.exists():
        verify_artifact(destination, source_dir)
        return destination
    tables, excluded = project_catalog(records)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "catalog_snapshot_id": identity,
        "source": "scryfall",
        "parser_version": PARSER_VERSION,
        "created_at": created_at or datetime.now(UTC).isoformat(),
        "selection": selection,
        **tables,
    }
    validate_catalog(payload)
    raw = canonical_bytes(payload)
    manifest = {
        "schema_version": "catalog-manifest-v1",
        "catalog_snapshot_id": identity,
        "publication_schema_version": SCHEMA_VERSION,
        "export_file": "catalog.json",
        "export_sha256": sha256(raw).hexdigest(),
        "export_bytes": len(raw),
        "row_counts": {key: len(tables[key]) for key in TABLES},
        "source_manifest_sha256": source_hash,
        "excluded_record_counts": excluded,
    }
    validate_manifest(manifest, raw)
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".catalog-", dir=output_root))
    try:
        (temporary / "catalog.json").write_bytes(raw)
        (temporary / "source-manifest.json").write_bytes(source_bytes)
        with duckdb.connect() as connection:
            for table in TABLES:
                if not tables[table]:
                    continue
                json_file = temporary / f"{table}.json"
                json_file.write_bytes(canonical_bytes(tables[table]))
                connection.read_json(str(json_file)).write_parquet(
                    str(temporary / f"{table}.parquet"), compression="zstd"
                )
                json_file.unlink()
        (temporary / "analytical-manifest.json").write_bytes(
            canonical_bytes(
                {
                    f"{table}.parquet": sha256(
                        (temporary / f"{table}.parquet").read_bytes()
                    ).hexdigest()
                    for table in TABLES
                    if tables[table]
                }
            )
        )
        (temporary / "manifest.json").write_bytes(canonical_bytes(manifest))
        try:
            os.rename(temporary, destination)
        except OSError:
            if not destination.exists():
                raise
            existing, _ = verify_artifact(destination, source_dir)
            if any(existing[key] != payload[key] for key in payload if key != "created_at"):
                raise ValueError("concurrent export content conflict") from None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination
