"""One connection owns the publication lock from attempt creation through promotion."""

from __future__ import annotations

import logging
from collections.abc import Callable
from hashlib import file_digest
from itertools import chain
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from mtg_scorer.publish.stream import rows, verify_publication

LOGGER = logging.getLogger(__name__)
LOCK_ID = 724602
TABLES = {
    "cards": "catalog_card",
    "faces": "catalog_face",
    "printings": "catalog_printing",
    "aliases": "catalog_alias",
}


def _load_rows(connection: psycopg.Connection, payload: dict[str, Any], export_file: Path) -> None:
    snapshot = payload["catalog_snapshot_id"]
    # Retry only removes unpublished staging rows, with the representative FK deferred.
    for table in (
        "catalog_printing_image",
        "catalog_alias",
        "catalog_face",
        "catalog_printing",
        "catalog_card",
    ):
        connection.execute(
            sql.SQL("DELETE FROM catalog.{} WHERE catalog_snapshot_id=%s").format(
                sql.Identifier(table)
            ),
            (snapshot,),
        )
    for label, table in TABLES.items():
        records = rows(export_file, label)
        first = next(records, None)
        if first is None:
            continue
        columns = [key for key in first if key != "images"]
        statement = sql.SQL("INSERT INTO catalog.{} ({}) VALUES ({})").format(
            sql.Identifier(table),
            sql.SQL(",").join(map(sql.Identifier, ["catalog_snapshot_id", *columns])),
            sql.SQL(",").join(sql.Placeholder() for _ in range(len(columns) + 1)),
        )
        with connection.cursor() as cursor:
            cursor.executemany(
                statement,
                ((snapshot, *(row[key] for key in columns)) for row in chain([first], records)),
            )
    for printing in rows(export_file, "printings"):
        for image in printing["images"]:
            connection.execute(
                "INSERT INTO catalog.catalog_printing_image VALUES(%s,%s,%s,%s,%s)",
                (
                    snapshot,
                    printing["scryfall_id"],
                    -1 if image["face_index"] is None else image["face_index"],
                    image["source_uri"],
                    image["artist"],
                ),
            )


def publish_catalog(
    directory: Path,
    source_dir: Path,
    dsn: str,
    *,
    before_promote: Callable[[str], None] | None = None,
) -> dict[str, str]:
    """Validate external bytes before entering the database; failed attempts remain diagnosable."""
    payload, manifest = verify_publication(directory, source_dir)
    attempt = uuid4()
    snapshot = payload["catalog_snapshot_id"]
    header = {key: value for key, value in payload.items() if key not in TABLES}
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            previous = connection.execute(
                "SELECT catalog_snapshot_id FROM catalog.active_catalog"
            ).fetchone()
            expected = previous[0] if previous else None
            with connection.transaction():
                started = connection.execute(
                    "SELECT catalog.begin_publication(%s,%s,%s,%s)",
                    (Jsonb(header), Jsonb(manifest), attempt, expected),
                ).fetchone()[0]
            if not started:
                return {"catalog_snapshot_id": snapshot, "state": "already_published"}
            LOGGER.info("catalog publication started snapshot=%s attempt=%s", snapshot, attempt)
            try:
                with connection.transaction():
                    _load_rows(connection, payload, directory / "catalog.json")
                    with (directory / "catalog.json").open("rb") as source:
                        if file_digest(source, "sha256").hexdigest() != manifest["export_sha256"]:
                            raise ValueError("export changed while loading")
                    if before_promote is not None:
                        before_promote(snapshot)
                    connection.execute("SELECT catalog.promote_publication(%s)", (attempt,))
            except Exception:
                # Log the cause locally, but persist only a stable code, never credentials/SQL.
                LOGGER.exception(
                    "catalog publication failed snapshot=%s attempt=%s", snapshot, attempt
                )
                connection.execute(
                    "SELECT catalog.fail_publication(%s,'publication_failed')", (attempt,)
                )
                raise
            return {
                "catalog_snapshot_id": snapshot,
                "attempt_id": str(attempt),
                "state": "published",
            }
        finally:
            if not connection.closed and not connection.broken:
                connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


def rollback_catalog(dsn: str, target: str, expected: str) -> None:
    """Guarded pointer rollback never rewrites a retained publication."""
    with psycopg.connect(dsn) as connection:
        connection.execute("SELECT catalog.rollback_catalog(%s,%s)", (target, expected))
