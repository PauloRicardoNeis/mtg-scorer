"""Published score runs through the running Java API (verify seeds the SYNTHETIC run).

`demo.py verify` publishes `fixtures/topdeck-synthetic` over the seed catalog's cards before
these tests run, so they only read: two events, seven decks, Lightning Bolt in four of them.
The API opens on the Overall run built from that run; the tests that read the Modern run's
own numbers ask for its format.
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


def modern(**query):
    """The synthetic run's format; without a format the API serves the Overall run."""
    return get(format="Modern", **query)


def validate(body, model):
    Draft202012Validator(
        {"$ref": "#/components/schemas/" + model, "components": SPEC["components"]},
        format_checker=FormatChecker(),
    ).validate(body)


def names(page):
    return [card["name"] for card in page["items"]]


def test_modern_rankings_follow_the_published_constructed_scores():
    status, page = modern()
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
        "hidden-gem-score": 8,
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
        "commanders": 0,
    } in page["formats"]
    assert page["total"] == 8
    assert page["view_counts"] == {"all": 8, "risers": 0, "fallers": 0}
    assert (page["previous_score_run_id"], page["max_deck_count"]) == (None, 4)
    assert [(w["score_run_id"], w["active"], w["commanders"]) for w in page["windows"]] == [
        (run["score_run_id"], True, 0)
    ]
    ranked = [(card["rank"], card["name"], card["score"]) for card in page["items"]]
    assert ranked[:2] == [(1, "Lightning Bolt", 93.75), (2, "Bonecrusher Giant // Stomp", 81.25)]
    assert [rank for rank, _, _ in ranked] == list(range(1, 9))
    assert "Island" not in names(page)


def test_without_a_format_the_overall_run_opens():
    status, page = get()
    assert status == 200
    validate(page, "RankingPage")
    assert (page["score_run"]["format_name"], page["method_id"]) == ("Overall", "overall-grade")
    assert any(entry["format_name"] == "Modern" for entry in page["formats"])


def test_cards_carry_usage_and_catalog_details_or_explicit_nulls():
    _, page = modern()
    cards = {card["oracle_id"]: card for card in page["items"]}
    bolt = cards[BOLT]
    assert (bolt["deck_count"], bolt["event_count"]) == (4, 2)
    assert (bolt["top_cut_count"], bolt["top_cut_known_decks"]) == (2, 2)
    assert (bolt["archetype_label"], bolt["archetype_deck_count"]) == ("Burn", 2)
    assert bolt["type_line"] == "Instant"
    assert bolt["color_identity"] == ["R"]
    assert bolt["preview_printing"]["images"]
    assert (bolt["win_rate"], bolt["win_rate_delta"], bolt["top_cut_lift"]) == (0.8, 0.3, 2.0)
    assert bolt["games"] > 0
    assert bolt["avg_copies"] >= 1
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
    # Delver's type lines name Humans, Bruna's rules text does.
    _, humans = get(q="human")
    assert set(names(humans)) == {
        "Delver of Secrets // Insectile Aberration",
        "Bruna, the Fading Light",
    }
    _, typed = get(q="human", **{"in": "type"})
    assert names(typed) == ["Delver of Secrets // Insectile Aberration"]
    _, white = get(color="W")
    assert names(white) == ["Bruna, the Fading Light"]


def test_sorting_and_paging_use_stored_values():
    _, by_name = modern(sort="name", limit=3)
    assert names(by_name) == sorted(names(by_name))
    assert (by_name["total"], by_name["limit"], len(by_name["items"])) == (8, 3, 3)
    _, rest = modern(sort="name", limit=3, offset=6)
    assert len(rest["items"]) == 2
    _, by_decks = modern(sort="decks")
    counts = [card["deck_count"] for card in by_decks["items"]]
    assert counts == sorted(counts, reverse=True)
    _, by_cuts = modern(sort="top_cuts")
    assert by_cuts["items"][0]["name"] == "Lightning Bolt"
    _, by_win = modern(sort="win_rate")
    rates = [card["win_rate"] for card in by_win["items"]]
    assert rates == sorted(rates, reverse=True)
    _, reverse = modern(sort="name", order="desc")
    assert names(reverse) == sorted(names(reverse), reverse=True)
    _, risers = modern(view="risers")
    assert (risers["total"], risers["view"]) == (0, "risers")


def test_a_pinned_run_and_another_method_are_served():
    _, page = modern()
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
    status, page = modern(method="signature-score")
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
    assert names(by_name) == sorted(names(by_name))
    assert len(by_name["items"]) == 3
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


