"""Every CHECK constraint of the ``scores`` schema is mirrored before a run file reaches
PostgreSQL, so a file that passes Python validation cannot fail on COPY (SYNTHETIC data).

``database_checks`` reads the CHECKs out of the Flyway migrations under
``api/src/main/resources/db/migration``. ``COVERAGE`` names, for each one, a mutation of
a valid run file that the Python side rejects, or the reason no file-level check applies.
A CHECK added by a new migration fails ``test_every_database_check_is_accounted_for``
until it is mapped here, and every mapped mutation is shown to be rejected.
"""

import copy
import json
import re
from pathlib import Path

import pytest
from jsonschema import ValidationError
from synthetic_topdeck import BOLT, COUNTERSPELL, open_event, save, weekly_event

from mtg_scorer.ingest.topdeck import read_saved_responses
from mtg_scorer.publish.overall_run import score_overall
from mtg_scorer.publish.score_run import build_score_run, write_score_run
from mtg_scorer.publish.score_validation import validate_overall_run, validate_score_run
from mtg_scorer.tournament_features import CohortRules

MIGRATIONS = Path(__file__).resolve().parents[2] / "api/src/main/resources/db/migration"
RULES = CohortRules(
    version="synthetic-parity-v1",
    format_name="Modern",
    starts_on="2026-03-01",
    ends_before="2026-09-01",
)

# Reasons a CHECK has no file-level mirror.
PUBLICATION = "publication state, set by the database functions"
DERIVED = "derived by the publisher from already validated content"
SUPERSEDED = "superseded by a later migration"


def database_checks() -> dict[tuple[str, str], str]:
    """Each ``(table, expression)`` CHECK on a ``scores`` table, with the migration naming it."""

    checks: dict[tuple[str, str], str] = {}
    for path in sorted(MIGRATIONS.glob("V*__*.sql")):
        text = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
        table = None
        for match in re.finditer(r"\b(?:CREATE|ALTER)\s+TABLE\s+(\w+)\.(\w+)|\bCHECK\s*\(", text):
            if match.group(1):
                table = match.group(2) if match.group(1) == "scores" else None
                continue
            if table is None:
                continue
            depth, end = 0, match.end() - 1
            start = end
            while True:
                if text[end] == "(":
                    depth += 1
                elif text[end] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                end += 1
            checks[(table, " ".join(text[start + 1 : end].split()))] = path.name
    return checks


@pytest.fixture
def document(tmp_path):
    saved = save(tmp_path / "saved", {"search.json": [open_event(), weekly_event()]})
    return build_score_run(read_saved_responses(saved), RULES)


def card(run, oracle_id):
    return next(card for card in run["cards"] if card["oracle_id"] == oracle_id)


def archetype(run):
    return run["cohort"]["archetypes"][0]


def score(run):
    return run["runs"][0]["scores"][0]


def without_decks(run):
    """The run as a file before feature pipeline card-usage-v7 listed decks."""

    del run["decks"]
    for each in run["cards"]:
        del each["decks"]
        del each["deck_copies"]


MUTATIONS = {}


def mutation(function):
    MUTATIONS[function.__name__] = function
    return function


# score_run
@mutation
def bad_run_id(run):
    run["score_run_id"] = "scores-not-a-hash"


@mutation
def wrong_schema_version(run):
    run["schema_version"] = "score-run-file-v9"


@mutation
def bad_source(run):
    run["source"] = "Top Deck"


@mutation
def blank_format_name(run):
    run["cohort"]["rules"]["format_name"] = " "


@mutation
def window_ends_before_it_starts(run):
    run["cohort"]["rules"].update(starts_on="2026-09-01", ends_before="2026-03-01")


@mutation
def blank_dataset_snapshot_id(run):
    run["dataset_snapshot_id"] = ""


@mutation
def blank_parser_version(run):
    run["parser_version"] = ""


@mutation
def blank_feature_pipeline_version(run):
    run["feature_pipeline_version"] = ""


@mutation
def bad_cohort_rules_hash(run):
    run["cohort_rules_hash"] = "nope"


