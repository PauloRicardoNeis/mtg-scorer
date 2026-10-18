"""Versioned score-run files: one cohort's card usage plus every method's scores.

A run's identity hashes everything that determines its results: the dataset
snapshot, parser, feature pipeline, cohort rules, scoring population and each
method's version and configuration. The same identity must always reproduce the
same file, so an existing file with different results is an error, never overwritten.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..ingest.topdeck import PARSER_VERSION, SOURCE, TopDeckSnapshot, read_saved_responses
from ..scoring import SCORE_METHODS, ScoreContext, ScoreMethod, ScoringInput
from ..tournament_features import (
    FEATURE_PIPELINE_VERSION,
    Cohort,
    CohortRules,
    ExcludedEvent,
    card_features,
    card_usage,
    select_cohort,
)
from .artifact import canonical_bytes

SCHEMA_VERSION = "score-run-file-v1"
ATTRIBUTION = "Data provided by TopDeck.gg (https://topdeck.gg)"
# Basic lands would otherwise lead every volume ranking.
POPULATION_RULE = "mainboard-cards-without-basic-lands-v1"
BASIC_LANDS = frozenset(
    {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
    | {f"Snow-Covered {name}" for name in ("Plains", "Island", "Swamp", "Mountain", "Forest")}
    | {"Snow-Covered Wastes"}
)


def load_cohort_rules(path: Path) -> CohortRules:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return CohortRules(
        version=raw["version"],
        format_name=raw["format_name"],
        starts_on=raw["starts_on"],
        ends_before=raw["ends_before"],
        min_decklist_coverage=raw["min_decklist_coverage"],
        excluded_events=tuple(
            ExcludedEvent(event["source_event_id"], event["reason"])
            for event in raw.get("excluded_events", ())
        ),
    )


def build_score_run(
    snapshot: TopDeckSnapshot,
    rules: CohortRules,
    methods: Iterable[ScoreMethod] = SCORE_METHODS,
) -> dict[str, Any]:
    """Select the cohort, compute card usage and run every method over it."""

    methods = tuple(methods)
    cohort = select_cohort(
        snapshot.tournaments,
        snapshot.decks,
        snapshot.standings,
        rules,
        incomplete_decks=snapshot.incomplete_mainboards,
    )
    usage = card_usage(cohort)
    population = [card for card in usage if card.name not in BASIC_LANDS]
    inputs = [ScoringInput(card.oracle_id, card_features(card, cohort)) for card in population]
    context = ScoreContext(snapshot.dataset_snapshot_id, FEATURE_PIPELINE_VERSION)
    identity = {
        "dataset_snapshot_id": snapshot.dataset_snapshot_id,
        "parser_version": PARSER_VERSION,
        "feature_pipeline_version": FEATURE_PIPELINE_VERSION,
        "cohort_rules_hash": rules.fingerprint,
        "population_rule": POPULATION_RULE,
        "method_identities": [[m.method_id, m.version, m.config_hash] for m in methods],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "score_run_id": "scores-" + sha256(canonical_bytes(identity)).hexdigest(),
        **identity,
        "source": SOURCE,
        "attribution": ATTRIBUTION,
        "raw_files": [
            {
                "name": raw.name,
                "sha256": raw.sha256,
                "bytes": raw.bytes,
                "retrieved_at": raw.retrieved_at.isoformat(),
                "retrieved_at_basis": raw.retrieved_at_basis,
            }
            for raw in snapshot.raw_files
        ],
        "cohort": _cohort_summary(cohort, snapshot),
        "population": {
            "rule": POPULATION_RULE,
            "scored_cards": len(population),
            "excluded_cards": sorted(card.name for card in usage if card.name in BASIC_LANDS),
        },
        "cards": [
            {
                "oracle_id": card.oracle_id,
                "name": card.name,
                "scored": card.name not in BASIC_LANDS,
                "deck_count": card.deck_count,
                "event_count": card.event_count,
                "top_cut_count": card.top_cut_count,
                "top_cut_known_decks": card.top_cut_known_decks,
                "archetype": {
                    "label": card.archetype_label,
                    "deck_count": card.archetype_deck_count,
                    "labelled_deck_count": card.labelled_deck_count,
                },
            }
            for card in usage
        ],
        "runs": [_run(method, inputs, context) for method in methods],
    }


def _cohort_summary(cohort: Cohort, snapshot: TopDeckSnapshot) -> dict[str, Any]:
    made_cut = {s.source_deck_id: s.made_top_cut for s in cohort.standings}
    return {
        "rules": {**_rules_dict(cohort.rules), "hash": cohort.rules.fingerprint},
        "events": [
            {
                "source_event_id": event.source_event_id,
                "occurred_on": event.occurred_on.isoformat(),
                "players": event.player_count,
                "decklists": event.coverage.decklists.observed_count,
                "top_cut_size": event.top_cut_size,
                "top_cut_basis": snapshot.top_cut_basis[event.source_event_id],
            }
            for event in cohort.tournaments
        ],
        "excluded_events": [
            {"source_event_id": event.source_event_id, "reason": event.reason}
            for event in cohort.excluded_events
        ],
        "totals": {
            "events": len(cohort.tournaments),
            "players": sum(event.player_count or 0 for event in cohort.tournaments),
            "decks": len(cohort.decks),
            "incomplete_decks_excluded": cohort.incomplete_deck_count,
            "top_cut_players": sum(result is True for result in made_cut.values()),
            "top_cut_decks": sum(
                made_cut.get(deck.source_deck_id) is True for deck in cohort.decks
            ),
            "quarantined_card_lines_in_source": snapshot.quarantined_card_lines,
        },
    }


def _rules_dict(rules: CohortRules) -> dict[str, Any]:
    return {
        "version": rules.version,
        "format_name": rules.format_name,
        "starts_on": rules.starts_on,
        "ends_before": rules.ends_before,
        "min_decklist_coverage": rules.min_decklist_coverage,
        "excluded_events": [
            {"source_event_id": event.source_event_id, "reason": event.reason}
            for event in rules.excluded_events
        ],
    }


def _run(method: ScoreMethod, inputs: list[ScoringInput], context: ScoreContext) -> dict[str, Any]:
    run = method.score(inputs, context)
    return {
        "method_id": run.method_id,
        "method_version": run.method_version,
        "method_config_hash": run.method_config_hash,
        "label": method.label,
        "description": method.description,
        "outputs": list(method.outputs),
        "scores": [
            {"card_id": score.card_id, "values": dict(score.values), "inputs": dict(score.inputs)}
            for score in run.scores
        ],
    }


def write_score_run(document: dict[str, Any], output_root: Path) -> Path:
    """Write ``<score_run_id>.json`` atomically; an identical rerun returns the same file."""

    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / f"{document['score_run_id']}.json"
    if destination.exists():
        existing = json.loads(destination.read_bytes())
        if _results(existing) != _results(json.loads(canonical_bytes(document))):
            raise ValueError(
                f"{destination.name} already holds different results for the same identity; "
                "bump the version of whatever changed"
            )
        return destination
    handle, temporary = tempfile.mkstemp(prefix=".score-run-", suffix=".json", dir=output_root)
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(canonical_bytes(document))
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination


def _results(document: dict[str, Any]) -> dict[str, Any]:
    # Retrieval times may legitimately differ between copies of the same responses.
    return {key: value for key, value in document.items() if key != "raw_files"}


def score_topdeck(source_dir: Path, cohort_file: Path, output_root: Path) -> Path:
    """Read saved TopDeck responses, score the cohort and write the run file."""

    document = build_score_run(read_saved_responses(source_dir), load_cohort_rules(cohort_file))
    return write_score_run(document, output_root)
