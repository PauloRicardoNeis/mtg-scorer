"""Executable catalog v1 validation; shared by export and publication."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from mtg_scorer.normalize.names import name_key

ROOT = Path(__file__).resolve().parents[4] / "contracts"
SCHEMA = json.loads((ROOT / "catalog-publication.schema.json").read_text())
MANIFEST_SCHEMA = json.loads((ROOT / "catalog-manifest.schema.json").read_text())


def validate_catalog(payload: dict[str, Any]) -> None:
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(payload)
    validate_relationships(payload)


def validate_relationships(payload: dict[str, Any]) -> None:
    """Validate compact identity indexes after rows have passed their closed schemas."""

    def keyed(table: str, keys: tuple[str, ...]) -> dict[tuple[Any, ...], dict[str, Any]]:
        rows = {tuple(row[key] for key in keys): row for row in payload[table]}
        if len(rows) != len(payload[table]):
            raise ValueError(f"duplicate {table} key")
        return rows

    cards = keyed("cards", ("oracle_id",))
    printings = keyed("printings", ("scryfall_id",))
    faces = keyed("faces", ("oracle_id", "face_index"))
    keyed("aliases", ("oracle_id", "alias_key", "kind"))
    for table in ("printings", "faces", "aliases"):
        if any((row["oracle_id"],) not in cards for row in payload[table]):
            raise ValueError(f"orphan {table} row")
    for card in cards.values():
        if card["mana_value"] is not None and not math.isfinite(card["mana_value"]):
            raise ValueError("mana_value must be finite")
        representative = printings.get((card["source_scryfall_id"],))
        if representative is None or representative["oracle_id"] != card["oracle_id"]:
            raise ValueError("representative printing must belong to this Oracle card")
        if card["name_key"] != name_key(card["name"]):
            raise ValueError("invalid name_key")
        indices = sorted(index for oracle, index in faces if oracle == card["oracle_id"])
        if indices != list(range(len(indices))):
            raise ValueError("face indices must be contiguous from zero")
        if (
            card["layout"] in {"transform", "modal_dfc", "split", "adventure", "flip"}
            and len(indices) < 2
        ):
            raise ValueError("known multi-face layout requires its faces")
        aliases = {
            r["alias_key"] for r in payload["aliases"] if r["oracle_id"] == card["oracle_id"]
        }
        expected = {card["name_key"]} | {
            name_key(face["name"])
            for face in payload["faces"]
            if face["oracle_id"] == card["oracle_id"]
        }
        if not expected <= aliases:
            raise ValueError("missing canonical or face alias")
    for alias in payload["aliases"]:
        if alias["alias_key"] != name_key(alias["alias_key"]):
            raise ValueError("alias key is not normalized")
    for printing in printings.values():
        image_indices = [image["face_index"] for image in printing["images"]]
        if len(image_indices) != len(set(image_indices)):
            raise ValueError("duplicate printing image slot")
        if any(
            index is not None and (printing["oracle_id"], index) not in faces
            for index in image_indices
        ):
            raise ValueError("image references missing face")
    set_names: dict[str, str] = {}
    for printing in printings.values():
        previous = set_names.setdefault(printing["set_code"], printing["set_name"])
        if previous != printing["set_name"]:
            raise ValueError("conflicting set names")
    if len(set_names) > 4096:
        raise ValueError("set vocabulary exceeds metadata bound")


def validate_manifest(manifest: dict[str, Any], export_bytes: bytes) -> None:
    """Check exported bytes only; source-manifest/raw verification belongs to importer."""
    Draft202012Validator(MANIFEST_SCHEMA).validate(manifest)
    if len(export_bytes) != manifest["export_bytes"]:
        raise ValueError("export size mismatch")
    if hashlib.sha256(export_bytes).hexdigest() != manifest["export_sha256"]:
        raise ValueError("export checksum mismatch")
    payload = json.loads(export_bytes)
    validate_catalog(payload)
    if payload["catalog_snapshot_id"] != manifest["catalog_snapshot_id"]:
        raise ValueError("snapshot mismatch")
    if payload["schema_version"] != manifest["publication_schema_version"]:
        raise ValueError("schema mismatch")
    for table, expected in manifest["row_counts"].items():
        if len(payload[table]) != expected:
            raise ValueError(f"{table} count mismatch")