@mutation
def blank_population_rule(run):
    run["population_rule"] = ""


@mutation
def blank_attribution(run):
    run["attribution"] = ""


# score_run_card
@mutation
def blank_card_name(run):
    card(run, BOLT)["name"] = " "


@mutation
def zero_deck_count(run):
    card(run, BOLT)["deck_count"] = 0


@mutation
def zero_event_count(run):
    card(run, BOLT)["event_count"] = 0


@mutation
def events_past_decks(run):
    without_decks(run)
    bolt = card(run, BOLT)
    bolt["event_count"] = bolt["deck_count"] + 1


@mutation
def negative_known_cuts(run):
    card(run, BOLT)["top_cut_known_decks"] = -1


@mutation
def known_cuts_past_decks(run):
    without_decks(run)
    bolt = card(run, BOLT)
    bolt["top_cut_known_decks"] = bolt["deck_count"] + 1


@mutation
def blank_archetype_label(run):
    card(run, BOLT)["archetype"]["label"] = ""


@mutation
def negative_archetype_decks(run):
    card(run, BOLT)["archetype"]["deck_count"] = -1


@mutation
def labelled_below_archetype_decks(run):
    counterspell = card(run, COUNTERSPELL)["archetype"]
    counterspell["labelled_deck_count"] = counterspell["deck_count"] - 1


@mutation
def labelled_past_decks(run):
    bolt = card(run, BOLT)
    bolt["archetype"]["labelled_deck_count"] = bolt["deck_count"] + 1


@mutation
def known_cut_without_results(run):
    card(run, BOLT)["top_cut_known_decks"] = 0


@mutation
def cuts_past_known_decks(run):
    without_decks(run)
    bolt = card(run, BOLT)
    bolt["top_cut_count"] = bolt["top_cut_known_decks"] + 1


@mutation
def label_without_labelled_decks(run):
    card(run, BOLT)["archetype"]["labelled_deck_count"] = 0


@mutation
def label_with_zero_archetype_decks(run):
    card(run, BOLT)["archetype"]["deck_count"] = 0


@mutation
def copies_below_decks(run):
    bolt = card(run, BOLT)
    bolt["mainboard_copies"] = bolt["deck_count"] - 1


@mutation
def record_past_decks(run):
    bolt = card(run, BOLT)
    bolt["record"]["decks"] = bolt["deck_count"] + 1


@mutation
def negative_record_wins(run):
    card(run, BOLT)["record"]["wins"] = -1


@mutation
def win_rate_above_one(run):
    card(run, BOLT)["performance"]["win_rate"] = 1.5


@mutation
def delta_below_minus_one(run):
    card(run, BOLT)["performance"]["win_rate_delta"] = -2


@mutation
def ci95_above_one(run):
    card(run, BOLT)["performance"]["win_rate_ci95"] = 2


@mutation
def negative_lift(run):
    card(run, BOLT)["performance"]["top_cut_lift"] = -1


@mutation
def share_delta_above_one(run):
    card(run, BOLT)["performance"]["share_delta"] = 2


@mutation
def short_series(run):
    card(run, BOLT)["series"].pop()


@mutation
def negative_distinct_archetypes(run):
    card(run, BOLT)["archetypes"]["distinct"] = -1


@mutation
def partial_record(run):
    del card(run, BOLT)["record"]["draws"]


@mutation
def win_rate_without_games(run):
    card(run, BOLT)["record"].update(wins=0, losses=0, draws=0)


@mutation
def negative_deck_position(run):
    card(run, BOLT)["decks"][0] = -1


@mutation
def zero_deck_copies(run):
    card(run, BOLT)["deck_copies"][0] = 0


@mutation
def copies_without_positions(run):
    del card(run, BOLT)["decks"]


@mutation
def deck_positions_short(run):
    bolt = card(run, BOLT)
    bolt["decks"].pop()
    bolt["deck_copies"].pop()


# score_run_method, card_score, card_score_input
@mutation
def bad_method_id(run):
    run["runs"][0]["method_id"] = "Bad_ID"


@mutation
def blank_method_version(run):
    run["runs"][0]["method_version"] = " "


