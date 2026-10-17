# ADR 0003: Administrative catalog import jobs

Status: implemented locally, 2026-09-28.

POST `/api/v1/admin/catalog-imports` performs a short PostgreSQL enqueue operation
and returns 202, a durable job ID, and a Location/status URL. GET on that URL
reports state, stage, timestamps, available counts, snapshot identities, versions,
result and a stable error code. Java does no source I/O or Python execution.

A separate Python worker polls the database. One partial unique index permits
one queued/running job; serialized enqueue calls reuse that job. A session advisory
lock (724603) covers the whole import. The worker uses that same connection for
publication, so losing ownership also loses any uncommitted publication. The
existing publication lock (724602), byte checks, staging guards and atomic pointer
promotion remain authoritative. No message broker is needed for this single job
stream.

GET, POST and worker startup can mark a disconnected worker's running job failed
only after obtaining its advisory lock. A live worker is never stolen based on
an estimated duration. A deliberately stopped or crashed worker can be retried by
POST; the next attempt reuses verified files. Queued jobs remain queued until a
worker is operated. `updated_at` records stage transitions, not a percent complete
or heartbeat. Process supervision is an operator responsibility.

Both routes require the server-only `CATALOG_IMPORT_ADMIN_TOKEN` bearer credential
(at least 32 characters). Missing/short configuration disables administration.
There are no browser credentials, user accounts, scheduled refreshes, or arbitrary
HTTP source URLs. An API database role receives only enqueue/status function
permissions. Publication and migrations keep their separate credentials.

Bulk identity hashes source type, source timestamp, verified raw SHA-256, effective
parser version (normalizer plus bulk pipeline), publication schema version and
selection. Retrieval time and transport URL do not create new content identities.
The complete retained source manifest still has its own verified byte hash.
An already-published identity is explicitly `already_published`; it does not
reactivate an older snapshot after rollback. Version changes rebuild retained
source data. A worker can be pinned to a retained source directory for an offline
rebuild. Normal startup only migrates/serves the database; sample activation is
explicit and deterministic verification uses a separate database.

The bulk exporter uses disk staging and the existing pure face-aware projection.
Validation uses disk indexes instead of retaining the full source or all output
rows. Game metadata now also retains the legacy `astral` and `sega` values observed
in the real source. Existing UI game filters remain paper/Arena/MTGO; other values
remain visible in printing details and included in unfiltered searches.
