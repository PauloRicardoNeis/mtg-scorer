"""Score-run files must satisfy the published contract before writing or publishing."""

import copy

import pytest
from jsonschema import ValidationError
from synthetic_topdeck import BOLT, open_event, save, weekly_event

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
    ],
)
def test_relationships_the_schema_cannot_express_are_checked(document, change, message) -> None:
    broken = copy.deepcopy(document)
    change(broken)

    with pytest.raises(ValueError, match=message):
        validate_score_run(broken)