@mutation
def bad_config_hash(run):
    run["runs"][0]["method_config_hash"] = "x"


@mutation
def blank_method_label(run):
    run["runs"][0]["label"] = ""


@mutation
def blank_method_description(run):
    run["runs"][0]["description"] = ""


@mutation
def no_outputs(run):
    run["runs"][0]["outputs"] = []


@mutation
def blank_output_name(run):
    score(run)["values"][""] = 1.0


@mutation
def infinite_score_value(run):
    values = score(run)["values"]
    values[next(iter(values))] = float("inf")


@mutation
def nan_score_value(run):
    values = score(run)["values"]
    values[next(iter(values))] = float("nan")


@mutation
def blank_input_name(run):
    score(run)["inputs"][""] = 0.5


@mutation
def infinite_input_value(run):
    score(run)["inputs"]["parity_probe"] = float("-inf")


# score_run_card_archetype
@mutation
def four_top_archetypes(run):
    card(run, BOLT)["archetypes"]["top"].extend(
        {"label": f"Synthetic {n}", "deck_count": 1} for n in range(3)
    )


@mutation
def blank_top_archetype_label(run):
    card(run, BOLT)["archetypes"]["top"][0]["label"] = ""


@mutation
def zero_top_archetype_decks(run):
    card(run, BOLT)["archetypes"]["top"][0]["deck_count"] = 0


# score_run_archetype
@mutation
def blank_archetype_core_label(run):
    archetype(run)["label"] = ""


@mutation
def zero_archetype_core_decks(run):
    archetype(run)["deck_count"] = 0


@mutation
def zero_archetype_events(run):
    archetype(run)["event_count"] = 0


@mutation
def archetype_events_past_decks(run):
    archetype(run)["event_count"] = archetype(run)["deck_count"] + 1


@mutation
def negative_archetype_cuts(run):
    archetype(run)["top_cut_count"] = -1


@mutation
def archetype_known_cuts_past_decks(run):
    archetype(run)["top_cut_known_decks"] = archetype(run)["deck_count"] + 1


@mutation
def archetype_record_past_decks(run):
    archetype(run)["record"]["decks"] = archetype(run)["deck_count"] + 1


@mutation
def negative_archetype_wins(run):
    archetype(run)["record"]["wins"] = -1


@mutation
def archetype_win_rate_above_one(run):
    archetype(run)["performance"]["win_rate"] = 2


@mutation
def archetype_delta_out_of_range(run):
    archetype(run)["performance"]["win_rate_delta"] = 2


@mutation
def archetype_ci95_out_of_range(run):
    archetype(run)["performance"]["win_rate_ci95"] = -1


@mutation
def archetype_negative_lift(run):
    archetype(run)["performance"]["top_cut_lift"] = -1


@mutation
def archetype_share_delta_out_of_range(run):
    archetype(run)["performance"]["share_delta"] = -2


@mutation
def archetype_short_series(run):
    archetype(run)["series"].pop()


@mutation
def half_an_archetype(run):
    del archetype(run)["series"]


@mutation
def archetype_cut_without_results(run):
    described = next(a for a in run["cohort"]["archetypes"] if a["top_cut_count"] is not None)
    described["top_cut_known_decks"] = 0


@mutation
def archetype_win_rate_without_games(run):
    archetype(run)["record"].update(wins=0, losses=0, draws=0)


# score_run_deck
@mutation
def blank_deck_id(run):
    run["decks"][0]["source_deck_id"] = ""


@mutation
def blank_deck_event(run):
    run["decks"][0]["source_event_id"] = ""


@mutation
def blank_event_name(run):
    run["cohort"]["events"][0]["name"] = ""


@mutation
def plain_event_url(run):
    run["cohort"]["events"][0]["url"] = "http://topdeck.gg/bracket/x"


@mutation
def zero_event_players(run):
    run["cohort"]["events"][0]["players"] = 0


@mutation
def blank_deck_archetype(run):
    run["decks"][0]["archetype"] = ""


@mutation
def zero_final_rank(run):
    run["decks"][0]["final_rank"] = 0


