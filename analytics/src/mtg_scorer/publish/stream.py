"""Streaming publication validation/loading; retain relationship indexes, not full card text."""

import json
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing
from hashlib import file_digest, sha256
from pathlib import Path
from typing import Any

import ijson
from jsonschema import Draft202012Validator, FormatChecker

from mtg_scorer.publish.artifact import TABLES, snapshot_identity, verified_source
from mtg_scorer.publish.validation import MANIFEST_SCHEMA, SCHEMA, validate_relationships


def rows(path: Path, table: str) -> Iterator[dict[str, Any]]:
    with path.open("rb") as source:
        yield from ijson.items(source, table + ".item", use_float=True)


def verify_publication(directory: Path, source_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="catalog-validation-") as temporary:
        with closing(sqlite3.connect(Path(temporary) / "validation.sqlite")) as db:
            db.execute("PRAGMA cache_size=-8192")
            db.execute("PRAGMA temp_store=FILE")
            return _verify(directory, source_dir, db)


def _verify(directory: Path, source_dir: Path, db) -> tuple[dict[str, Any], dict[str, Any]]:
    path = directory / "catalog.json"
    manifest = json.loads((directory / "manifest.json").read_bytes())
    Draft202012Validator(MANIFEST_SCHEMA).validate(manifest)
    with path.open("rb") as source:
        digest = file_digest(source, "sha256").hexdigest()
    if digest != manifest["export_sha256"] or path.stat().st_size != manifest["export_bytes"]:
        raise ValueError("export integrity mismatch")
    header: dict[str, Any] = {}
    seen = set()
    with path.open("rb") as source:
        for prefix, event, value in ijson.parse(source, use_float=True):
            if prefix == "" and event == "map_key":
                if value in seen or value not in SCHEMA["properties"]:
                    raise ValueError("duplicate or unknown export field")
                seen.add(value)
            if prefix in TABLES and event not in {"start_array", "end_array"}:
                raise ValueError("catalog table must be an array")
            if (
                prefix in SCHEMA["properties"]
                and prefix not in (*TABLES, "selection")
                and event in {"string", "number", "boolean", "null"}
            ):
                header[prefix] = value
    with path.open("rb") as source:
        header["selection"] = next(ijson.items(source, "selection", use_float=True))
    if seen != set(SCHEMA["required"]):
        raise ValueError("missing export field")
    header_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            key: schema for key, schema in SCHEMA["properties"].items() if key not in TABLES
        },
        "required": [key for key in SCHEMA["required"] if key not in TABLES],
    }
    Draft202012Validator(header_schema, format_checker=FormatChecker()).validate(header)
    source_manifest = json.loads((source_dir / "manifest.json").read_bytes())
    if "content_sha256" in source_manifest:
        from mtg_scorer.publish.bulk import SELECTION, bulk_identity, bulk_source

        source_bytes, records = bulk_source(source_dir)
        expected_identity = bulk_identity(source_manifest, header["parser_version"])
        if header["selection"] != SELECTION:
            raise ValueError("invalid bulk selection")
    else:
        source_bytes, records = verified_source(source_dir)
        expected_identity = snapshot_identity(
            sha256(source_bytes).hexdigest(), header["parser_version"], header["selection"]
        )
    source_hash = sha256(source_bytes).hexdigest()
    if (
        source_hash != manifest["source_manifest_sha256"]
        or (directory / "source-manifest.json").read_bytes() != source_bytes
    ):
        raise ValueError("source manifest checksum mismatch")
    if (
        header["catalog_snapshot_id"] != manifest["catalog_snapshot_id"]
        or header["schema_version"] != manifest["publication_schema_version"]
        or header["catalog_snapshot_id"] != expected_identity
    ):
        raise ValueError("publication identity mismatch")
    db.execute("CREATE TABLE provenance(id TEXT PRIMARY KEY, hash TEXT, retrieved TEXT)")
    for source, provenance in records:
        db.execute(
            "INSERT OR IGNORE INTO provenance VALUES(?,?,?)",
            (
                source["id"],
                provenance["raw_sha256"],
                provenance["retrieved_at"],
            ),
        )
    db.execute("CREATE TABLE compact(kind TEXT, oracle TEXT, payload TEXT)")
    db.execute("CREATE INDEX compact_oracle ON compact(oracle,kind)")
    db.execute("CREATE TABLE printing_ids(id TEXT PRIMARY KEY)")
    db.execute("CREATE TABLE sets(code TEXT PRIMARY KEY, name TEXT)")
    keys = {
        "cards": ("oracle_id", "source_scryfall_id", "name", "name_key", "layout", "mana_value"),
        "faces": ("oracle_id", "face_index", "name"),
        "printings": ("scryfall_id", "oracle_id", "set_code", "set_name", "images"),
        "aliases": ("oracle_id", "alias_key", "kind"),
    }
    definitions = dict(zip(TABLES, ("card", "face", "printing", "alias"), strict=True))
    for table in TABLES:
        validator = Draft202012Validator(
            {"$ref": "#/$defs/" + definitions[table], "$defs": SCHEMA["$defs"]},
            format_checker=FormatChecker(),
        )
        count = 0
        for row in rows(path, table):
            validator.validate(row)
            if table == "printings":
                if (
                    not db.execute(
                        "SELECT 1 FROM provenance WHERE id=? AND hash=? AND retrieved=?",
                        (
                            row["scryfall_id"],
                            row["raw_sha256"],
                            row["retrieved_at"],
                        ),
                    ).fetchone()
                    or row["raw_snapshot_ref"] != "sha256:" + row["raw_sha256"]
                ):
                    raise ValueError("printing provenance mismatch")
                db.execute("INSERT INTO printing_ids VALUES(?)", (row["scryfall_id"],))
                previous = db.execute(
                    "SELECT name FROM sets WHERE code=?", (row["set_code"],)
                ).fetchone()
                if previous and previous[0] != row["set_name"]:
                    raise ValueError("conflicting set names")
                db.execute(
                    "INSERT OR IGNORE INTO sets VALUES(?,?)", (row["set_code"], row["set_name"])
                )
            db.execute(
                "INSERT INTO compact VALUES(?,?,?)",
                (
                    table,
                    row["oracle_id"],
                    json.dumps({key: row[key] for key in keys[table]}),
                ),
            )
            count += 1
        if count != manifest["row_counts"][table]:
            raise ValueError("row count mismatch")
    if db.execute("SELECT count(*) FROM sets").fetchone()[0] > 4096:
        raise ValueError("set vocabulary exceeds metadata bound")
    # Relationships are local to one Oracle identity, so text and all-catalog
    # indexes never need to coexist in the Python heap.
    for (oracle,) in db.execute("SELECT DISTINCT oracle FROM compact"):
        compact = {table: [] for table in TABLES}
        for kind, raw in db.execute("SELECT kind,payload FROM compact WHERE oracle=?", (oracle,)):
            compact[kind].append(json.loads(raw))
        validate_relationships(compact)
    analytical = json.loads((directory / "analytical-manifest.json").read_bytes())
    if set(analytical) != {f"{table}.parquet" for table in TABLES if manifest["row_counts"][table]}:
        raise ValueError("missing analytical artifact")
    for filename, checksum in analytical.items():
        with (directory / filename).open("rb") as source:
            if file_digest(source, "sha256").hexdigest() != checksum:
                raise ValueError("analytical artifact checksum mismatch")
    return header, manifest
