"""Worker job-state logic without PostgreSQL; the real queue is proven in the database stage."""

import json
import logging
import re
import sys

import pytest
from test_bulk_catalog import bulk_fixture

import mtg_scorer.import_worker as worker
from mtg_scorer.normalize.catalog import SCHEMA_VERSION
from mtg_scorer.publish.bulk import PARSER_VERSION, bulk_identity
from mtg_scorer.publish.stream import verify_publication

DSN = "dbname=catalog_worker_test"


class Result:
    def __init__(self, rows=(), rowcount=None):
        self.rows = list(rows)
        self.rowcount = len(self.rows) if rowcount is None else rowcount

    def fetchone(self):
        return self.rows[0] if self.rows else None


class JobDatabase:
    """Models the single job row a worker may own and records each statement it sends."""

    def __init__(self, *, lock_available=True, queued=True, published=None, recovered_at=None):
        self.lock_available = lock_available
        self.published = published
        self.recovered_at = recovered_at
        self.job = {"job_id": "job-1", "state": "queued" if queued else "succeeded"}
        self.stages = []
        self.statements = []
        self.closed = self.broken = False

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.closed = True

    def execute(self, query, params=()):
        text = query if isinstance(query, str) else query.as_string(None)
        self.statements.append((text, tuple(params)))
        if "pg_try_advisory_lock" in text:
            return Result([(self.lock_available,)])
        if "SET state='running'" in text:
            if self.job["state"] != "queued":
                return Result()
            self.job.update(state="running", parser_version=params[0], schema_version=params[1])
            return Result([(self.job["job_id"],)])
        if "SET stage=" in text:
            stage, *values, job_id = params
            if stage == self.recovered_at:
                self.job["state"] = "failed"  # another session recovered the job meanwhile
            if job_id != self.job["job_id"] or self.job["state"] != "running":
                return Result(rowcount=0)
            columns = re.findall(r'"(\w+)"=%s', text)
            for column, value in zip(columns, values, strict=True):
                self.job[column] = getattr(value, "obj", value)
            self.stages.append(stage)
            return Result(rowcount=1)
        if "FROM catalog.catalog_snapshot" in text:
            return Result([(self.published,)] if self.published else [])
        if "SET state='succeeded'" in text:
            self.job["state"] = "succeeded"
        elif "SET state='failed'" in text:
            self.job.update(state="failed", error_code="import_failed")
        return Result()

    def ran(self, fragment):
        return any(fragment in text for text, _ in self.statements)


def connect_to(monkeypatch, database):
    def connect(dsn, *, autocommit):
        assert (dsn, autocommit) == (DSN, True)
        return database

    monkeypatch.setattr(worker.psycopg, "connect", connect)
    return database


def never(*args, **kwargs):
    pytest.fail("called after the worker should have stopped")


def test_worker_without_the_lock_claims_nothing(tmp_path, monkeypatch):
    database = connect_to(monkeypatch, JobDatabase(lock_available=False))

    assert worker.run_once(DSN, tmp_path, download=never) is False
    assert database.statements == [("SELECT pg_try_advisory_lock(%s)", (worker.WORKER_LOCK,))]
    assert database.job["state"] == "queued"


def test_idle_worker_recovers_and_releases_its_lock(tmp_path, monkeypatch):
    database = connect_to(monkeypatch, JobDatabase(queued=False))

    assert worker.run_once(DSN, tmp_path, download=never) is False
    assert database.ran("catalog.recover_catalog_import()")
    assert database.statements[-1] == ("SELECT pg_advisory_unlock(%s)", (worker.WORKER_LOCK,))


def test_worker_records_each_stage_and_publishes_on_its_own_connection(tmp_path, monkeypatch):
    source = bulk_fixture(tmp_path / "retained")
    database = connect_to(monkeypatch, JobDatabase())
    downloads, published = [], []

    def publish(artifact, source_dir, dsn, *, before_promote, before_load, connection):
        assert (dsn, connection) == (DSN, database)
        verify_publication(artifact, source_dir)
        before_load()
        before_promote(artifact.name)
        published.append(artifact)
        return {"catalog_snapshot_id": artifact.name, "state": "published"}

    monkeypatch.setattr(worker, "publish_catalog", publish)

    assert worker.run_once(DSN, tmp_path, download=lambda root: downloads.append(root) or source)

    identity = bulk_identity(json.loads(source.manifest_file.read_bytes()), PARSER_VERSION)
    manifest = json.loads((tmp_path / "catalog" / identity / "manifest.json").read_bytes())
    assert downloads == [tmp_path / "raw" / "scryfall"]
    assert published == [tmp_path / "catalog" / identity]
    assert database.stages == ["normalizing", "validating", "publishing", "promoting", "complete"]
    assert database.job == {
        "job_id": "job-1",
        "state": "succeeded",
        "parser_version": PARSER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "source_snapshot_id": source.snapshot_id,
        "catalog_snapshot_id": identity,
        "row_counts": manifest["row_counts"],
        "excluded_record_counts": manifest["excluded_record_counts"],
        "result": "published",
    }
    assert database.statements[-1] == ("SELECT pg_advisory_unlock(%s)", (worker.WORKER_LOCK,))