@mutation
def negative_deck_record(run):
    recorded = next(deck for deck in run["decks"] if deck["record"])
    recorded["record"]["wins"] = -1


@mutation
def partial_deck_record(run):
    recorded = next(deck for deck in run["decks"] if deck["record"])
    del recorded["record"]["draws"]


@mutation
def commanders_without_sideboard(run):
    del run["decks"][0]["sideboard"]


@mutation
def commander_outside_its_deck(run):
    # The newest deck plays Bolt alone, so Counterspell cannot be its commander.
    run["decks"][0]["commanders"] = [COUNTERSPELL]


@mutation
def blank_sideboard_name(run):
    # The synthetic sideboards are empty, so the card is added to an observed one.
    run["decks"][0]["sideboard"] = [{"oracle_id": COUNTERSPELL, "name": " ", "copies": 1}]


@mutation
def zero_sideboard_copies(run):
    run["decks"][0]["sideboard"] = [{"oracle_id": COUNTERSPELL, "name": "Counter", "copies": 0}]


COVERAGE = {
    ("score_run", "score_run_id ~ '^scores-[0-9a-f]{64}$'"): "bad_run_id",
    ("score_run", "schema_version = 'score-run-file-v1'"): SUPERSEDED,
    ("score_run", "schema_version IN ('score-run-file-v1','score-run-file-v2')"): SUPERSEDED,
    (
        "score_run",
        "schema_version IN ('score-run-file-v1','score-run-file-v2','overall-run-file-v1')",
    ): "wrong_schema_version",
    ("score_run", "source ~ '^[a-z0-9][a-z0-9-]*$'"): "bad_source",
    ("score_run", "format_name <> ''"): "blank_format_name",
    ("score_run", "window_ends_before > window_starts_on"): "window_ends_before_it_starts",
    ("score_run", "dataset_snapshot_id <> ''"): "blank_dataset_snapshot_id",
    ("score_run", "parser_version <> ''"): "blank_parser_version",
    ("score_run", "feature_pipeline_version <> ''"): "blank_feature_pipeline_version",
    ("score_run", "cohort_rules_hash ~ '^[0-9a-f]{64}$'"): "bad_cohort_rules_hash",
    ("score_run", "population_rule <> ''"): "blank_population_rule",
    ("score_run", "attribution <> ''"): "blank_attribution",
    ("score_run", "results_sha256 ~ '^[0-9a-f]{64}$'"): DERIVED,
    ("score_run", "state IN ('staging','published')"): PUBLICATION,
    ("score_run", "(state = 'published') = (published_at IS NOT NULL)"): PUBLICATION,
    ("score_run_card", "name <> ''"): "blank_card_name",
    ("score_run_card", "deck_count > 0"): "zero_deck_count",
    ("score_run_card", "event_count > 0 AND event_count <= deck_count"): (
        "zero_event_count",
        "events_past_decks",
    ),
    ("score_run_card", "top_cut_known_decks BETWEEN 0 AND deck_count"): (
        "negative_known_cuts",
        "known_cuts_past_decks",
    ),
    ("score_run_card", "archetype_label <> ''"): "blank_archetype_label",
    ("score_run_card", "archetype_deck_count >= 0"): "negative_archetype_decks",
    (
        "score_run_card",
        "labelled_deck_count BETWEEN archetype_deck_count AND deck_count",
    ): ("labelled_below_archetype_decks", "labelled_past_decks"),
    ("score_run_card", "(top_cut_count IS NULL) = (top_cut_known_decks = 0)"): (
        "known_cut_without_results"
    ),
    (
        "score_run_card",
        "top_cut_count IS NULL OR top_cut_count BETWEEN 0 AND top_cut_known_decks",
    ): "cuts_past_known_decks",
    ("score_run_card", "(archetype_label IS NULL) = (labelled_deck_count = 0)"): (
        "label_without_labelled_decks"
    ),
    ("score_run_card", "(archetype_label IS NULL) = (archetype_deck_count = 0)"): (
        "label_with_zero_archetype_decks"
    ),
    ("score_run_card", "mainboard_copies IS NULL OR mainboard_copies >= deck_count"): (
        "copies_below_decks"
    ),
    ("score_run_card", "record_decks IS NULL OR record_decks BETWEEN 0 AND deck_count"): (
        "record_past_decks"
    ),
    ("score_run_card", "record_wins IS NULL OR record_wins >= 0"): "negative_record_wins",
    ("score_run_card", "record_losses IS NULL OR record_losses >= 0"): "negative_record_wins",
    ("score_run_card", "record_draws IS NULL OR record_draws >= 0"): "negative_record_wins",
    ("score_run_card", "win_rate IS NULL OR win_rate BETWEEN 0 AND 1"): "win_rate_above_one",
    ("score_run_card", "win_rate_delta IS NULL OR win_rate_delta BETWEEN -1 AND 1"): (
        "delta_below_minus_one"
    ),
    ("score_run_card", "win_rate_ci95 IS NULL OR win_rate_ci95 BETWEEN 0 AND 1"): (
        "ci95_above_one"
    ),
    ("score_run_card", "top_cut_lift IS NULL OR top_cut_lift >= 0"): "negative_lift",
    ("score_run_card", "share_delta IS NULL OR share_delta BETWEEN -1 AND 1"): (
        "share_delta_above_one"
    ),
    ("score_run_card", "series_decks IS NULL OR cardinality(series_decks) = 12"): "short_series",
    ("score_run_card", "archetype_count IS NULL OR archetype_count >= 0"): (
        "negative_distinct_archetypes"
    ),
    (
        "score_run_card",
        "(record_decks IS NULL) = (record_wins IS NULL) AND (record_wins IS NULL) = "
        "(record_losses IS NULL) AND (record_losses IS NULL) = (record_draws IS NULL)",
    ): "partial_record",
    ("score_run_card", "win_rate IS NULL OR record_wins + record_losses + record_draws > 0"): (
        "win_rate_without_games"
    ),
    ("score_run_card", "deck_positions IS NULL OR 0 <= ALL(deck_positions)"): (
        "negative_deck_position"
    ),
    ("score_run_card", "deck_copies IS NULL OR 1 <= ALL(deck_copies)"): "zero_deck_copies",
    ("score_run_card", "(deck_positions IS NULL) = (deck_copies IS NULL)"): (
        "copies_without_positions"
    ),
    (
        "score_run_card",
        "deck_positions IS NULL OR (cardinality(deck_positions) = deck_count AND "
        "cardinality(deck_copies) = deck_count)",
    ): "deck_positions_short",
    ("score_run_method", "method_id ~ '^[a-z0-9][a-z0-9-]*$'"): "bad_method_id",
    ("score_run_method", "method_version <> ''"): "blank_method_version",
    ("score_run_method", "method_config_hash ~ '^[0-9a-f]{64}$'"): "bad_config_hash",
    ("score_run_method", "label <> ''"): "blank_method_label",
    ("score_run_method", "description <> ''"): "blank_method_description",
    ("score_run_method", "cardinality(outputs) > 0"): "no_outputs",
    ("card_score", "output <> ''"): "blank_output_name",
    (
        "card_score",
        "value IS NULL OR (value > '-Infinity'::float8 AND value < 'Infinity'::float8)",
    ): ("infinite_score_value", "nan_score_value"),
    ("card_score_input", "input_name <> ''"): "blank_input_name",
    (
        "card_score_input",
        "value IS NULL OR (value > '-Infinity'::float8 AND value < 'Infinity'::float8)",
    ): "infinite_input_value",
    ("score_publication_attempt", "state IN ('running','succeeded','failed')"): PUBLICATION,
    ("score_publication_attempt", "(state = 'running') = (finished_at IS NULL)"): PUBLICATION,
    ("score_run_card_archetype", "position BETWEEN 1 AND 3"): "four_top_archetypes",
    ("score_run_card_archetype", "label <> ''"): "blank_top_archetype_label",
    ("score_run_card_archetype", "deck_count > 0"): "zero_top_archetype_decks",
    ("score_run_archetype", "label <> ''"): "blank_archetype_core_label",
    ("score_run_archetype", "deck_count > 0"): "zero_archetype_core_decks",
    ("score_run_archetype", "event_count IS NULL OR event_count BETWEEN 1 AND deck_count"): (
        "zero_archetype_events",
        "archetype_events_past_decks",
    ),
    ("score_run_archetype", "top_cut_count IS NULL OR top_cut_count >= 0"): (
        "negative_archetype_cuts"
    ),
    (
        "score_run_archetype",
        "top_cut_known_decks IS NULL OR top_cut_known_decks BETWEEN 0 AND deck_count",
    ): "archetype_known_cuts_past_decks",
    ("score_run_archetype", "record_decks IS NULL OR record_decks BETWEEN 0 AND deck_count"): (
        "archetype_record_past_decks"
    ),
    ("score_run_archetype", "record_wins IS NULL OR record_wins >= 0"): "negative_archetype_wins",
    ("score_run_archetype", "record_losses IS NULL OR record_losses >= 0"): (
        "negative_archetype_wins"
    ),
    ("score_run_archetype", "record_draws IS NULL OR record_draws >= 0"): (
        "negative_archetype_wins"
    ),
    ("score_run_archetype", "win_rate IS NULL OR win_rate BETWEEN 0 AND 1"): (
        "archetype_win_rate_above_one"
    ),
    ("score_run_archetype", "win_rate_delta IS NULL OR win_rate_delta BETWEEN -1 AND 1"): (
        "archetype_delta_out_of_range"
    ),
    ("score_run_archetype", "win_rate_ci95 IS NULL OR win_rate_ci95 BETWEEN 0 AND 1"): (
        "archetype_ci95_out_of_range"
    ),
    ("score_run_archetype", "top_cut_lift IS NULL OR top_cut_lift >= 0"): (
        "archetype_negative_lift"
    ),
    ("score_run_archetype", "share_delta IS NULL OR share_delta BETWEEN -1 AND 1"): (
        "archetype_share_delta_out_of_range"
    ),
    ("score_run_archetype", "series_decks IS NULL OR cardinality(series_decks) = 12"): (
        "archetype_short_series"
    ),
    (
        "score_run_archetype",
        "(record_decks IS NULL) = (record_wins IS NULL) AND (record_wins IS NULL) = "
        "(record_losses IS NULL) AND (record_losses IS NULL) = (record_draws IS NULL) AND "
        "(record_draws IS NULL) = (event_count IS NULL) AND (event_count IS NULL) = "
        "(top_cut_known_decks IS NULL) AND (top_cut_known_decks IS NULL) = (commanders IS NULL) "
        "AND (commanders IS NULL) = (series_decks IS NULL)",
    ): "half_an_archetype",
    ("score_run_archetype", "top_cut_count IS NULL OR top_cut_known_decks > 0"): (
        "archetype_cut_without_results"
    ),
    (
        "score_run_archetype",
        "win_rate IS NULL OR record_wins + record_losses + record_draws > 0",
    ): "archetype_win_rate_without_games",
    ("score_run_deck", "position >= 0"): DERIVED,
    ("score_run_deck", "source_deck_id <> ''"): "blank_deck_id",
    ("score_run_deck", "source_event_id <> ''"): "blank_deck_event",
    ("score_run_deck", "event_name <> ''"): "blank_event_name",
    ("score_run_deck", "event_url ~ '^https://\\S+$'"): "plain_event_url",
    ("score_run_deck", "players > 0"): "zero_event_players",
    ("score_run_deck", "archetype_label <> ''"): "blank_deck_archetype",
    ("score_run_deck", "final_rank > 0"): "zero_final_rank",
    ("score_run_deck", "record_wins >= 0"): "negative_deck_record",
    ("score_run_deck", "record_losses >= 0"): "negative_deck_record",
    ("score_run_deck", "record_draws >= 0"): "negative_deck_record",
    (
        "score_run_deck",
        "(record_wins IS NULL) = (record_losses IS NULL) AND (record_losses IS NULL) = "
        "(record_draws IS NULL)",
    ): "partial_deck_record",
    ("score_run_deck", "mainboard_copies IS NULL OR 1 <= ALL(mainboard_copies)"): (
        "zero_deck_copies"
    ),
    ("score_run_deck", "sideboard_names IS NULL OR '' <> ALL(sideboard_names)"): (
        "blank_sideboard_name"
    ),
    ("score_run_deck", "sideboard_copies IS NULL OR 1 <= ALL(sideboard_copies)"): (
        "zero_sideboard_copies"
    ),
    (
        "score_run_deck",
        "(mainboard IS NULL) = (mainboard_copies IS NULL) AND (mainboard IS NULL) = "
        "(commanders IS NULL)",
    ): "commanders_without_sideboard",
    (
        "score_run_deck",
        "mainboard IS NULL OR (cardinality(mainboard) > 0 AND cardinality(mainboard_copies) = "
        "cardinality(mainboard) AND commanders <@ mainboard)",
    ): "commander_outside_its_deck",
    (
        "score_run_deck",
        "(sideboard IS NULL) = (sideboard_names IS NULL) AND (sideboard IS NULL) = "
        "(sideboard_copies IS NULL)",
    ): DERIVED,
    (
        "score_run_deck",
        "sideboard IS NULL OR (mainboard IS NOT NULL AND cardinality(sideboard_names) = "
        "cardinality(sideboard) AND cardinality(sideboard_copies) = cardinality(sideboard))",
    ): DERIVED,
}


