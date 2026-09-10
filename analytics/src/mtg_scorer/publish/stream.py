"""Streaming publication validation/loading; retain relationship indexes, not full card text."""

import json
from collections.abc import Iterator
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
    source_bytes, records = verified_source(source_dir)
    source_hash = sha256(source_bytes).hexdigest()
    if (
        source_hash != manifest["source_manifest_sha256"]
        or (directory / "source-manifest.json").read_bytes() != source_bytes
    ):
        raise ValueError("source manifest checksum mismatch")
    if (
        header["catalog_snapshot_id"] != manifest["catalog_snapshot_id"]
        or header["schema_version"] != manifest["publication_schema_version"]
        or header["catalog_snapshot_id"]
        != snapshot_identity(source_hash, header["parser_version"], header["selection"])
    ):
        raise ValueError("publication identity mismatch")
    provenance = {(p["raw_sha256"], p["retrieved_at"], s["id"]) for s, p in records}
    compact: dict[str, list[dict[str, Any]]] = {}
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
        compact[table] = []
        for row in rows(path, table):
            validator.validate(row)
            if (
                table == "printings"
                and (row["raw_sha256"], row["retrieved_at"], row["scryfall_id"]) not in provenance
            ):
                raise ValueError("printing provenance mismatch")
            compact[table].append({key: row[key] for key in keys[table]})
        if len(compact[table]) != manifest["row_counts"][table]:
            raise ValueError("row count mismatch")
    validate_relationships(compact)
    return header, manifest
