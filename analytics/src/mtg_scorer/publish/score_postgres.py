"""Publish a score-run file to PostgreSQL; one connection holds the lock until promotion."""

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

from .score_run import results_sha256
from .score_validation import validate_score_run

LOGGER = logging.getLogger(__name__)
LOCK_ID = 724603
# Children before parents, so a retry can clear unpublished staging rows.
STAGING_TABLES = ("card_score_input", "card_score", "score_run_method", "score_run_card")


def score_run_header(document: dict[str, Any]) -> dict[str, Any]:
    """Everything about a run except its per-card rows, plus counts to verify the rows."""

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
        "row_counts": {
            "cards": len(document["cards"]),
            "methods": len(document["runs"]),
            "scores": sum(len(s["values"]) for run in document["runs"] for s in run["scores"]),
            "inputs": sum(len(s["inputs"]) for run in document["runs"] for s in run["scores"]),
        },
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
        "labelled_deck_count) FROM STDIN"
    ) as copy:
        for card in document["cards"]:
            archetype = card["archetype"]
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


def publish_score_run(
    run_file: Path,
    dsn: str,
    *,
    before_promote: Callable[[str], None] | None = None,
    connection: psycopg.Connection | None = None,
) -> dict[str, str]:
    """Validate the file before entering the database; failed attempts remain diagnosable."""

    document = json.loads(run_file.read_bytes())
    validate_score_run(document)
    header = score_run_header(document)
    run_id = header["score_run_id"]
    attempt = uuid4()
    with (
        nullcontext(connection) if connection else psycopg.connect(dsn, autocommit=True)
    ) as connection:
        connection.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            previous = connection.execute(
                "SELECT score_run_id FROM scores.active_score_run "
                "WHERE source=%s AND format_name=%s",
                (header["source"], header["format_name"]),
            ).fetchone()
            expected = previous[0] if previous else None
            with connection.transaction():
                started = connection.execute(
                    "SELECT scores.begin_score_publication(%s,%s,%s)",
                    (Jsonb(header), attempt, expected),
                ).fetchone()[0]
            if not started:
                return {"score_run_id": run_id, "state": "already_published"}
            LOGGER.info("score publication started run=%s attempt=%s", run_id, attempt)
            try:
                with connection.transaction():
                    _load_rows(connection, document)
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