def test_every_database_check_is_accounted_for() -> None:
    checks = database_checks()

    unmapped = sorted(set(checks) - set(COVERAGE))
    stale = sorted(set(COVERAGE) - set(checks))
    assert not unmapped, f"CHECKs without a file-level mirror: {unmapped}"
    assert not stale, f"COVERAGE names CHECKs no migration has: {stale}"


def mirrors() -> set[str]:
    """Every mutation name COVERAGE points at; a CHECK may need one per clause."""

    return {name for how in COVERAGE.values() for name in ((how,) if isinstance(how, str) else how)}


def test_every_mapping_names_a_mutation_or_a_reason() -> None:
    reasons = {PUBLICATION, DERIVED, SUPERSEDED}

    unknown = sorted(mirrors() - set(MUTATIONS) - reasons)
    assert unknown == []
    assert set(MUTATIONS) <= mirrors(), "every mutation mirrors a CHECK"


@pytest.mark.parametrize("name", sorted(mirrors() & set(MUTATIONS)))
def test_the_python_side_rejects_what_each_check_rejects(document, name) -> None:
    broken = copy.deepcopy(document)
    MUTATIONS[name](broken)

    with pytest.raises((ValueError, ValidationError)):
        validate_score_run(broken)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("window_ends_before_it_starts", "window must end after it starts"),
        ("events_past_decks", "events or known top cuts exceed the card's decks"),
        ("known_cuts_past_decks", "events or known top cuts exceed the card's decks"),
        ("cuts_past_known_decks", "top cuts exceed the decks with a known result"),
        ("labelled_below_archetype_decks", "labelled decks must lie between"),
        ("labelled_past_decks", "labelled decks must lie between"),
        ("infinite_score_value", "must be finite"),
        ("nan_score_value", "must be finite"),
        ("infinite_input_value", "must be finite"),
    ],
)
def test_the_checks_the_schema_cannot_express_name_their_rule(document, name, message) -> None:
    broken = copy.deepcopy(document)
    MUTATIONS[name](broken)

    with pytest.raises(ValueError, match=message):
        validate_score_run(broken)


def test_an_overall_run_rejects_non_finite_scores(document, tmp_path) -> None:
    run_file = write_score_run(document, tmp_path / "runs")
    overall = json.loads(score_overall([run_file], tmp_path / "overall").read_bytes())
    validate_overall_run(overall)
    values = overall["runs"][0]["scores"][0]["values"]
    values[next(iter(values))] = float("nan")

    with pytest.raises(ValueError, match="must be finite"):
        validate_overall_run(overall)
