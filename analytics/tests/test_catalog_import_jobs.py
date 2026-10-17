"""Real HTTP, PostgreSQL and worker tests using retained fixture bytes only."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import psycopg
import pytest
from test_bulk_catalog import bulk_fixture

from mtg_scorer.import_worker import WORKER_LOCK, run_once

API = os.environ.get("CATALOG_TEST_API_URL")
DSN = os.environ.get("CATALOG_TEST_PUBLISH_DSN")
TOKEN = os.environ.get("CATALOG_IMPORT_ADMIN_TOKEN")
pytestmark = pytest.mark.skipif(not (API and DSN and TOKEN), reason="running fixture API required")
ROUTE = "/api/v1/admin/catalog-imports"


def request(path=ROUTE, method="POST", token=TOKEN):
    req = Request(
        API + path, method=method, headers={"Authorization": "Bearer " + token} if token else {}
    )
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


def test_authorization_duplicate_status_worker_reuse_and_recovery(tmp_path):
    assert request(token=None)[0] == 401
    assert request(token="incorrect")[0] == 401
    assert request(ROUTE + "/" + str(uuid4()), "GET", token=None)[0] == 401
    assert request(ROUTE + "/" + str(uuid4()), "GET")[0] == 404
    assert request(ROUTE + "/invalid", "GET")[0] == 400
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: request(), range(8)))
    assert {status for status, _ in results} == {202}
    assert len({body["job_id"] for _, body in results}) == 1
    job = results[0][1]
    assert job["state"] == "queued" and job["started_at"] is None
    source = bulk_fixture(tmp_path / "raw")
    entered, release = Event(), Event()

    def download(_):
        entered.set()
        assert release.wait(15)
        return source

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run_once, DSN, tmp_path, download=download)
        assert entered.wait(5)
        try:
            assert request(job["status_url"], "GET")[1]["state"] == "running"
            assert request()[1]["job_id"] == job["job_id"]
            assert run_once(DSN, tmp_path, download=download) is False
        finally:
            release.set()
        assert future.result(timeout=30)
    completed = request(job["status_url"], "GET")[1]
    assert completed["state"] == "succeeded", completed
    assert completed["row_counts"]["cards"] == 7
    assert completed["result"] == "published"
    assert completed["finished_at"] and completed["source_snapshot_id"]
    next_job = request()[1]
    run_once(DSN, tmp_path, download=lambda _: source)
    reused = request(next_job["status_url"], "GET")[1]
    assert reused["result"] == "already_published"
    assert reused["catalog_snapshot_id"] == completed["catalog_snapshot_id"]
    failed_job = request()[1]

    def fail(_):
        raise ValueError("password=SECRET path=private fixture failure")

    run_once(DSN, tmp_path, download=fail)
    failed = request(failed_job["status_url"], "GET")[1]
    assert failed["state"] == "failed" and failed["error_code"] == "import_failed"
    assert "SECRET" not in json.dumps(failed)
    abandoned = request()[1]
    with psycopg.connect(DSN, autocommit=True) as worker:
        worker.execute("SELECT pg_advisory_lock(%s)", (WORKER_LOCK,))
        worker.execute(
            "UPDATE catalog.catalog_import_job SET state='running' WHERE job_id=%s",
            (abandoned["job_id"],),
        )
        assert request(abandoned["status_url"], "GET")[1]["state"] == "running"
    recovered = request(abandoned["status_url"], "GET")[1]
    assert recovered["state"] == "failed" and recovered["error_code"] == "worker_interrupted"
    retry = request()[1]
    run_once(DSN, tmp_path, download=lambda _: source)
    assert request(retry["status_url"], "GET")[1]["state"] == "succeeded"
    with psycopg.connect(os.environ["TEST_DATABASE_DSN"], autocommit=True) as reader:
        reader.execute("SET ROLE catalog_reader")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            reader.execute("SELECT catalog.request_catalog_import(%s)", (uuid4(),))
