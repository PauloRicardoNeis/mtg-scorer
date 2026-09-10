"""Python-produced artifacts through real PostgreSQL and a running Java HTTP server."""

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from mtg_scorer.publish.artifact import export_catalog
from mtg_scorer.publish.postgres import publish_catalog, rollback_catalog

BASE = os.environ.get("CATALOG_TEST_API_URL")
PUBLISH_DSN = os.environ.get("CATALOG_TEST_PUBLISH_DSN")
pytestmark = pytest.mark.skipif(
    not BASE or not PUBLISH_DSN, reason="running Java and publisher DSN required"
)
ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "analytics/seeds/scryfall-layouts-v1"
SPEC = json.loads((ROOT / "contracts/catalog-api.openapi.json").read_bytes())
BOLT = "4457ed35-7c10-48c8-9776-456485fdf070"
DELVER = "edd531b9-f615-4399-8c8c-1c5e18c4acbf"


def get(path, **query):
    url = BASE + path + ("?" + urlencode(query, doseq=True) if query else "")
    try:
        with urlopen(url, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def validate(body, model):
    Draft202012Validator(
        {"$ref": "#/components/schemas/" + model, "components": SPEC["components"]},
        format_checker=FormatChecker(),
    ).validate(body)


def test_real_contract_faces_filters_literal_search_and_dataset():
    status, page = get("/api/v1/cards", q="insectile")
    assert status == 200
    validate(page, "CardPage")
    assert [c["oracle_id"] for c in page["items"]] == [DELVER]
    snapshot = page["catalog_snapshot_id"]
    status, detail = get("/api/v1/cards/" + DELVER, catalog_snapshot_id=snapshot)
    assert status == 200
    validate(detail, "CardDetail")
    assert detail["oracle_text"] is None
    assert detail["colors"] == ["U"]
    assert detail["faces"][1]["mana_cost"] == ""
    assert all(f["oracle_text"] for f in detail["faces"])
    for query in ({"set": "2x2", "rarity": "common"}, {"q": "%"}, {"q": "_"}, {"set": "zzzzzz"}):
        status, empty = get("/api/v1/cards", **query)
        assert status == 200 and empty["items"] == []
    status, eligible = get("/api/v1/cards", set="m11", rarity="common", game="paper")
    assert status == 200 and eligible["items"][0]["oracle_id"] == BOLT
    assert eligible["items"][0]["eligible_printing_count"] == 1
    status, prints = get(f"/api/v1/cards/{BOLT}/printings", set="2x2", rarity="common")
    validate(prints, "PrintingPage")
    assert status == 200 and prints["items"] == []
    status, dataset = get("/api/v1/snapshots/" + snapshot)
    assert status == 200
    validate(dataset, "Snapshot")
    assert dataset["card_count"] == 7 and dataset["printing_count"] == 8
    assert dataset["tournament_evidence"] == {
        "state": "not_available",
        "reason_codes": ["no_tournament_dataset"],
    }


def test_invalid_queries_cursor_tampering_and_unknown_resources():
    for query in (
        {"q": ["one", "two"]},
        {"limit": 101},
        {"unknown": "x"},
        {"color_identity": "RR"},
        {"sort": "power"},
    ):
        status, body = get("/api/v1/cards", **query)
        assert status == 400 and body["code"] == "invalid_query"
    for path, code in (
        ("/api/v1/cards/00000000-0000-4000-8000-000000000000", "card_not_found"),
        ("/api/v1/snapshots/unknown", "snapshot_not_found"),
    ):
        status, body = get(path)
        assert status == 404 and body["code"] == code
    _, page = get("/api/v1/cards", limit=2)
    cursor = page["next_cursor"]
    decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    decoded["last_key"] = ["x", "' OR true --"]
    invalid = base64.urlsafe_b64encode(json.dumps(decoded).encode()).decode().rstrip("=")
    for query in (
        {"cursor": invalid, "limit": 2},
        {"cursor": cursor, "limit": 3},
        {"cursor": cursor, "limit": 2, "q": "bolt"},
    ):
        status, body = get("/api/v1/cards", **query)
        assert status == 400 and body["code"] == "invalid_cursor"


def test_pagination_and_printings_remain_pinned_across_real_python_refresh(tmp_path):
    _, first = get("/api/v1/cards", limit=2)
    old = first["catalog_snapshot_id"]
    _, printing_first = get(f"/api/v1/cards/{BOLT}/printings", limit=1)
    refreshed = export_catalog(
        SEED,
        tmp_path,
        selection={
            "kind": "bounded_sample",
            "description": "Real source replay for HTTP refresh consistency",
        },
    )
    publish_catalog(refreshed, SEED, PUBLISH_DSN)
    try:
        assert get("/api/v1/cards")[1]["catalog_snapshot_id"] == refreshed.name
        items = list(first["items"])
        cursor = first["next_cursor"]
        while cursor:
            status, page = get("/api/v1/cards", limit=2, cursor=cursor)
            assert status == 200 and page["catalog_snapshot_id"] == old
            items.extend(page["items"])
            cursor = page["next_cursor"]
        assert len(items) == len({c["oracle_id"] for c in items}) == 7
        status, printing_next = get(
            f"/api/v1/cards/{BOLT}/printings", limit=1, cursor=printing_first["next_cursor"]
        )
        assert status == 200 and printing_next["catalog_snapshot_id"] == old
        assert printing_next["items"][0]["scryfall_id"] != printing_first["items"][0]["scryfall_id"]
        validate(printing_next, "PrintingPage")
    finally:
        rollback_catalog(PUBLISH_DSN, old, refreshed.name)


def test_synthetic_unknown_colorless_and_ambiguous_literal_aliases(tmp_path):
    """Synthetic adversaries stay separate from the real demonstration and restore its pointer."""
    import copy
    import hashlib
    from uuid import NAMESPACE_URL, uuid5

    _, listing = get("/api/v1/snapshots")
    previous = listing["active_catalog_snapshot_id"]
    source = json.loads((SEED / "00.json").read_bytes())
    source_dir = tmp_path / "synthetic-source"
    source_dir.mkdir()
    records = []
    for index, identity in enumerate(([], ["U"], None)):
        card = copy.deepcopy(source)
        card["id"] = str(uuid5(NAMESPACE_URL, f"synthetic-printing-{index}"))
        card["oracle_id"] = str(uuid5(NAMESPACE_URL, f"synthetic-oracle-{index}"))
        card["name"] = "Shared%_Alias" if index < 2 else "Unknown identity"
        card["color_identity"] = identity
        card["colors"] = identity
        if identity is None:
            card.pop("cmc", None)
        raw = json.dumps(card).encode()
        filename = f"{index}.json"
        (source_dir / filename).write_bytes(raw)
        records.append(
            {
                "raw_file": filename,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "scryfall_id": card["id"],
                "retrieved_at": "2026-09-08T00:46:15Z",
            }
        )
    (source_dir / "manifest.json").write_text(
        json.dumps({"selection": "SYNTHETIC adversarial HTTP fixture", "records": records})
    )
    artifact = export_catalog(
        source_dir,
        tmp_path / "export",
        selection={
            "kind": "bounded_sample",
            "description": "SYNTHETIC adversarial fixture; not real catalog evidence",
        },
    )
    publish_catalog(artifact, source_dir, PUBLISH_DSN)
    try:
        assert len(get("/api/v1/cards")[1]["items"]) == 3
        assert len(get("/api/v1/cards", color_identity="C")[1]["items"]) == 1
        assert len(get("/api/v1/cards", color_identity="U")[1]["items"]) == 2
        assert len(get("/api/v1/cards", color_identity="R")[1]["items"]) == 1
        assert len(get("/api/v1/cards", q="%_")[1]["items"]) == 2
        unknown = get("/api/v1/cards", q="unknown")[1]["items"][0]
        assert unknown["color_identity"] is None
        assert get("/api/v1/cards/" + unknown["oracle_id"])[1]["mana_value"] is None
    finally:
        rollback_catalog(PUBLISH_DSN, previous, artifact.name)


@pytest.mark.skipif(
    os.environ.get("CATALOG_TEST_EMPTY") != "1", reason="runs before first publication"
)
def test_initial_catalog_is_unavailable_not_an_empty_success():
    status, body = get("/api/v1/cards")
    assert status == 503 and body["code"] == "catalog_unavailable"
    assert get("/actuator/health/liveness")[0] == 200
    assert get("/actuator/health/readiness")[0] == 503