def commanders(**query):
    search = "?" + urlencode(query, doseq=True) if query else ""
    url = BASE + "/api/v1/rankings/commanders" + search
    try:
        with urlopen(url, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def test_a_format_whose_decks_name_no_commanders_lists_none():
    # The synthetic Modern decks carry TopDeck labels, so no archetype is a commander.
    status, page = commanders(format="Modern")
    assert status == 200
    validate(page, "CommanderPage")
    assert page["score_run"]["format_name"] == "Modern"
    assert (page["total"], page["max_deck_count"], page["items"]) == (0, 0, [])
    assert (page["sort"], page["order"], page["previous_score_run_id"]) == ("decks", "desc", None)
    _, fewer = commanders(format="Modern", min_decks="5")
    assert (fewer["total"], fewer["max_deck_count"]) == (0, 0)


@pytest.mark.parametrize(
    ("query", "status", "code"),
    [
        ({}, 503, "rankings_unavailable"),
        ({"format": "Modern", "sort": "score"}, 400, "invalid_query"),
        ({"format": "Modern", "type": "creature"}, 400, "invalid_query"),
        ({"format": "Modern", "view": "risers"}, 400, "invalid_query"),
        ({"format": "Modern", "min_decks": "0"}, 400, "invalid_query"),
    ],
)
def test_commander_problems_have_stable_codes(query, status, code):
    # Without a format, commanders default to EDH, which verify does not publish.
    actual, body = commanders(**query)
    assert (actual, body["code"]) == (status, code)
    validate(body, "CatalogError")


def decks(card, **query):
    url = BASE + f"/api/v1/cards/{card}/decks" + ("?" + urlencode(query) if query else "")
    try:
        with urlopen(url, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def test_a_cards_decks_are_the_published_decks_that_played_it_newest_event_first():
    status, page = decks(BOLT)
    assert status == 200
    validate(page, "CardDeckPage")
    assert [(f["format_name"], f["deck_count"]) for f in page["formats"]] == [("Modern", 4)]
    assert (page["run"]["format_name"], page["total"], page["offset"]) == ("Modern", 4, 0)
    # The weekly's two Bolt decks, then the open's: positions skip decks without Bolt.
    assert [deck["position"] for deck in page["items"]] == [0, 1, 3, 4]
    assert [deck["copies"] for deck in page["items"]] == [4, 2, 4, 4]
    weekly = page["items"][0]
    assert weekly["event"] == {
        "source_event_id": "synthetic-verify-weekly",
        "name": "SYNTHETIC verify weekly",
        "url": "https://topdeck.gg/bracket/synthetic-verify-weekly",
        "occurred_on": "2026-05-02",
        "players": 3,
    }
    assert (weekly["archetype"], weekly["wins"], weekly["losses"], weekly["draws"]) == (
        "Burn",
        2,
        0,
        0,
    )
    # The weekly cut to no top 8; the open's two Bolt decks made its top 2.
    assert [deck["made_top_cut"] for deck in page["items"]] == [None, None, True, True]


def test_a_cards_decks_page_within_a_pinned_run():
    _, first = decks(BOLT, limit=2)
    status, second = decks(BOLT, limit=2, offset=2, score_run_id=first["run"]["score_run_id"])
    assert status == 200
    assert [deck["position"] for deck in second["items"]] == [3, 4]
    _, past = decks(BOLT, offset=4)
    assert (past["total"], past["items"]) == (4, [])


def test_a_card_out_of_the_catalog_still_lists_its_decks_and_an_unplayed_one_none():
    _, unlisted = decks(UNLISTED)
    assert [deck["source_deck_id"] for deck in unlisted["items"]] == ["synthetic-verify-open#3"]
    status, unplayed = decks("00000000-0000-4000-8000-000000000000")
    assert status == 200
    validate(unplayed, "CardDeckPage")
    assert (unplayed["formats"], unplayed["run"], unplayed["total"]) == ([], None, 0)


@pytest.mark.parametrize(
    ("card", "query", "status", "code"),
    [
        ("bolt", {}, 400, "invalid_query"),
        (BOLT, {"sort": "newest"}, 400, "invalid_query"),
        (BOLT, {"limit": "101"}, 400, "invalid_query"),
        (BOLT, {"score_run_id": "scores-" + "0" * 64}, 404, "score_run_not_found"),
    ],
)
def test_deck_problems_have_stable_codes(card, query, status, code):
    actual, body = decks(card, **query)
    assert (actual, body["code"]) == (status, code)
    validate(body, "CatalogError")


def deck(run, position, **query):
    url = BASE + f"/api/v1/decks/{run}/{position}" + ("?" + urlencode(query) if query else "")
    try:
        with urlopen(url, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def test_a_deck_is_read_with_its_whole_list_in_the_catalog():
    _, page = decks(BOLT)
    run = page["run"]["score_run_id"]
    status, weekly = deck(run, 0)
    assert status == 200
    validate(weekly, "DeckDetail")
    assert (weekly["source_deck_id"], weekly["archetype"], weekly["run"]["score_run_id"]) == (
        "synthetic-verify-weekly#1",
        "Burn",
        run,
    )
    # A listed deck states its commanders and the sideboard its source reported, here empty.
    assert (weekly["commanders"], weekly["sideboard"]) == ([], [])
    assert sum(card["copies"] for card in weekly["mainboard"]) == 7
    bolt = next(card for card in weekly["mainboard"] if card["oracle_id"] == BOLT)
    assert (bolt["copies"], bolt["type_line"], bolt["mana_cost"], bolt["in_catalog"]) == (
        4,
        "Instant",
        "{R}",
        True,
    )
    # A card the catalog does not have keeps the run's name and has no details.
    _, third = deck(run, 5, catalog_snapshot_id=weekly["catalog_snapshot_id"])
    unlisted = next(card for card in third["mainboard"] if card["oracle_id"] == UNLISTED)
    assert (unlisted["name"], unlisted["in_catalog"], unlisted["type_line"]) == (
        "Synthetic Unlisted Card",
        False,
        None,
    )


@pytest.mark.parametrize(
    ("run", "position", "query", "status", "code"),
    [
        (None, "99", {}, 404, "deck_not_found"),
        ("scores-" + "0" * 64, "0", {}, 404, "score_run_not_found"),
        (None, "first", {}, 400, "invalid_query"),
        (None, "0", {"offset": "1"}, 400, "invalid_query"),
    ],
)
def test_deck_page_problems_have_stable_codes(run, position, query, status, code):
    if run is None:
        run = decks(BOLT)[1]["run"]["score_run_id"]
    actual, body = deck(run, position, **query)
    assert (actual, body["code"]) == (status, code)
    validate(body, "CatalogError")
