"""Real PostgreSQL proof; TEST_DATABASE_DSN must name a disposable test database."""

import copy
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from mtg_scorer.publish.artifact import export_catalog, verify_artifact
from mtg_scorer.publish.postgres import publish_catalog, rollback_catalog

SEED = Path(__file__).resolve().parents[1] / "seeds/scryfall-layouts-v1"
DSN = os.environ.get("TEST_DATABASE_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="real PostgreSQL TEST_DATABASE_DSN required")


def role_dsn(role):
    return psycopg.conninfo.make_conninfo(DSN, options=f"-c role={role}")


@pytest.fixture
def publications(tmp_path):
    # Each test gets immutable identities and checks only its own attempts/rows.
    return [
        export_catalog(
            SEED,
            tmp_path,
            selection={
                "kind": "bounded_sample",
                "description": f"Real seed integration test {uuid4()}",
            },
        )
        for _ in range(3)
    ]


def active(connection):
    row = connection.execute("SELECT catalog_snapshot_id FROM catalog.active_catalog").fetchone()
    return row[0] if row else None


def publish(directory, **kwargs):
    return publish_catalog(directory, SEED, role_dsn("catalog_publisher"), **kwargs)


def test_integrity_replay_conflict_permissions_and_pointer_rollback(publications):
    first, second, _ = publications
    result = publish(first)
    old = result["catalog_snapshot_id"]
    assert result["state"] == "published"
    assert publish(first)["state"] == "already_published"
    with psycopg.connect(role_dsn("catalog_reader"), autocommit=True) as reader:
        assert (
            reader.execute(
                "SELECT count(*) FROM catalog.published_catalog_face WHERE catalog_snapshot_id=%s",
                (old,),
            ).fetchone()[0]
            == 10
        )
        for statement in (
            "SELECT * FROM catalog.catalog_card",
            "DELETE FROM catalog.active_catalog",
            "SELECT catalog.rollback_catalog(NULL,NULL)",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                reader.execute(statement)
    payload, manifest = verify_artifact(first, SEED)
    changed = copy.deepcopy(manifest)
    changed["export_sha256"] = "0" * 64
    with psycopg.connect(role_dsn("catalog_publisher"), autocommit=True) as writer:
        with pytest.raises(psycopg.Error, match="snapshot_content_conflict"):
            writer.execute(
                "SELECT catalog.begin_publication(%s,%s,%s,%s)",
                (Jsonb(payload), Jsonb(changed), uuid4(), old),
            )
        with pytest.raises(psycopg.Error, match="snapshot_immutable"):
            writer.execute(
                "UPDATE catalog.catalog_card SET name='tampered' WHERE catalog_snapshot_id=%s",
                (old,),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            writer.execute(
                "UPDATE catalog.catalog_snapshot SET state='staging' WHERE catalog_snapshot_id=%s",
                (old,),
            )
        assert (
            writer.execute(
                "SELECT count(*) FROM catalog.catalog_publication_attempt "
                "WHERE catalog_snapshot_id=%s",
                (old,),
            ).fetchone()[0]
            == 1
        )
    new = publish(second)["catalog_snapshot_id"]
    rollback_catalog(role_dsn("catalog_publisher"), old, new)
    with psycopg.connect(role_dsn("catalog_reader")) as reader:
        assert active(reader) == old
        assert (
            reader.execute(
                "SELECT count(*) FROM catalog.published_snapshot "
                "WHERE catalog_snapshot_id IN (%s,%s)",
                (old, new),
            ).fetchone()[0]
            == 2
        )


def test_failed_load_staging_invisibility_and_retry(publications):
    first, failed, _ = publications
    old = publish(first)["catalog_snapshot_id"]

    def fail(snapshot):
        with psycopg.connect(role_dsn("catalog_reader")) as reader:
            assert active(reader) == old
            assert (
                reader.execute(
                    "SELECT count(*) FROM catalog.published_snapshot WHERE catalog_snapshot_id=%s",
                    (snapshot,),
                ).fetchone()[0]
                == 0
            )
            assert (
                reader.execute(
                    "SELECT count(*) FROM catalog.published_catalog_card "
                    "WHERE catalog_snapshot_id=%s",
                    (snapshot,),
                ).fetchone()[0]
                == 0
            )
        raise RuntimeError("injected interruption before promotion")

    with pytest.raises(RuntimeError, match="injected"):
        publish(failed, before_promote=fail)
    with psycopg.connect(role_dsn("catalog_publisher")) as writer:
        assert active(writer) == old
        assert writer.execute(
            "SELECT state,error_code FROM catalog.catalog_publication_attempt "
            "WHERE catalog_snapshot_id=%s",
            (failed.name,),
        ).fetchone() == ("failed", "publication_failed")
        assert (
            writer.execute(
                "SELECT count(*) FROM catalog.catalog_card WHERE catalog_snapshot_id=%s",
                (failed.name,),
            ).fetchone()[0]
            == 0
        )
    assert publish(failed)["state"] == "published"


def test_publishers_serialize_while_readers_keep_previous_snapshot(publications):
    first, second, third = publications
    old = publish(first)["catalog_snapshot_id"]
    staged, release, second_entered, second_started = Event(), Event(), Event(), Event()

    def pause(_):
        staged.set()
        assert release.wait(10)

    def run_second():
        second_started.set()
        return publish(third, before_promote=lambda _: second_entered.set())

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(publish, second, before_promote=pause)
        assert staged.wait(10)
        two = pool.submit(run_second)
        assert second_started.wait(10)
        try:
            with psycopg.connect(role_dsn("catalog_reader")) as reader:
                assert active(reader) == old
                assert (
                    reader.execute(
                        "SELECT count(*) FROM catalog.published_catalog_card "
                        "WHERE catalog_snapshot_id=%s",
                        (old,),
                    ).fetchone()[0]
                    == 7
                )
            assert not second_entered.wait(0.2)
        finally:
            release.set()
        assert one.result(timeout=10)["state"] == "published"
        assert two.result(timeout=10)["state"] == "published"
    with psycopg.connect(role_dsn("catalog_reader")) as reader:
        assert active(reader) == third.name


def test_abandoned_attempt_recovered_and_bad_counts_rejected(publications):
    first, second, _ = publications
    old = publish(first)["catalog_snapshot_id"]
    payload, manifest = verify_artifact(second, SEED)
    abandoned = uuid4()
    with psycopg.connect(role_dsn("catalog_publisher"), autocommit=True) as writer:
        writer.execute("SELECT pg_advisory_lock(724602)")
        writer.execute(
            "SELECT catalog.begin_publication(%s,%s,%s,%s)",
            (Jsonb(payload), Jsonb(manifest), abandoned, old),
        )
        with pytest.raises(psycopg.Error, match="row_count_mismatch"):
            writer.execute("SELECT catalog.promote_publication(%s)", (abandoned,))
    # Closing the dedicated connection simulates crash/release; next run repairs the attempt.
    assert publish(second)["state"] == "published"
    with psycopg.connect(role_dsn("catalog_publisher")) as writer:
        assert writer.execute(
            "SELECT state,error_code FROM catalog.catalog_publication_attempt WHERE attempt_id=%s",
            (abandoned,),
        ).fetchone() == ("failed", "abandoned_attempt")


def test_invalid_references_and_stale_promotion_preserve_previous(publications, monkeypatch):
    import mtg_scorer.publish.postgres as publisher

    first, second, _ = publications
    old = publish(first)["catalog_snapshot_id"]
    load = publisher._load_rows

    def wrong_reference(connection, payload, export_file):
        load(connection, payload, export_file)
        connection.execute(
            "UPDATE catalog.catalog_card SET source_scryfall_id=%s WHERE catalog_snapshot_id=%s",
            (uuid4(), payload["catalog_snapshot_id"]),
        )

    with monkeypatch.context() as patch:
        patch.setattr(publisher, "_load_rows", wrong_reference)
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            publish(second)
    with psycopg.connect(role_dsn("catalog_publisher"), autocommit=True) as writer:
        assert active(writer) == old
        with pytest.raises(psycopg.Error, match="stale_promotion"):
            writer.execute("SELECT catalog.rollback_catalog(%s,NULL)", (old,))
