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


def test_modern_rankings_follow_the_published_constructed_scores():
    status, page = get()
    assert status == 200
    validate(page, "RankingPage")
    run = page["score_run"]
    assert (run["format_name"], run["source"]) == ("Modern", "topdeck")
    assert (run["events"], run["players"], run["decks"], run["top_cut_decks"]) == (2, 7, 7, 2)
    assert (run["scored_cards"], run["matches"], run["players_per_game"]) == (8, 9, 2)
    assert (run["field_win_rate"], run["field_top_cut_rate"]) == (0.5, 0.5)
    assert (run["series_period_days"], len(run["series_decks"])) == (16, 12)
    assert run["attribution"].startswith("Data provided by TopDeck.gg")
    assert {method["method_id"]: method["scored_cards"] for method in run["methods"]} == {
        "constructed-score": 8,
        "foundation": 8,
        "max-ratio": 8,
        "signature-score": 8,
    }
    assert (page["method_id"], page["output"]) == ("constructed-score", "score")
    assert {
        "format_name": "Modern",
        "source": "topdeck",
        "score_run_id": run["score_run_id"],
        "decks": 7,
        "players_per_game": 2,
    } in page["formats"]
    assert page["total"] == 8
    assert page["view_counts"] == {"all": 8, "risers": 0, "fallers": 0}
    assert (page["previous_score_run_id"], page["max_deck_count"]) == (None, 4)
    assert [(w["score_run_id"], w["active"]) for w in page["windows"]] == [
        (run["score_run_id"], True)
    ]
    ranked = [(card["rank"], card["name"], card["score"]) for card in page["items"]]
    assert ranked[:2] == [(1, "Lightning Bolt", 93.75), (2, "Bonecrusher Giant // Stomp", 81.25)]
    assert [rank for rank, _, _ in ranked] == list(range(1, 9))
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
    assert (bolt["win_rate"], bolt["win_rate_delta"], bolt["top_cut_lift"]) == (0.8, 0.3, 2.0)
    assert bolt["games"] > 0 and bolt["avg_copies"] >= 1
    assert [a["label"] for a in bolt["archetypes"]] == ["Burn", "Izzet Tempo"]
    assert "R" in bolt["archetypes"][0]["colors"]
    assert (bolt["archetype_count"], bolt["rank_change"]) == (2, None)
    assert len(bolt["series_decks"]) == 12
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
    assert fire["rank"] == 4
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
    _, by_win = get(sort="win_rate")
    rates = [card["win_rate"] for card in by_win["items"]]
    assert rates == sorted(rates, reverse=True)
    _, reverse = get(sort="name", order="desc")
    assert names(reverse) == sorted(names(reverse), reverse=True)
    _, risers = get(view="risers")
    assert (risers["total"], risers["view"]) == (0, "risers")


def test_a_pinned_run_and_another_method_are_served():
    _, page = get()
    run_id = page["score_run"]["score_run_id"]
    status, pinned = get(score_run_id=run_id, method="max-ratio")
    assert status == 200
    assert pinned["score_run"]["score_run_id"] == run_id
    assert (pinned["method_id"], pinned["output"]) == ("max-ratio", "max_ratio")
    assert [(card["name"], card["score"]) for card in pinned["items"][:2]] == [
        ("Lightning Bolt", 100.0),
        ("Fire // Ice", 75.0),
    ]
    assert pinned["total"] == 8


def test_the_signature_score_ranks_single_archetype_cards_above_shared_staples():
    status, page = get(method="signature-score")
    assert status == 200
    validate(page, "RankingPage")
    assert (page["method_id"], page["output"]) == ("signature-score", "score")
    ranked = {card["name"]: (card["rank"], card["score"]) for card in page["items"]}
    # Fire // Ice is only ever Izzet Tempo; Lightning Bolt splits between two archetypes.
    assert ranked["Fire // Ice"] == (1, 93.75)
    assert ranked["Lightning Bolt"] == (5, 43.75)


