"""Two score publishers racing on one PostgreSQL; TEST_DATABASE_DSN names a disposable
database. Every run is SYNTHETIC and carries its own identity, so the test shares the
database with the other publication tests.

The catalog publisher has the same proof in test_postgres_publication.py; this one
exercises the score publisher's advisory lock (``LOCK_ID``) and its reading of the
active run under that lock, which no offline test can reach.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from synthetic_topdeck import open_event, save, weekly_event

from mtg_scorer.ingest.topdeck import read_saved_responses
from mtg_scorer.publish.score_postgres import publish_score_run
from mtg_scorer.publish.score_run import build_score_run, write_score_run
from mtg_scorer.tournament_features import CohortRules

DSN = os.environ.get("TEST_DATABASE_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="real PostgreSQL TEST_DATABASE_DSN required")
# A format of its own, so the active run this test moves is never another test's.
FORMAT = "Synthetic Race"


def role_dsn(role):
    return psycopg.conninfo.make_conninfo(DSN, options=f"-c role={role}")


@pytest.fixture
def make_run(tmp_path):
    """Write a fresh SYNTHETIC run file; a unique cohort version gives a unique identity."""

    def make():
        directory = save(tmp_path / uuid4().hex, {"search.json": [open_event(), weekly_event()]})
        rules = CohortRules(
            version=f"synthetic-race-{uuid4()}",
            format_name="Modern",
            starts_on="2026-03-01",
            ends_before="2026-09-01",
        )
        document = build_score_run(read_saved_responses(directory), rules)
        # The synthetic events are Modern; the run is published under this test's format.
        document["cohort"]["rules"]["format_name"] = FORMAT
        return write_score_run(document, tmp_path / "runs")

    return make


def publish(run_file, **kwargs):
    return publish_score_run(run_file, role_dsn("score_publisher"), **kwargs)


def active(connection):
    found = connection.execute(
        "SELECT score_run_id FROM scores.active_score_run "
        "WHERE source='topdeck' AND format_name=%s",
        (FORMAT,),
    ).fetchone()
    return found[0] if found else None


def run_id_of(run_file):
    return run_file.stem


def test_publishers_serialize_while_readers_keep_the_active_run(make_run) -> None:
    first, second, third = make_run(), make_run(), make_run()
    assert publish(first)["state"] == "published"
    staged, release, third_entered, third_started = Event(), Event(), Event(), Event()

    def pause(_):
        staged.set()
        assert release.wait(10)

    def run_third():
        third_started.set()
        return publish(third, before_promote=lambda _: third_entered.set())

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(publish, second, before_promote=pause)
        assert staged.wait(10)
        two = pool.submit(run_third)
        assert third_started.wait(10)
        try:
            with psycopg.connect(role_dsn("score_reader")) as reader:
                # The second run is loaded but not promoted: readers still see the first,
                # with every one of its scores, and the third publisher is held at the lock.
                assert active(reader) == run_id_of(first)
                assert (
                    reader.execute(
                        "SELECT count(*) FROM scores.published_card_score WHERE score_run_id=%s",
                        (run_id_of(first),),
                    ).fetchone()[0]
                    > 0
                )
            with psycopg.connect(DSN) as admin:
                assert (
                    admin.execute(
                        "SELECT state FROM scores.score_run WHERE score_run_id=%s",
                        (run_id_of(second),),
                    ).fetchone()[0]
                    == "staging"
                )
            assert not third_entered.wait(0.2)
        finally:
            release.set()
        assert one.result(timeout=10)["state"] == "published"
        assert two.result(timeout=10)["state"] == "published"
    with psycopg.connect(DSN) as admin:
        assert active(admin) == run_id_of(third)
        assert {
            state
            for (state,) in admin.execute(
                "SELECT state FROM scores.score_run WHERE score_run_id = ANY(%s)",
                ([run_id_of(first), run_id_of(second), run_id_of(third)],),
            ).fetchall()
        } == {"published"}
