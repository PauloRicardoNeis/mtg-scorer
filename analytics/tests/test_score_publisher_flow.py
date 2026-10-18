"""Publisher control flow with a recording connection; real SQL runs in test_score_publication."""

from contextlib import contextmanager

import pytest
from synthetic_topdeck import open_event, save, weekly_event

import mtg_scorer.publish.score_postgres as score_postgres
from mtg_scorer.ingest.topdeck import read_saved_responses
from mtg_scorer.publish.score_postgres import publish_score_run, rollback_score_run
from mtg_scorer.publish.score_run import build_score_run, write_score_run
from mtg_scorer.tournament_features import CohortRules

RULES = CohortRules(
    version="synthetic-flow-v1",
    format_name="Modern",
    starts_on="2026-03-01",
    ends_before="2026-09-01",
)


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Copy:
    def __init__(self, sink):
        self.sink = sink

    def write_row(self, row):
        self.sink.append(row)


class Cursor:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def copy(self, statement):
        rows = []
        yield Copy(rows)
        self.connection.copies.append(rows)


class RecordingConnection:
    """Answers the publisher's two queries and records everything else it is asked."""

    def __init__(self, *, active=None, started=True):
        self.active, self.started = active, started
        self.statements, self.copies = [], []
        self.closed = self.broken = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=()):
        text = statement if isinstance(statement, str) else "<composed>"
        self.statements.append(text)
        if "FROM scores.active_score_run" in text:
            return Result(None if self.active is None else (self.active,))
        if "begin_score_publication" in text:
            return Result((self.started,))
        return Result(None)

    @contextmanager
    def transaction(self):
        yield

    def cursor(self):
        return Cursor(self)

    def called(self, function):
        return any(function in statement for statement in self.statements)


@pytest.fixture
def run_file(tmp_path):
    saved = save(tmp_path / "saved", {"search.json": [open_event(), weekly_event()]})
    return write_score_run(build_score_run(read_saved_responses(saved), RULES), tmp_path / "runs")


def test_a_new_run_is_loaded_promoted_and_unlocked(run_file) -> None:
    connection = RecordingConnection(active="scores-" + "a" * 64)

    result = publish_score_run(run_file, "unused", connection=connection)

    assert result["state"] == "published"
    assert [len(rows) for rows in connection.copies] == [3, 2, 14, 4]
    assert connection.called("promote_score_publication")
    assert not connection.called("fail_score_publication")
    assert connection.statements[-1] == "SELECT pg_advisory_unlock(%s)"


def test_an_already_published_run_is_not_loaded_again(run_file) -> None:
    connection = RecordingConnection(started=False)

    assert publish_score_run(run_file, "unused", connection=connection)["state"] == (
        "already_published"
    )
    assert connection.copies == []
    assert connection.statements[-1] == "SELECT pg_advisory_unlock(%s)"


def test_a_failure_records_the_attempt_and_is_raised(run_file) -> None:
    connection = RecordingConnection()

    def explode(run_id):
        raise RuntimeError("synthetic failure")

    with pytest.raises(RuntimeError, match="synthetic failure"):
        publish_score_run(run_file, "unused", connection=connection, before_promote=explode)

    assert connection.called("fail_score_publication")
    assert not connection.called("promote_score_publication")
    assert connection.statements[-1] == "SELECT pg_advisory_unlock(%s)"


def test_a_broken_connection_is_not_unlocked(run_file) -> None:
    connection = RecordingConnection()

    def break_connection(run_id):
        connection.broken = True
        raise RuntimeError("connection lost")

    with pytest.raises(RuntimeError):
        publish_score_run(
            run_file, "unused", connection=connection, before_promote=break_connection
        )

    assert "SELECT pg_advisory_unlock(%s)" not in connection.statements


def test_without_a_connection_the_publisher_opens_an_autocommit_one(monkeypatch, run_file):
    opened = []

    def connect(dsn, **options):
        opened.append((dsn, options))
        return RecordingConnection()

    monkeypatch.setattr(score_postgres.psycopg, "connect", connect)

    assert publish_score_run(run_file, "dbname=scores")["state"] == "published"
    assert opened == [("dbname=scores", {"autocommit": True})]


def test_an_invalid_file_never_reaches_the_database(monkeypatch, tmp_path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text('{"schema_version": "score-run-file-v1"}')
    monkeypatch.setattr(score_postgres.psycopg, "connect", lambda *a, **k: pytest.fail("opened"))

    with pytest.raises(Exception, match="required property"):
        publish_score_run(broken, "dbname=scores")


def test_rollback_calls_the_guarded_function(monkeypatch) -> None:
    connection = RecordingConnection()
    monkeypatch.setattr(score_postgres.psycopg, "connect", lambda dsn: connection)

    rollback_score_run("dbname=scores", "scores-old", "scores-new")

    assert connection.statements == ["SELECT scores.rollback_score_run(%s,%s)"]