def compare(**query):
    url = BASE + "/api/v1/rankings/compare" + ("?" + urlencode(query, doseq=True) if query else "")
    try:
        with urlopen(url, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def test_compare_ranks_each_card_in_every_format_with_a_constructed_score():
    status, page = compare(format=["Modern", "Vintage"])
    assert status == 200
    validate(page, "ComparePage")
    # Publication tests leave other formats active too; only Modern was asked for and exists.
    assert [f["format_name"] for f in page["formats"]] == ["Modern"]
    assert "Modern" in [f["format_name"] for f in page["available"]]
    assert (page["total"], page["sort"], page["order"], page["every"]) == (8, "best", "desc", False)
    bolt = page["items"][0]
    assert (bolt["name"], bolt["best_format"], bolt["ranked_in"]) == ("Lightning Bolt", "Modern", 1)
    cell = bolt["formats"]["Modern"]
    assert (cell["rank"], cell["score"], cell["win_rate_delta"]) == (1, 93.75, 0.3)
    assert cell["share"] == pytest.approx(4 / 7)


def test_compare_filters_and_sorts_by_one_formats_column():
    _, by_share = compare(format="Modern", sort="Modern:share", every="true")
    shares = [card["formats"]["Modern"]["share"] for card in by_share["items"]]
    assert shares == sorted(shares, reverse=True)
    _, searched = compare(format="Modern", q="fire", color="R")
    assert names(searched) == ["Fire // Ice"]
    _, by_name = compare(format="Modern", sort="name", limit=3, offset=3)
    assert names(by_name) == sorted(names(by_name)) and len(by_name["items"]) == 3
    _, fallback = compare(format="Modern", sort="Vintage:grade")
    assert fallback["sort"] == "best"


def test_compare_grades_by_the_signature_score_where_it_scored_cards():
    status, page = compare(format="Modern", method="signature-score")
    assert status == 200
    validate(page, "ComparePage")
    assert page["method_id"] == "signature-score"
    assert [(f["format_name"], f["scored_cards"]) for f in page["formats"]] == [("Modern", 8)]
    # Every available format published the method; only those it scored are compared.
    assert all(f["scored_cards"] > 0 for f in page["formats"])
    assert "Modern" in [f["format_name"] for f in page["available"]]
    ranked = {card["name"]: card["formats"]["Modern"]["rank"] for card in page["items"]}
    assert (ranked["Fire // Ice"], ranked["Lightning Bolt"]) == (1, 5)
    _, constructed = compare(format="Modern")
    assert constructed["method_id"] == "constructed-score"
    assert names(constructed)[0] == "Lightning Bolt"


@pytest.mark.parametrize(
    ("query", "status", "code"),
    [
        ({"view": "risers"}, 400, "invalid_query"),
        ({"sort": "Modern:elo"}, 400, "invalid_query"),
        ({"method": "max-ratio"}, 400, "invalid_query"),
        ({"format": "Vintage"}, 503, "rankings_unavailable"),
    ],
)
def test_compare_problems_have_stable_codes(query, status, code):
    actual, body = compare(**query)
    assert (actual, body["code"]) == (status, code)


@pytest.mark.parametrize(
    ("query", "status", "code"),
    [
        ({"format": "Vintage"}, 503, "rankings_unavailable"),
        ({"score_run_id": "scores-" + "0" * 64}, 404, "score_run_not_found"),
        ({"method": "elo"}, 400, "invalid_query"),
        ({"grade": "A"}, 400, "invalid_query"),
        ({"limit": "0"}, 400, "invalid_query"),
        ({"order": "up"}, 400, "invalid_query"),
        ({"view": "new"}, 400, "invalid_query"),
    ],
)
def test_problems_have_stable_codes(query, status, code):
    actual, body = get(**query)
    assert (actual, body["code"]) == (status, code)
    validate(body, "CatalogError")
