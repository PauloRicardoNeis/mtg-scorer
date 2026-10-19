"""Published score runs through the running Java API (verify seeds the SYNTHETIC run).

`demo.py verify` publishes `fixtures/topdeck-synthetic` over the seed catalog's cards before
these tests run, so they only read: two events, seven decks, Lightning Bolt in four of them.
"""

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
from jsonschema import Draft202012Validator, FormatChecker

BASE = os.environ.get("CATALOG_TEST_API_URL")
pytestmark = pytest.mark.skipif(not BASE, reason="running Java API required")
ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "contracts/catalog-api.openapi.json").read_bytes())
BOLT = "4457ed35-7c10-48c8-9776-456485fdf070"
UNLISTED = "6a1f5b52-3c4d-5e6f-8a9b-0c1d2e3f4a5b"


def get(**query):
    url = BASE + "/api/v1/rankings" + ("?" + urlencode(query, doseq=True) if query else "")
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


def names(page):
    return [card["name"] for card in page["items"]]


def test_modern_rankings_follow_the_published_volume_scores():
    status, page = get()
    assert status == 200
    validate(page, "RankingPage")
    run = page["score_run"]
    assert (run["format_name"], run["source"]) == ("Modern", "topdeck")
    assert (run["events"], run["players"], run["decks"], run["top_cut_decks"]) == (2, 7, 7, 2)
    assert run["attribution"].startswith("Data provided by TopDeck.gg")
    assert {method["method_id"] for method in run["methods"]} == {"foundation", "max-ratio"}
    assert (page["method_id"], page["output"]) == ("max-ratio", "max_ratio")
    assert {"format_name": "Modern", "source": "topdeck", "score_run_id": run["score_run_id"]} in (
        page["formats"]
    )
    assert page["total"] == 8
    ranked = [(card["rank"], card["name"], card["score"]) for card in page["items"]]
    assert ranked[:2] == [(1, "Lightning Bolt", 100.0), (2, "Fire // Ice", 75.0)]
    assert {rank for rank, _, score in ranked if score == 50.0} == {3}
    assert {rank for rank, _, score in ranked if score == 25.0} == {6}
    assert "Island" not in names(page)


def test_cards_carry_usage_and_catalog_details_or_explicit_nulls():
    _, page = get()
    cards = {card["oracle_id"]: card for card in page["items"]}
    bolt = cards[BOLT]
    assert (bolt["deck_count"], bolt["event_count"]) == (4, 2)
    assert (bolt["top_cut_count"], bolt["top_cut_known_decks"]) == (2, 2)
    assert (bolt["archetype_label"], bolt["archetype_deck_count"]) == ("Burn", 2)
    assert bolt["type_line"] == "Instant"
    assert bolt["color_identity"] == ["R"]
    assert bolt["preview_printing"]["images"]
    unlisted = cards[UNLISTED]
    assert unlisted["preview_printing"] is None
    assert unlisted["type_line"] is None
    assert unlisted["color_identity"] is None


def test_filters_keep_each_cards_overall_rank():
    status, instants = get(type="instant")
    assert status == 200
    assert "Fire // Ice" in names(instants)
    assert all("Instant" in card["type_line"] for card in instants["items"])
    fire = next(card for card in instants["items"] if card["name"] == "Fire // Ice")
    assert fire["rank"] == 2
    _, searched = get(q="fire")
    assert names(searched) == ["Fire // Ice"]
    _, white = get(color="W")
    assert names(white) == ["Bruna, the Fading Light"]


def test_sorting_and_paging_use_stored_values():
    _, by_name = get(sort="name", limit=3)
    assert names(by_name) == sorted(names(by_name))
    assert (by_name["total"], by_name["limit"], len(by_name["items"])) == (8, 3, 3)
    _, rest = get(sort="name", limit=3, offset=6)
    assert len(rest["items"]) == 2
    _, by_decks = get(sort="decks")
    counts = [card["deck_count"] for card in by_decks["items"]]
    assert counts == sorted(counts, reverse=True)
    _, by_cuts = get(sort="top_cuts")
    assert by_cuts["items"][0]["name"] == "Lightning Bolt"


def test_a_pinned_run_and_another_method_are_served():
    _, page = get()
    run_id = page["score_run"]["score_run_id"]
    status, pinned = get(score_run_id=run_id, method="foundation")
    assert status == 200
    assert pinned["score_run"]["score_run_id"] == run_id
    assert (pinned["method_id"], pinned["output"]) == ("foundation", "staple")
    assert pinned["total"] == 8


@pytest.mark.parametrize(
    ("query", "status", "code"),
    [
        ({"format": "Vintage"}, 503, "rankings_unavailable"),
        ({"score_run_id": "scores-" + "0" * 64}, 404, "score_run_not_found"),
        ({"method": "elo"}, 400, "invalid_query"),
        ({"grade": "A"}, 400, "invalid_query"),
        ({"limit": "0"}, 400, "invalid_query"),
    ],
)
def test_problems_have_stable_codes(query, status, code):
    actual, body = get(**query)
    assert (actual, body["code"]) == (status, code)
    validate(body, "CatalogError")
