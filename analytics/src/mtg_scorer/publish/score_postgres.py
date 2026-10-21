"""Publish a score-run or overall-run file to PostgreSQL; one connection holds the lock until
promotion."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from .overall_run import SCHEMA_VERSION as OVERALL_SCHEMA_VERSION
from .score_run import results_sha256
from .score_validation import validate_overall_run, validate_score_run

LOGGER = logging.getLogger(__name__)
LOCK_ID = 724603
# Children before parents, so a retry can clear unpublished staging rows.
STAGING_TABLES = (
    "card_score_input",
    "card_score",
    "score_run_card_archetype",
    "score_run_method",
    "score_run_card",
    "score_run_archetype",
    "score_run_deck",
)


def _validate(document: dict[str, Any]) -> None:
    if document.get("schema_version") == OVERALL_SCHEMA_VERSION:
        validate_overall_run(document)
    else:
        validate_score_run(document)


def _row_counts(document: dict[str, Any], archetypes: int) -> dict[str, int]:
    return {
        "cards": len(document["cards"]),
        "methods": len(document["runs"]),
        "scores": sum(len(s["values"]) for run in document["runs"] for s in run["scores"]),
        "inputs": sum(len(s["inputs"]) for run in document["runs"] for s in run["scores"]),
        "card_archetypes": sum(len(card["archetypes"]["top"]) for card in document["cards"]),
        "archetypes": archetypes,
        "decks": len(document.get("decks", ())),
    }


def _overall_header(document: dict[str, Any]) -> dict[str, Any]:
    """An overall run stores its totals where a format's run stores its cohort's, so both
    read the same way; its components say which runs it combined."""

    return {
        **{
            key: document[key]
            for key in (
                "score_run_id",
                "schema_version",
                "source",
                "format_name",
                "window_starts_on",
                "window_ends_before",
                "dataset_snapshot_id",
                "parser_version",
                "feature_pipeline_version",
                "cohort_rules_hash",
                "population_rule",
                "attribution",
            )
        },
        "summary": {
            "cohort": {"totals": document["totals"]},
            "population": document["population"],
            "components": document["components"],
            "method_identities": document["method_identities"],
        },
        "row_counts": _row_counts(document, 0),
        "results_sha256": results_sha256(document),
    }


def score_run_header(document: dict[str, Any]) -> dict[str, Any]:
    """Everything about a run except its per-card rows, plus counts to verify the rows."""

    if document["schema_version"] == OVERALL_SCHEMA_VERSION:
        return _overall_header(document)
    rules = document["cohort"]["rules"]
    return {
        "score_run_id": document["score_run_id"],
        "schema_version": document["schema_version"],
        "source": document["source"],
        "format_name": rules["format_name"],
        "window_starts_on": rules["starts_on"],
        "window_ends_before": rules["ends_before"],
        "dataset_snapshot_id": document["dataset_snapshot_id"],
        "parser_version": document["parser_version"],
        "feature_pipeline_version": document["feature_pipeline_version"],
        "cohort_rules_hash": document["cohort_rules_hash"],
        "population_rule": document["population_rule"],
        "attribution": document["attribution"],
        "summary": {
            "cohort": document["cohort"],
            "population": document["population"],
            "raw_files": document["raw_files"],
            "method_identities": document["method_identities"],
        },
        "row_counts": _row_counts(document, len(document["cohort"]["archetypes"])),
        "results_sha256": results_sha256(document),
    }


def _load_rows(connection: psycopg.Connection, document: dict[str, Any]) -> None:
    run_id = document["score_run_id"]
    for table in STAGING_TABLES:
        connection.execute(
            sql.SQL("DELETE FROM scores.{} WHERE score_run_id=%s").format(sql.Identifier(table)),
            (run_id,),
        )
    with connection.cursor().copy(
        "COPY scores.score_run_card (score_run_id,oracle_id,name,scored,deck_count,event_count,"
        "top_cut_count,top_cut_known_decks,archetype_label,archetype_deck_count,"
        "labelled_deck_count,mainboard_copies,record_decks,record_wins,record_losses,"
        "record_draws,win_rate,win_rate_delta,win_rate_ci95,top_cut_lift,share_delta,"
        "series_decks,archetype_count,deck_positions,deck_copies) FROM STDIN"
    ) as copy:
        for card in document["cards"]:
            archetype = card["archetype"]
            record = card["record"]
            performance = card["performance"]
            copy.write_row(
                (
                    run_id,
                    card["oracle_id"],
                    card["name"],
                    card["scored"],
                    card["deck_count"],
                    card["event_count"],
                    card["top_cut_count"],
                    card["top_cut_known_decks"],
                    archetype["label"],
                    archetype["deck_count"],
                    archetype["labelled_deck_count"],
                    card["mainboard_copies"],
                    record["decks"],
                    record["wins"],
                    record["losses"],
                    record["draws"],
                    performance["win_rate"],
                    performance["win_rate_delta"],
                    performance["win_rate_ci95"],
                    performance["top_cut_lift"],
                    performance["share_delta"],
                    card["series"],
                    card["archetypes"]["distinct"],
                    # Files before feature pipeline card-usage-v7 list no decks.
                    card.get("decks"),
                    card.get("deck_copies"),
                )
            )
    with connection.cursor().copy(
        "COPY scores.score_run_card_archetype (score_run_id,oracle_id,position,label,deck_count)"
        " FROM STDIN"
    ) as copy:
        for card in document["cards"]:
            for position, share in enumerate(card["archetypes"]["top"], start=1):
                copy.write_row(
                    (run_id, card["oracle_id"], position, share["label"], share["deck_count"])
                )
    with connection.cursor().copy(
        "COPY scores.score_run_archetype (score_run_id,label,deck_count,core_cards,commanders,"
        "event_count,top_cut_count,top_cut_known_decks,record_decks,record_wins,record_losses,"
        "record_draws,win_rate,win_rate_delta,win_rate_ci95,top_cut_lift,share_delta,"
        "series_decks) FROM STDIN"
    ) as copy:
        for archetype in document.get("cohort", {}).get("archetypes", ()):
            # Files before feature pipeline card-usage-v5 leave everything past the core NULL.
            record = archetype.get("record", {})
            performance = archetype.get("performance", {})
            copy.write_row(
                (
                    run_id,
                    archetype["label"],
                    archetype["deck_count"],
                    archetype["core_cards"],
                    archetype.get("commanders"),
                    archetype.get("event_count"),
                    archetype.get("top_cut_count"),
                    archetype.get("top_cut_known_decks"),
                    record.get("decks"),
                    record.get("wins"),
                    record.get("losses"),
                    record.get("draws"),
                    performance.get("win_rate"),
                    performance.get("win_rate_delta"),
                    performance.get("win_rate_ci95"),
                    performance.get("top_cut_lift"),
                    performance.get("share_delta"),
                    archetype.get("series"),
                )
            )
    events = {
        event["source_event_id"]: event for event in document.get("cohort", {}).get("events", ())
    }
    decks = document.get("decks", ())
    mainboards = _mainboards(document) if decks and "sideboard" in decks[0] else None
    with connection.cursor().copy(
        "COPY scores.score_run_deck (score_run_id,position,source_deck_id,source_event_id,"
        "event_name,event_url,occurred_on,players,archetype_label,final_rank,made_top_cut,"
        "record_wins,record_losses,record_draws,mainboard,mainboard_copies,commanders,"
        "sideboard,sideboard_names,sideboard_copies) FROM STDIN"
    ) as copy:
        for position, deck in enumerate(decks):
            event = events[deck["source_event_id"]]
            record = deck["record"] or {}
            # Decks before feature pipeline card-usage-v8 state no list of their own.
            main, main_copies = mainboards[position] if mainboards else (None, None)
            sideboard = deck.get("sideboard")
            copy.write_row(
                (
                    run_id,
                    position,
                    deck["source_deck_id"],
                    deck["source_event_id"],
                    event.get("name"),
                    event.get("url"),
                    event["occurred_on"],
                    event["players"],
                    deck["archetype"],
                    deck["final_rank"],
                    deck["made_top_cut"],
                    record.get("wins"),
                    record.get("losses"),
                    record.get("draws"),
                    main,
                    main_copies,
                    deck.get("commanders"),
                    None if sideboard is None else [card["oracle_id"] for card in sideboard],
                    None if sideboard is None else [card["name"] for card in sideboard],
                    None if sideboard is None else [card["copies"] for card in sideboard],
                )
            )
    with connection.cursor().copy(
        "COPY scores.score_run_method (score_run_id,method_id,method_version,method_config_hash,"
        "label,description,outputs) FROM STDIN"
    ) as copy:
        for run in document["runs"]:
            copy.write_row(
                (
                    run_id,
                    run["method_id"],
                    run["method_version"],
                    run["method_config_hash"],
                    run["label"],
                    run["description"],
                    run["outputs"],
                )
            )
    for table, column, key in (
        ("card_score", "output", "values"),
        ("card_score_input", "input_name", "inputs"),
    ):
        statement = sql.SQL(
            "COPY scores.{} (score_run_id,method_id,oracle_id,{},value) FROM STDIN"
        ).format(sql.Identifier(table), sql.Identifier(column))
        with connection.cursor().copy(statement) as copy:
            for run in document["runs"]:
                for score in run["scores"]:
                    for name, value in score[key].items():
                        copy.write_row((run_id, run["method_id"], score["card_id"], name, value))


def _mainboards(document: dict[str, Any]) -> list[tuple[list[str], list[int]]]:
    """Each deck's main deck, by oracle id with its copies, from the cards' deck lists."""

    mainboards: list[tuple[list[str], list[int]]] = [([], []) for _ in document["decks"]]
    for card in document["cards"]:
        for position, copies in zip(card["decks"], card["deck_copies"], strict=True):
            cards, counts = mainboards[position]
            cards.append(card["oracle_id"])
            counts.append(copies)
    return mainboards


def publish_score_run(
    run_file: Path,
    dsn: str,
    *,
    before_promote: Callable[[str], None] | None = None,
    connection: psycopg.Connection | None = None,
) -> dict[str, str]:
    """Validate the file before entering the database; failed attempts remain diagnosable."""

    document = json.loads(run_file.read_bytes())
    _validate(document)
    header = score_run_header(document)
    run_id = header["score_run_id"]
    attempt = uuid4()
    with (
        nullcontext(connection) if connection else psycopg.connect(dsn, autocommit=True)
    ) as connection:  # noqa: PLR1704 -- the context yields the connection it was given
        connection.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            previous = connection.execute(
                "SELECT score_run_id FROM scores.active_score_run "
                "WHERE source=%s AND format_name=%s",
                (header["source"], header["format_name"]),
            ).fetchone()
            expected = previous[0] if previous else None
            with connection.transaction():
                (started,) = connection.execute(
                    "SELECT scores.begin_score_publication(%s,%s,%s)",
                    (Jsonb(header), attempt, expected),
                ).fetchone() or (False,)
            if not started:
                return {"score_run_id": run_id, "state": "already_published"}
            LOGGER.info("score publication started run=%s attempt=%s", run_id, attempt)
            try:
                with connection.transaction():
                    _load_rows(connection, document)
                    # Fresh statistics: a run the planner has never seen is estimated at one
                    # row, which turns promotion checks and the first rankings reads into
                    # nested loops over the whole run.
                    connection.execute(
                        "ANALYZE " + ",".join(f"scores.{table}" for table in STAGING_TABLES)
                    )
                    if before_promote is not None:
                        before_promote(run_id)
                    connection.execute("SELECT scores.promote_score_publication(%s)", (attempt,))
            except Exception:
                # Log the cause locally, but persist only a stable code, never credentials/SQL.
                LOGGER.exception("score publication failed run=%s attempt=%s", run_id, attempt)
                connection.execute(
                    "SELECT scores.fail_score_publication(%s,'publication_failed')", (attempt,)
                )
                raise
            return {"score_run_id": run_id, "attempt_id": str(attempt), "state": "published"}
        finally:
            if not connection.closed and not connection.broken:
                connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


def rollback_score_run(dsn: str, target: str, expected: str) -> None:
    """Point the target's source and format back at an earlier published run."""

    with psycopg.connect(dsn) as connection:
        connection.execute("SELECT scores.rollback_score_run(%s,%s)", (target, expected))
