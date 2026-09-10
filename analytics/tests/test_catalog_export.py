import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb
import pytest
from jsonschema import ValidationError

from mtg_scorer.normalize.catalog import project_catalog
from mtg_scorer.normalize.names import name_key
from mtg_scorer.publish.artifact import export_catalog, verified_source, verify_artifact
from mtg_scorer.publish.validation import validate_catalog

SEED = Path(__file__).resolve().parents[1] / "seeds/scryfall-layouts-v1"


def test_real_seed_faces_provenance_and_replay(tmp_path):
    directory = export_catalog(SEED, tmp_path)
    payload, manifest = verify_artifact(directory, SEED)
    assert manifest["row_counts"] == {"cards": 7, "faces": 10, "printings": 8, "aliases": 17}
    assert manifest["excluded_record_counts"] == {}
    delver = next(c for c in payload["cards"] if c["name"].startswith("Delver"))
    assert delver["oracle_text"] is None
    assert delver["mana_cost"] is None
    assert delver["colors"] == ["U"]
    faces = [f for f in payload["faces"] if f["oracle_id"] == delver["oracle_id"]]
    assert all(f["oracle_text"] for f in faces)
    assert faces[1]["mana_cost"] == ""
    bolt = next(c for c in payload["cards"] if c["name"] == "Lightning Bolt")
    printing = next(
        p for p in payload["printings"] if p["scryfall_id"] == bolt["source_scryfall_id"]
    )
    assert (printing["set_code"], printing["rarity"]) == ("2x2", "uncommon")
    before = (directory / "catalog.json").read_bytes()
    assert export_catalog(SEED, tmp_path, created_at="2099-01-01T00:00:00Z") == directory
    assert (directory / "catalog.json").read_bytes() == before
    with duckdb.connect() as connection:
        assert (
            connection.read_parquet(str(directory / "faces.parquet")).count("*").fetchone()[0] == 10
        )


def test_order_independent_representative_and_ambiguous_aliases():
    _, records = verified_source(SEED)
    assert project_catalog(records) == project_catalog(reversed(records))
    card, provenance = copy.deepcopy(records[0])
    card["lang"] = "ja"
    card["released_at"] = "2099-01-01"
    tables, _ = project_catalog([(card, provenance), records[1]])
    assert tables["cards"][0]["source_scryfall_id"] == records[1][0]["id"]
    other = copy.deepcopy(card)
    other["id"] = "00000000-0000-4000-8000-000000000001"
    other["oracle_id"] = "00000000-0000-4000-8000-000000000002"
    tables, _ = project_catalog([(card, provenance), (other, provenance)])
    assert len(tables["aliases"]) == 2
    assert tables["aliases"][0]["alias_key"] == tables["aliases"][1]["alias_key"]


def test_missingness_layout_policy_and_conflicting_printings():
    _, records = verified_source(SEED)
    card, provenance = copy.deepcopy(records[2])
    card["layout"] = "future_layout"
    card.pop("cmc")
    card.pop("color_identity")
    card["card_faces"][1].pop("colors")
    tables, _ = project_catalog([(card, provenance)])
    assert len(tables["faces"]) == 2
    assert all(
        tables["cards"][0][key] is None for key in ("mana_value", "color_identity", "colors")
    )
    card["color_identity"] = []
    assert project_catalog([(card, provenance)])[0]["cards"][0]["color_identity"] == []
    with pytest.raises(ValueError, match="conflicting duplicate"):
        project_catalog([(card, provenance), records[2]])
    card.pop("oracle_id")
    card["layout"] = "reversible_card"
    assert project_catalog([(card, provenance)])[1] == {"missing_oracle_id": 1}


def test_corruption_failed_export_and_concurrent_finalize(tmp_path, monkeypatch):
    import mtg_scorer.publish.artifact as artifact

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: export_catalog(SEED, tmp_path), range(2)))
    assert results[0] == results[1]
    good = (results[0] / "catalog.json").read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(
            artifact,
            "project_catalog",
            lambda _: (_ for _ in ()).throw(ValueError("failed normalization")),
        )
        with pytest.raises(ValueError, match="failed normalization"):
            export_catalog(
                SEED, tmp_path, selection={"kind": "bounded_sample", "description": "new selection"}
            )
    assert (results[0] / "catalog.json").read_bytes() == good
    assert len(list(tmp_path.iterdir())) == 1
    (results[0] / "catalog.json").write_bytes(good + b" ")
    with pytest.raises(ValueError, match="size mismatch"):
        export_catalog(SEED, tmp_path)


def test_raw_hash_and_invalid_payload_are_rejected(tmp_path):
    import shutil

    shutil.copytree(SEED, tmp_path / "seed")
    (tmp_path / "seed/00.json").write_text("{}")
    with pytest.raises(ValueError, match="raw checksum"):
        export_catalog(tmp_path / "seed", tmp_path / "output")
    assert not (tmp_path / "output").exists()
    directory = export_catalog(SEED, tmp_path / "output")
    payload = json.loads((directory / "catalog.json").read_bytes())
    for invalid in (float("nan"), float("inf"), -1):
        payload["cards"][0]["mana_value"] = invalid
        with pytest.raises((ValueError, ValidationError)):
            validate_catalog(payload)


def test_literal_name_key():
    assert name_key(" ＦＩＲＥ\t //  Ice ") == "fire // ice"
    assert name_key("Æther 100%_ ") == "Æther 100%_"


def test_streaming_publication_validation_matches_the_bounded_export(tmp_path):
    from mtg_scorer.publish.stream import rows, verify_publication

    directory = export_catalog(SEED, tmp_path)
    payload, manifest = verify_artifact(directory, SEED)
    header, streamed_manifest = verify_publication(directory, SEED)
    assert header["catalog_snapshot_id"] == payload["catalog_snapshot_id"]
    assert streamed_manifest == manifest
    for table in ("cards", "faces", "printings", "aliases"):
        assert list(rows(directory / "catalog.json", table)) == payload[table]
    (directory / "faces.parquet").write_bytes(b"damaged")
    with pytest.raises(ValueError, match="analytical artifact checksum"):
        verify_artifact(directory, SEED)
