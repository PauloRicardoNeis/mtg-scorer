"""Score-run files must satisfy the published contract before writing or publishing."""

import copy

import pytest
from jsonschema import ValidationError
from synthetic_topdeck import BOLT, COUNTERSPELL, open_event, save, weekly_event

from mtg_scorer.ingest.topdeck import read_saved_responses
from mtg_scorer.publish.score_run import build_score_run
from mtg_scorer.publish.score_validation import SCHEMA, validate_score_run
from mtg_scorer.tournament_features import CohortRules

RULES = CohortRules(
    version="synthetic-cohort-v1",
    format_name="Modern",
    starts_on="2026-03-01",
    ends_before="2026-09-01",
)


@pytest.fixture
def document(tmp_path):
    saved = save(tmp_path / "saved", {"search.json": [open_event(), weekly_event()]})
    return build_score_run(read_saved_responses(saved), RULES)


def card(run, oracle_id):
    return next(card for card in run["cards"] if card["oracle_id"] == oracle_id)


def test_a_built_run_satisfies_the_contract(document) -> None:
    validate_score_run(document)


def test_the_schema_is_a_valid_draft_2020_12_schema() -> None:
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda run: run.update(schema_version="score-run-file-v9"), id="version"),
        pytest.param(lambda run: run.update(extra=True), id="unknown-field"),
        pytest.param(lambda run: run["cards"][0].update(oracle_id="bolt"), id="non-uuid-card"),
        pytest.param(lambda run: run["cards"][0].update(deck_count=0), id="zero-decks"),
        pytest.param(lambda run: run["raw_files"][0].update(retrieved_at="soon"), id="bad-time"),
        pytest.param(lambda run: run["runs"][0].update(outputs=[]), id="no-outputs"),
        pytest.param(
            lambda run: run["cohort"]["archetypes"][0].pop("series"), id="half-an-archetype"
        ),
        pytest.param(lambda run: run["cards"][0].pop("deck_copies"), id="decks-without-copies"),
        pytest.param(lambda run: run["decks"][0].update(player="Anyone"), id="unknown-deck-field"),
        pytest.param(lambda run: run["decks"][0]["record"].pop("draws"), id="partial-record"),
        pytest.param(lambda run: run["decks"][0].pop("sideboard"), id="commanders-alone"),
        pytest.param(
            lambda run: run["decks"][2]["sideboard"].append({"oracle_id": BOLT, "copies": 1}),
            id="unnamed-sideboard-card",
        ),
        pytest.param(lambda run: run["cohort"]["events"][0].update(url="http://x"), id="plain-url"),
    ],
)
def test_the_schema_rejects_malformed_runs(document, change) -> None:
    broken = copy.deepcopy(document)
    change(broken)

    with pytest.raises(ValidationError):
        validate_score_run(broken)


def duplicate_card(run):
    run["cards"].append(copy.deepcopy(run["cards"][0]))


def unknown_top_cut_with_known_results(run):
    card(run, BOLT)["top_cut_count"] = None


def label_without_labelled_decks(run):
    card(run, BOLT)["archetype"]["labelled_deck_count"] = 0


def wrong_scored_count(run):
    run["population"]["scored_cards"] += 1


def mismatched_identity(run):
    run["method_identities"][0][1] = "another-version"


def duplicate_method(run):
    run["runs"].append(copy.deepcopy(run["runs"][0]))
    run["method_identities"].append(list(run["method_identities"][0]))


def missing_score(run):
    run["runs"][0]["scores"].pop()


def extra_output(run):
    run["runs"][0]["scores"][0]["values"]["surprise"] = 1.0


def duplicate_archetype(run):
    run["cohort"]["archetypes"].append(copy.deepcopy(run["cohort"]["archetypes"][0]))


def archetype_record_past_its_decks(run):
    run["cohort"]["archetypes"][0]["record"]["decks"] += 5


def archetype_win_rate_without_games(run):
    archetype = run["cohort"]["archetypes"][0]
    archetype["record"].update(wins=0, losses=0, draws=0)


def cards_list_unpublished_decks(run):
    del run["decks"]


def a_card_without_its_decks(run):
    for key in ("decks", "deck_copies"):
        del card(run, BOLT)[key]


def a_deck_missing(run):
    run["decks"].pop()


def duplicate_deck(run):
    run["decks"][1]["source_deck_id"] = run["decks"][0]["source_deck_id"]


def a_deck_from_another_event(run):
    run["decks"][0]["source_event_id"] = "synthetic-elsewhere"


def oldest_event_first(run):
    run["decks"].reverse()


def a_card_missing_a_deck(run):
    card(run, BOLT)["decks"].pop()


def unordered_card_decks(run):
    card(run, BOLT)["decks"].reverse()