def test_already_published_snapshot_completes_without_exporting(tmp_path, monkeypatch):
    source = bulk_fixture(tmp_path / "retained")
    counts = {
        "row_counts": {"cards": 7, "faces": 10, "printings": 8, "aliases": 17},
        "excluded_record_counts": {"missing_oracle_id": 2},
    }
    database = connect_to(monkeypatch, JobDatabase(published=counts))
    monkeypatch.setattr(worker, "export_bulk_catalog", never)
    monkeypatch.setattr(worker, "publish_catalog", never)

    assert worker.run_once(DSN, tmp_path, download=lambda _: source)

    identity = bulk_identity(json.loads(source.manifest_file.read_bytes()), PARSER_VERSION)
    lookups = [params for text, params in database.statements if "catalog_snapshot " in text]
    assert lookups == [(identity,)]
    assert database.stages == ["normalizing", "complete"]
    assert database.job["state"] == "succeeded"
    assert database.job["result"] == "already_published"
    assert {key: database.job[key] for key in counts} == counts


def test_ownership_lost_during_validation_leaves_no_export_and_no_success(tmp_path, monkeypatch):
    source = bulk_fixture(tmp_path / "retained")
    database = connect_to(monkeypatch, JobDatabase(recovered_at="validating"))
    monkeypatch.setattr(worker, "publish_catalog", never)

    assert worker.run_once(DSN, tmp_path, download=lambda _: source)

    assert database.stages == ["normalizing"]
    assert list((tmp_path / "catalog").iterdir()) == []
    assert not database.ran("SET state='succeeded'")
    assert database.ran("pg_advisory_unlock")


def test_failed_import_persists_only_a_stable_error_code(tmp_path, monkeypatch, caplog):
    database = connect_to(monkeypatch, JobDatabase())

    def download(_):
        raise ValueError("password=SECRET fixture failure")

    with caplog.at_level(logging.ERROR, logger=worker.LOG.name):
        assert worker.run_once(DSN, tmp_path, download=download)

    assert database.job["state"] == "failed"
    assert database.job["error_code"] == "import_failed"
    assert "SECRET" not in repr(database.statements)
    assert "import failed job=job-1" in caplog.text
    assert caplog.records[-1].exc_info[0] is ValueError
    assert database.ran("pg_advisory_unlock")


def test_broken_connection_skips_the_failure_record_and_unlock(tmp_path, monkeypatch):
    database = connect_to(monkeypatch, JobDatabase())

    def download(_):
        database.broken = True
        raise OSError("connection lost")

    assert worker.run_once(DSN, tmp_path, download=download)
    assert not database.ran("SET state='failed'")
    assert not database.ran("pg_advisory_unlock")


def start_main(monkeypatch, *arguments):
    monkeypatch.setenv("CATALOG_PUBLISH_DSN", DSN)
    monkeypatch.setattr(worker.logging, "basicConfig", lambda **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["import_worker", *map(str, arguments)])
    worker.main()


def test_main_once_rebuilds_from_a_verified_retained_source(tmp_path, monkeypatch):
    source = bulk_fixture(tmp_path / "retained")
    calls = []

    def run_once(dsn, data_dir, *, download):
        calls.append((dsn, data_dir, download(data_dir / "raw" / "scryfall")))

    monkeypatch.setattr(worker, "run_once", run_once)
    monkeypatch.setattr(worker.time, "sleep", never)

    start_main(
        monkeypatch,
        "--once",
        "--data-dir",
        tmp_path / "data",
        "--source-dir",
        source.raw_file.parent,
    )
    assert calls == [(DSN, tmp_path / "data", source)]

    source.raw_file.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="raw snapshot checksum mismatch"):
        start_main(monkeypatch, "--once", "--source-dir", source.raw_file.parent)


def test_main_without_once_keeps_polling_the_live_source(monkeypatch):
    class StopPollingError(Exception):
        pass

    downloads, sleeps = [], []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise StopPollingError

    monkeypatch.setattr(
        worker, "run_once", lambda dsn, data_dir, *, download: downloads.append(download)
    )
    monkeypatch.setattr(worker.time, "sleep", sleep)

    with pytest.raises(StopPollingError):
        start_main(monkeypatch)
    assert downloads == [worker.download_default_cards_snapshot] * 2
    assert sleeps == [2, 2]
