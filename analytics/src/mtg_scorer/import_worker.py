"""Durable PostgreSQL queue consumer. Run independently from the HTTP service."""

import argparse
import json
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from mtg_scorer.ingest.scryfall import ScryfallSnapshot, download_default_cards_snapshot
from mtg_scorer.normalize.catalog import SCHEMA_VERSION
from mtg_scorer.publish.bulk import PARSER_VERSION, bulk_identity, export_bulk_catalog
from mtg_scorer.publish.postgres import publish_catalog

LOG = logging.getLogger(__name__)
WORKER_LOCK = 724603


def run_once(dsn: str, data_dir: Path, *, download=download_default_cards_snapshot) -> bool:
    """Claim at most one job. Session ownership also fences a disconnected worker.

    Each stage write and the pre-promotion callback use the lock-owning connection.
    A dead connection cannot continue promotion after another worker recovers it.
    """
    with psycopg.connect(dsn, autocommit=True) as connection:
        locked = connection.execute("SELECT pg_try_advisory_lock(%s)", (WORKER_LOCK,)).fetchone()
        if not (locked and locked[0]):
            return False
        try:
            connection.execute("SELECT catalog.recover_catalog_import()")
            job = connection.execute(
                "UPDATE catalog.catalog_import_job SET state='running',stage='source',"
                "started_at=clock_timestamp(),updated_at=clock_timestamp(),"
                "parser_version=%s,schema_version=%s WHERE state='queued' RETURNING job_id",
                (PARSER_VERSION, SCHEMA_VERSION),
            ).fetchone()
            if job is None:
                return False
            job_id = job[0]

            def update(stage, **fields):
                from psycopg import sql

                assignments: list[sql.Composable] = [
                    sql.SQL("stage=%s"),
                    sql.SQL("updated_at=clock_timestamp()"),
                ]
                values = [stage]
                for key, value in fields.items():
                    assignments.append(sql.SQL("{}=%s").format(sql.Identifier(key)))
                    values.append(Jsonb(value) if isinstance(value, dict) else value)
                changed = connection.execute(
                    sql.SQL(
                        "UPDATE catalog.catalog_import_job SET {} "
                        "WHERE job_id=%s AND state='running'"
                    ).format(sql.SQL(",").join(assignments)),
                    [*values, job_id],
                ).rowcount
                if changed != 1:
                    raise RuntimeError("import ownership lost")

            try:
                source = download(data_dir / "raw" / "scryfall")
                identity = bulk_identity(
                    json.loads(source.manifest_file.read_bytes()), PARSER_VERSION
                )
                update(
                    "normalizing",
                    source_snapshot_id=source.snapshot_id,
                    catalog_snapshot_id=identity,
                )
                published = connection.execute(
                    "SELECT manifest FROM catalog.catalog_snapshot "
                    "WHERE catalog_snapshot_id=%s AND state='published'",
                    (identity,),
                ).fetchone()
                if published:
                    manifest = published[0]
                    result = "already_published"
                else:
                    artifact = export_bulk_catalog(
                        source.raw_file.parent,
                        data_dir / "catalog",
                        before_validate=lambda manifest: update(
                            "validating",
                            row_counts=manifest["row_counts"],
                            excluded_record_counts=manifest["excluded_record_counts"],
                        ),
                    )
                    manifest = json.loads((artifact / "manifest.json").read_bytes())
                    # The existing publisher validates, takes its own publication lock,
                    # loads transactionally, and rechecks bytes before promotion.
                    result = publish_catalog(
                        artifact,
                        source.raw_file.parent,
                        dsn,
                        before_promote=lambda _: update("promoting"),
                        before_load=lambda: update("publishing"),
                        connection=connection,
                    )["state"]
                update(
                    "complete",
                    row_counts=manifest["row_counts"],
                    excluded_record_counts=manifest["excluded_record_counts"],
                    result=result,
                )
                connection.execute(
                    "UPDATE catalog.catalog_import_job SET state='succeeded',"
                    "finished_at=clock_timestamp(),updated_at=clock_timestamp() WHERE job_id=%s",
                    (job_id,),
                )
                LOG.info("import succeeded job=%s result=%s snapshot=%s", job_id, result, identity)
            except Exception:
                LOG.exception("import failed job=%s", job_id)
                if not connection.closed and not connection.broken:
                    connection.execute(
                        "UPDATE catalog.catalog_import_job SET state='failed',"
                        "error_code='import_failed',finished_at=clock_timestamp(),"
                        "updated_at=clock_timestamp() WHERE job_id=%s",
                        (job_id,),
                    )
            return True
        finally:
            if not connection.closed and not connection.broken:
                connection.execute("SELECT pg_advisory_unlock(%s)", (WORKER_LOCK,))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(".local/catalog-imports"))
    parser.add_argument("--once", action="store_true", help="Process one queued job and exit")
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Rebuild a retained raw snapshot instead of checking the current Scryfall metadata",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    dsn = os.environ["CATALOG_PUBLISH_DSN"]
    download: Callable[[Path], ScryfallSnapshot] = download_default_cards_snapshot
    if args.source_dir:
        from mtg_scorer.ingest.scryfall import _snapshot_from_manifest
        from mtg_scorer.publish.bulk import bulk_source

        def rebuild_from_source(_raw_root: Path) -> ScryfallSnapshot:
            source_bytes, _ = bulk_source(args.source_dir)
            manifest = json.loads(source_bytes)
            return _snapshot_from_manifest(
                manifest, args.source_dir / manifest["raw_file"], args.source_dir / "manifest.json"
            )

        download = rebuild_from_source

    while True:
        run_once(dsn, args.data_dir, download=download)
        if args.once:
            return
        time.sleep(2)


if __name__ == "__main__":
    main()
