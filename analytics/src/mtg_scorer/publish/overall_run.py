"""Overall-run files: every format's run combined into one overall grade per card.

The overall run is published like a format's run under the format name "Overall",
so it has its own identity, history and active pointer. Its identity hashes the
component runs, which already hash everything that determined their results, plus
the overall method's version and configuration.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..scoring.overall import FormatGrades, OverallMethod
from .artifact import canonical_bytes
from .score_run import write_score_run
from .score_validation import validate_overall_run, validate_score_run

SCHEMA_VERSION = "overall-run-file-v1"
FORMAT_NAME = "Overall"
POPULATION_RULE = "cards-graded-in-any-format-v1"


def _one(values: Iterable[str], what: str) -> str:
    distinct = sorted(set(values))
    if len(distinct) != 1:
        raise ValueError(f"components must share one {what}; got {distinct}")
    return distinct[0]


def _versions(values: Iterable[str]) -> str:
    """Components may come from different code versions; each run id pins its own, so the
    overall run records them all."""

    return "+".join(sorted(set(values)))


def _sum(cards: Sequence[dict[str, Any]], key: str) -> int:
    return sum(card[key] for card in cards)


def _format(document: dict[str, Any]) -> str:
    return document["cohort"]["rules"]["format_name"]


def _pooled_card(oracle_id: str, entries: list[tuple[dict, dict]]) -> dict[str, Any]:
    """Pool one card's usage over the formats that graded it.

    Counts add up. Win rates are not comparable between one-on-one and multiplayer
    formats, so only each format's gap to its own field is pooled, weighted by games.
    Top-cut lift becomes top cuts made over the top cuts the field's rate expects.
    """

    cards = [card for card, _ in entries]
    games = 0
    gap = 0.0
    made = 0
    expected = 0.0
    for card, component in entries:
        record = card["record"]
        played = record["wins"] + record["losses"] + record["draws"]
        delta = card["performance"]["win_rate_delta"]
        if played and delta is not None:
            games += played
            gap += delta * played
        field_rate = component["cohort"]["performance"]["top_cut_rate"]
        if card["top_cut_count"] is not None and field_rate:
            made += card["top_cut_count"]
            expected += card["top_cut_known_decks"] * field_rate
    known = _sum(cards, "top_cut_known_decks")
    return {
        "oracle_id": oracle_id,
        "name": cards[0]["name"],
        "scored": True,
        "deck_count": _sum(cards, "deck_count"),
        "event_count": _sum(cards, "event_count"),
        "top_cut_count": (sum(card["top_cut_count"] or 0 for card in cards) if known else None),
        "top_cut_known_decks": known,
        "archetype": {"label": None, "deck_count": 0, "labelled_deck_count": 0},
        "archetypes": {"distinct": None, "top": []},
        "mainboard_copies": _sum(cards, "mainboard_copies"),
        "record": {
            key: sum(card["record"][key] for card in cards)
            for key in ("decks", "wins", "losses", "draws")
        },
        "performance": {
            "win_rate": None,
            "win_rate_delta": round(gap / games, 4) if games else None,
            "win_rate_ci95": None,
            "top_cut_lift": round(made / expected, 4) if expected else None,
            "share_delta": None,
        },
        "series": None,
    }


def build_overall_run(
    components: Sequence[dict[str, Any]], method: OverallMethod | None = None
) -> dict[str, Any]:
    """Combine score-run v2 documents, one per format, into an overall run.

    Each component must hold the method the overall grade combines. A component
    without decklists adds nothing and is left out.
    """

    method = method or OverallMethod()
    config = method.config
    graded: list[tuple[dict[str, Any], dict[str, float]]] = []
    for document in components:
        validate_score_run(document)
        run = next((r for r in document["runs"] if r["method_id"] == config.component_method), None)
        if run is None:
            raise ValueError(f"{document['score_run_id']} has no {config.component_method} scores")
        grades = {
            score["card_id"]: score["values"][config.component_output]
            for score in run["scores"]
            if score["values"].get(config.component_output) is not None
        }
        if document["cohort"]["totals"]["decks"] and grades:
            graded.append((document, grades))
    if not graded:
        raise ValueError("no component has graded cards")
    graded.sort(key=lambda item: _format(item[0]))
    formats = [_format(document) for document, _ in graded]
    if len(set(formats)) != len(formats) or FORMAT_NAME in formats:
        raise ValueError(f"each format can be combined only once, and not {FORMAT_NAME!r}")
    documents = [document for document, _ in graded]
    source = _one((d["source"] for d in documents), "source")

    scores = method.score(
        [
            FormatGrades(_format(document), document["cohort"]["totals"]["decks"], grades)
            for document, grades in graded
        ]
    )
    usage: dict[str, list[tuple[dict, dict]]] = {}
    per_format: dict[str, dict[str, float]] = {}
    for document, grades in graded:
        for card in document["cards"]:
            if card["oracle_id"] in grades:
                usage.setdefault(card["oracle_id"], []).append((card, document))
                per_format.setdefault(card["oracle_id"], {})[_format(document)] = grades[
                    card["oracle_id"]
                ]

    component_rows = [
        {
            "format_name": _format(document),
            "score_run_id": document["score_run_id"],
            "method_id": config.component_method,
            "output": config.component_output,
            "window_starts_on": document["cohort"]["rules"]["starts_on"],
            "window_ends_before": document["cohort"]["rules"]["ends_before"],
            "players_per_game": document["cohort"]["rules"]["players_per_game"],
            "decks": document["cohort"]["totals"]["decks"],
            "graded_cards": len(grades),
            "weight": round(method.weight(document["cohort"]["totals"]["decks"]), 4),
        }
        for document, grades in graded
    ]
    method_identities = [[method.method_id, method.version, method.config_hash]]
    identity = {
        "schema_version": SCHEMA_VERSION,
        "format_name": FORMAT_NAME,
        "source": source,
        "components": [[row["format_name"], row["score_run_id"]] for row in component_rows],
        "population_rule": POPULATION_RULE,
        "method_identities": method_identities,
    }
    totals = {
        key: sum(d["cohort"]["totals"][key] for d in documents)
        for key in ("events", "players", "decks", "top_cut_decks", "matches")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "score_run_id": "scores-" + sha256(canonical_bytes(identity)).hexdigest(),
        "format_name": FORMAT_NAME,
        "window_starts_on": min(row["window_starts_on"] for row in component_rows),
        "window_ends_before": max(row["window_ends_before"] for row in component_rows),
        "dataset_snapshot_id": "components-"
        + sha256(canonical_bytes(sorted(d["dataset_snapshot_id"] for d in documents))).hexdigest(),
        "parser_version": _versions(d["parser_version"] for d in documents),
        "feature_pipeline_version": _versions(d["feature_pipeline_version"] for d in documents),
        "cohort_rules_hash": sha256(
            canonical_bytes([[_format(d), d["cohort_rules_hash"]] for d in documents])
        ).hexdigest(),
        "population_rule": POPULATION_RULE,
        "method_identities": method_identities,
        "source": source,
        "attribution": _one((d["attribution"] for d in documents), "attribution"),
        "components": component_rows,
        "totals": {"formats": len(component_rows), **totals},
        "population": {"rule": POPULATION_RULE, "scored_cards": len(scores), "excluded_cards": []},
        "cards": [
            {
                **_pooled_card(score.card_id, usage[score.card_id]),
                "formats": per_format[score.card_id],
            }
            for score in scores
        ],
        "runs": [
            {
                "method_id": method.method_id,
                "method_version": method.version,
                "method_config_hash": method.config_hash,
                "label": method.label,
                "description": method.description,
                "outputs": list(method.outputs),
                "scores": [
                    {
                        "card_id": score.card_id,
                        "values": dict(score.values),
                        "inputs": dict(score.inputs),
                    }
                    for score in scores
                ],
            }
        ],
    }


def score_overall(run_files: Sequence[Path], output_root: Path) -> Path:
    """Read one score-run file per format, combine them and write the overall run file."""

    document = build_overall_run([json.loads(path.read_bytes()) for path in run_files])
    return write_score_run(document, output_root, validate=validate_overall_run)


def active_run_files(dsn: str, runs_dir: Path) -> list[Path]:
    """The file of every format's active run, except the overall run itself."""

    import psycopg

    with psycopg.connect(dsn) as connection:
        ids = [
            row[0]
            for row in connection.execute(
                "SELECT score_run_id FROM scores.active_score_run WHERE format_name<>%s"
                " ORDER BY format_name,source",
                (FORMAT_NAME,),
            )
        ]
    files = [runs_dir / f"{run_id}.json" for run_id in ids]
    missing = [path.name for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"active runs missing from {runs_dir}: {', '.join(missing)}")
    return files
