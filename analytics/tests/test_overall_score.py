"""The overall grade averages per-format grades by evidence, shrunk toward the median."""

import pytest

from mtg_scorer.scoring import FormatGrades, OverallConfig, OverallMethod

METHOD = OverallMethod()


def scores(formats, method=METHOD):
    return {score.card_id: score.values["score"] for score in method.score(formats)}


def test_a_card_proven_in_many_formats_outranks_one_strong_in_a_single_format() -> None:
    result = scores(
        [
            FormatGrades("Modern", 1000, {"staple": 90, "specialist": 95, "filler": 10}),
            FormatGrades("Legacy", 1000, {"staple": 90, "filler": 20}),
            FormatGrades("Pauper", 1000, {"staple": 90, "filler": 30}),
        ]
    )

    assert result["staple"] > result["specialist"] > result["filler"]


def test_a_format_with_few_decklists_barely_moves_a_card() -> None:
    result = scores(
        [
            FormatGrades("Modern", 1000, {"a": 60, "b": 60}),
            FormatGrades("Tiny", 5, {"a": 100}),
            FormatGrades("Large", 5000, {"b": 100}),
        ]
    )

    assert result["b"] > result["a"]


def test_the_overall_grade_is_a_percentile_of_every_graded_card() -> None:
    result = scores([FormatGrades("Modern", 1000, {"a": 10, "b": 50, "c": 90})])

    assert result == {"a": pytest.approx(16.667), "b": 50.0, "c": pytest.approx(83.333)}


def test_inputs_explain_the_blend() -> None:
    (score,) = METHOD.score(
        [FormatGrades("Modern", 250, {"a": 80}), FormatGrades("Legacy", 250, {"a": 60})]
    )

    # Each format counts half; with one format of a median 50: (40 + 30 + 50) / 2.
    assert score.inputs == {"blend": 60.0, "evidence": 1.0, "formats": 2.0}


def test_formats_without_decklists_are_ignored() -> None:
    result = scores([FormatGrades("Modern", 100, {"a": 70}), FormatGrades("Empty", 0, {"b": 90})])

    assert set(result) == {"a"}


def test_a_format_can_be_combined_only_once() -> None:
    with pytest.raises(ValueError, match="only once"):
        METHOD.score([FormatGrades("Modern", 10, {"a": 1}), FormatGrades("Modern", 10, {})])


def test_scoring_is_deterministic_and_ordered_by_card() -> None:
    formats = [FormatGrades("Modern", 100, {"b": 70, "a": 30})]

    assert METHOD.score(formats) == METHOD.score(formats)
    assert [score.card_id for score in METHOD.score(formats)] == ["a", "b"]


def test_a_changed_setting_changes_the_method_identity() -> None:
    changed = OverallMethod(OverallConfig(half_weight_decks=100))

    assert changed.config_hash != METHOD.config_hash
    assert METHOD.version == "overall-grade-v1"


@pytest.mark.parametrize(
    "changes",
    [
        {"version": " "},
        {"component_method": ""},
        {"half_weight_decks": 0},
        {"prior_formats": -1},
        {"prior_score": 101},
    ],
)
def test_invalid_settings_are_rejected(changes) -> None:
    with pytest.raises(ValueError):
        OverallConfig(**changes)
