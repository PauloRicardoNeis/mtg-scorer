"""Offline conformance checks for publication schemas and generated Spring OpenAPI."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from mtg_scorer.publish.validation import name_key, validate_catalog, validate_manifest
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[1] / "contracts"
SCHEMA = json.loads((ROOT / "catalog-publication.schema.json").read_text())
SPEC = json.loads((ROOT / "catalog-api.openapi.json").read_text())
MANIFEST_SCHEMA = json.loads((ROOT / "catalog-manifest.schema.json").read_text())


class ContractChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads((ROOT / "fixtures/catalog-valid.json").read_text())

    def test_valid_catalog_and_unknowns(self) -> None:
        validate_catalog(self.payload)
        self.assertIsNone(self.payload["cards"][0]["oracle_text"])
        self.payload["cards"][0]["colors"] = None
        validate_catalog(self.payload)
        self.payload["cards"][0]["colors"] = []
        validate_catalog(self.payload)  # Both states are legal and remain distinct.

    def test_rejects_invalid_publication(self) -> None:
        mutations = {
            "unsupported_version": lambda p: p.update(schema_version="v999"),
            "scores_in_catalog": lambda p: p.update(buildaround_signal=100),
            "duplicate_card": lambda p: p["cards"].append(copy.deepcopy(p["cards"][0])),
            "orphan_printing": lambda p: p["printings"][0].update(
                oracle_id="00000000-0000-4000-8000-000000000099"
            ),
            "lost_faces": lambda p: p.update(faces=[]),
            "lost_aliases": lambda p: p.update(aliases=[]),
            "naive_timestamp": lambda p: p.update(created_at="2026-09-07T00:00:00"),
            "missing_checksum": lambda p: p["printings"][0].update(raw_sha256=""),
            "nonfinite_mana": lambda p: p["cards"][0].update(mana_value=float("-inf")),
            "positive_infinity": lambda p: p["cards"][0].update(mana_value=float("inf")),
            "nan": lambda p: p["cards"][0].update(mana_value=float("nan")),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                payload = copy.deepcopy(self.payload)
                mutate(payload)
                with self.assertRaises((ValueError, ValidationError)):
                    validate_catalog(payload)

    def test_printing_filter_counterexample(self) -> None:
        # Expected relation for future PostgreSQL/API tests, not production filtering.
        printings = self.payload["printings"]
        matches = [p for p in printings if p["set_code"] == "aaa" and p["rarity"] == "common"]
        self.assertEqual(matches, [])
        self.assertTrue(any(p["set_code"] == "aaa" for p in printings))
        self.assertTrue(any(p["rarity"] == "common" for p in printings))

    def test_name_key_preserves_identity(self) -> None:
        self.assertEqual(name_key("  FIRE  //\tIce "), "fire // ice")
        self.assertEqual(name_key("Ｆｉｒｅ"), "fire")
        self.assertNotEqual(name_key("Æther"), name_key("Aether"))

    def test_export_integrity_and_manifest(self) -> None:
        raw = (ROOT / "fixtures/catalog-valid.json").read_bytes()
        manifest = {
            "schema_version": "catalog-manifest-v1",
            "catalog_snapshot_id": self.payload["catalog_snapshot_id"],
            "publication_schema_version": self.payload["schema_version"],
            "export_file": "catalog.json",
            "export_sha256": hashlib.sha256(raw).hexdigest(),
            "export_bytes": len(raw),
            "row_counts": {
                table: len(self.payload[table])
                for table in ("cards", "faces", "printings", "aliases")
            },
            "source_manifest_sha256": "0" * 64,
            "excluded_record_counts": {},
        }
        validate_manifest(manifest, raw)
        with self.assertRaises(ValueError):
            validate_manifest(manifest, raw.replace(b"Fixture", b"Changed"))
        manifest["row_counts"]["cards"] += 1
        with self.assertRaises(ValueError):
            validate_manifest(manifest, raw)

    def test_openapi_and_response_fixture(self) -> None:
        Draft202012Validator.check_schema(SCHEMA)
        Draft202012Validator.check_schema(MANIFEST_SCHEMA)
        validate(SPEC)
        schema = {
            "$ref": "#/components/schemas/CardPage",
            "components": SPEC["components"],
        }
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        page = json.loads((ROOT / "fixtures/card-page.json").read_text())
        validator.validate(page)
        page["items"][0]["eligible_printing_count"] = 0
        with self.assertRaises(ValidationError):
            validator.validate(page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