def a_card_deck_past_the_run(run):
    card(run, BOLT)["decks"][-1] = len(run["decks"])


def copies_past_the_mainboard(run):
    card(run, BOLT)["deck_copies"][0] += 1


def decks_from_one_event(run):
    # Bolt's three decks, all moved to the open: the weekly no longer counts.
    card(run, BOLT)["decks"] = [2, 3, 4]


def a_deck_result_rewritten(run):
    run["decks"][2]["made_top_cut"] = False


def a_deck_record_rewritten(run):
    run["decks"][0]["record"]["wins"] += 1


def a_deck_without_its_lists(run):
    for key in ("commanders", "sideboard"):
        del run["decks"][0][key]


def a_commander_outside_its_deck(run):
    # The weekly's Burn deck plays no Counterspell.
    run["decks"][0]["commanders"] = [card(run, COUNTERSPELL)["oracle_id"]]


def a_sideboard_card_twice(run):
    listed = {"oracle_id": BOLT, "name": "Bolt", "copies": 1}
    run["decks"][0]["sideboard"] = [listed, dict(listed)]


def a_deck_without_main_deck_cards(run):
    # The open's last deck, dropped from Counterspell's list, would list nothing.
    counterspell = card(run, COUNTERSPELL)
    counterspell["decks"].pop()
    counterspell["deck_copies"].pop()
    counterspell["deck_count"] -= 1
    counterspell["mainboard_copies"] -= 4
    counterspell["top_cut_known_decks"] -= 1
    counterspell["record"].update(decks=2, wins=2, losses=2)


def run_before_whole_deck_lists(run):
    # Files from card-usage-v7 list decks without their commanders and sideboards.
    for deck in run["decks"]:
        del deck["commanders"], deck["sideboard"]


def run_before_deck_lists(run):
    # Files before card-usage-v7 list no decks.
    del run["decks"]
    for each in run["cards"]:
        del each["decks"], each["deck_copies"]


def run_before_archetype_performance(run):
    # Files from card-usage-v4 and earlier describe archetypes by their cores alone.
    for archetype in run["cohort"]["archetypes"]:
        for key in list(archetype):
            if key not in ("label", "deck_count", "core_cards"):
                del archetype[key]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (duplicate_card, "duplicate card oracle_id"),
        (unknown_top_cut_with_known_results, "top_cut_count must be unknown exactly"),
        (label_without_labelled_decks, "archetype label and labelled decks disagree"),
        (wrong_scored_count, "scored_cards does not match"),
        (mismatched_identity, "method_identities do not match"),
        (duplicate_method, "duplicate method_id"),
        (missing_score, "must score each scored card exactly once"),
        (extra_output, "exactly its declared outputs"),
        (duplicate_archetype, "duplicate archetype label"),
        (archetype_record_past_its_decks, "exceed the archetype's decks"),
        (archetype_win_rate_without_games, "win rate must be unknown exactly without games"),
        (cards_list_unpublished_decks, "cards list decks the run does not publish"),
        (a_card_without_its_decks, "every card must list its decks"),
        (a_deck_missing, "decks do not match the cohort's deck total"),
        (duplicate_deck, "duplicate source_deck_id"),
        (a_deck_from_another_event, "a deck's event is not in the cohort"),
        (oldest_event_first, "newest event first"),
        (a_card_missing_a_deck, "must list each of the card's decks"),
        (unordered_card_decks, "must ascend within the run's decks"),
        (a_card_deck_past_the_run, "must ascend within the run's decks"),
        (copies_past_the_mainboard, "do not add up to its mainboard copies"),
        (decks_from_one_event, "do not match its event count"),
        (a_deck_result_rewritten, "top cuts do not match its counts"),
        (a_deck_record_rewritten, "records do not add up to its record"),
        (a_deck_without_its_lists, "every deck must state its commanders and sideboard"),
        (a_commander_outside_its_deck, "a commander is not in its main deck"),
        (a_sideboard_card_twice, "a sideboard card is listed twice"),
        (a_deck_without_main_deck_cards, "a deck has no main deck card"),
    ],
)
def test_relationships_the_schema_cannot_express_are_checked(document, change, message) -> None:
    broken = copy.deepcopy(document)
    change(broken)

    with pytest.raises(ValueError, match=message):
        validate_score_run(broken)


def test_runs_before_archetype_performance_still_validate(document) -> None:
    older = copy.deepcopy(document)
    run_before_archetype_performance(older)

    validate_score_run(older)


def test_runs_before_whole_deck_lists_still_validate(document) -> None:
    older = copy.deepcopy(document)
    run_before_whole_deck_lists(older)

    validate_score_run(older)


def test_runs_before_deck_lists_still_validate(document) -> None:
    older = copy.deepcopy(document)
    run_before_deck_lists(older)

    validate_score_run(older)
