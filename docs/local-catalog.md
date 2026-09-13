# Local catalog: run, verify and recover

This guest application serves the eight retained real Scryfall responses in
`analytics/seeds/scryfall-layouts-v1`. It needs no MTG account or production
credentials. Python publishes facts; Spring owns product queries; Next.js renders
the Java responses. Application requests do not run Python or query MTG source
APIs. Browsers load card scans from published image URLs under the image delivery
exception in [ADR 0001](adr/0001-polyglot-application-boundary.md).

## Toolchain and first start

Use Python **3.12.10**, Node **24.14.1**, npm **11.11.0**, and a **JDK 21**.
Python resolutions and package hashes are in `analytics/uv.lock`; npm resolutions
are in `web/package-lock.json`. Maven Wrapper and the Spring dependency BOM pin
the Java build. Maven Enforcer rejects other JDK major versions. Ruff, Spotless,
strict TypeScript, dependency checks and generated-client drift checks are gates.

From the repository root in PowerShell:

```powershell
# Set this to your own JDK 21 directory. On the verified machine:
$env:JAVA_HOME = 'C:\Users\paulo\.jdks\temurin-21.0.12.1'
python scripts/demo.py up
```

The entry point installs the locked Python and npm environments, obtains the
Playwright Chromium runtime, runs language checks/tests, builds both applications,
starts PostgreSQL if needed, migrates a local database, publishes the real seed,
and starts the preview. First setup needs internet for tool dependencies; catalog
verification uses retained bytes and never fetches live Scryfall or TopDeck.

Open [discovery](http://127.0.0.1:3300/cards) and
[Swagger](http://127.0.0.1:18080/swagger-ui.html). Ctrl+C stops this runner's Java
and Next.js processes. PostgreSQL, published snapshots and logs remain available.
Occupied API/web ports cause a clear error; the runner does not terminate other
applications. Each run launches a copy of the JAR so Windows does not lock the
Maven build output.

For subsequent starts with installed dependencies and verified builds:

```powershell
python scripts/demo.py up --skip-install --skip-build
```

On POSIX, use the same Python entry point after exporting `JAVA_HOME`. The script
uses `bash api/mvnw` and platform-specific Python/Node paths automatically. Supply
a local PostgreSQL connection or put native PostgreSQL binaries on PATH. Windows
execution has been verified here; the Linux path is configured in CI, whose remote
execution is not claimed by local results.

## PostgreSQL choices and credentials

On Windows with no configured database, the runner uses the official EDB portable
PostgreSQL **17.11** archive, verifies SHA-256
`4b8db0930c38f6ef845db919551dedda3b6b845aeb0927b3d79a6e8e9e4537cf`,
and extracts it beneath ignored `.local/tools`. The binary source is linked from
[PostgreSQL's Windows downloads](https://www.postgresql.org/download/windows/) and
[EDB's binary archives](https://www.enterprisedb.com/download-postgresql-binaries).
No Windows service or system-wide PostgreSQL installation is created.

The default cluster is `.local/postgres-data`, listens only on **127.0.0.1:55432**,
and uses local trust authentication for this development workspace. It is not a
production configuration. To use an existing local service instead:

```powershell
$env:CATALOG_ADMIN_DSN = 'postgresql://postgres:YOUR_LOCAL_PASSWORD@127.0.0.1:5432/postgres'
python scripts/demo.py up
```

Alternatively set `POSTGRES_BIN` to a directory containing `initdb` and `pg_ctl`.
The admin account needs database/role creation and migration privileges on this
local test service. The application connects as `catalog_api_local`, a member of
`catalog_reader`; the publisher connects as `catalog_publisher_local`, a member
of `catalog_publisher`. The demo creates these login roles with the development
password `local-catalog-only` if absent. Existing roles are not reset. Migrations
use the separate admin connection. The reader cannot access staging tables or
write the active pointer; the publisher cannot alter published rows or schemas.

The development database is **mtg_catalog_demo**. To stop the default Windows
cluster after stopping the preview:

```powershell
& .local/tools/postgresql-17.11/pgsql/bin/pg_ctl.exe -D .local/postgres-data stop -m fast
```

## Complete deterministic verification

```powershell
python scripts/demo.py verify
```

This creates a new `mtg_verify_<id>` database, applies the actual Flyway migration,
checks the initially unavailable API, exercises PostgreSQL publication under the
restricted roles, publishes the real seed, checks Java HTTP responses, and runs
Chromium against the production Next.js build. Verification uses **18081/3301**,
so it does not share the preview's API/web ports. Test-only synthetic records are
explicitly labeled and never become the final demo seed.

Results include unit/contract checks; real PostgreSQL failure, integrity, retry,
permission, abandonment, concurrency and rollback tests; HTTP filters and pinned
pagination; browser discovery/faces/dataset, clipboard/reopened URLs, Back,
loading, empty/error/retry, mobile overflow and axe checks. Publication and HTTP
tests skipped in the offline phase are explicitly run in their database phases;
the no-active test runs before the first publication.

Card image tests compare Java responses with all eight retained source printings
and check filtered previews, both Delver faces and failed-image fallbacks in the
browser. Browser tests stub the image host so this workflow stays deterministic;
real CDN availability and visual image quality need a separate live check.

Evidence is retained under `.local/mtg_verify_<id>/`, `api/target/surefire-reports/`
and `web/test-results/` / `web/playwright-report/`. The test database is retained
for diagnosis; no existing database is cleared. CI runs this same entry point
against PostgreSQL 17.11 and uploads its evidence. It needs no live MTG service.

To verify a new Python environment without replacing an existing virtualenv:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.local/clean-python-m2"
python scripts/demo.py verify
Remove-Item Env:UV_PROJECT_ENVIRONMENT
```

## Reproduce the seed, publish, retry or roll back

The source manifest has SHA-256
`263bef0fc5d4833af02db85207c19df16e0e8c60a3847df997e3e9a8faa8cc4a`.
Git attributes preserve these JSON files as exact bytes, including their original
line endings; checkout conversion must not change source provenance.
The default export identity is
`catalog-5d2a2464059d4c02fcedbc47c3687262066338961421f84a7d03eb5021744d6e`.
The scripted demo fixes `created_at` to `2026-09-08T00:46:15Z`, so a fresh export
has the same bytes across machines. The catalog has **7 cards, 8 printings,
10 faces, 17 aliases**, with no exclusions from these eight source records.
Its source scope remains incomplete; there are no tournament observations.

After the setup/migration above, PowerShell from the repository root:

```powershell
$seed = 'analytics/seeds/scryfall-layouts-v1'
$snapshot = 'catalog-5d2a2464059d4c02fcedbc47c3687262066338961421f84a7d03eb5021744d6e'
analytics/.venv/Scripts/python.exe -m mtg_scorer.cli export-catalog --source-dir $seed --output-root .local/manual-export --created-at 2026-09-08T00:46:15Z
$env:CATALOG_PUBLISH_DSN = 'postgresql://catalog_publisher_local:local-catalog-only@127.0.0.1:55432/mtg_catalog_demo'
analytics/.venv/Scripts/python.exe -m mtg_scorer.cli publish-catalog --source-dir $seed --artifact ".local/manual-export/$snapshot"
```

Retry the identical `publish-catalog` command. Already published content is a
no-op, not a pointer rollback. The same dataset ID with another export digest is
rejected. A failed unpublished attempt is rebuilt under a new attempt ID; an
abandoned running attempt is marked failed while the next publisher holds the
advisory lock. Never regenerate `created_at` or edit files beneath an existing
snapshot directory. A deliberate new source/parser/selection gets another ID.

To roll the pointer back to an explicitly retained published ID:

```powershell
analytics/.venv/Scripts/python.exe -m mtg_scorer.cli rollback-catalog --target catalog-RETAINED_ID --expected catalog-CURRENT_ACTIVE_ID
```

Use full IDs from `/api/v1/snapshots`; placeholders above are intentionally not
executable identities. A stale expected pointer is rejected. Rollback does not
rewrite rows or make newer retained snapshots inaccessible. No deletion policy
is introduced in this milestone.

## Diagnose a failed refresh

1. Read the publisher's snapshot/attempt IDs and local exception log. API Problem
   Details include a request ID; responses never expose SQL, paths or credentials.
2. Query `catalog.catalog_publication_attempt` with the publisher role. A failed
   attempt has a stable `publication_failed` or `abandoned_attempt` code; loading
   failure leaves child rows uncommitted and the previous active snapshot intact.
3. Verify raw hashes, `source-manifest.json`, `manifest.json`, and the export hash.
   Correct the new input or producer rather than patching a published database row.
4. Retry the complete immutable artifact. Use explicit pointer rollback only if
   a valid published catalog should be replaced by another retained publication.

`/actuator/health/liveness` checks the process; `/actuator/health/readiness` requires
a usable connection and active published catalog. Missing tournament evidence
does not make a catalog unready. Query errors are 400, unknown card/snapshot is
404, unavailable catalog is 503, and unexpected implementation failure is 500.

## Contract evolution and limits

The authoritative HTTP schema is generated from Spring at
`contracts/catalog-api.openapi.json`. The milestone-1 proposal was preserved at
`docs/evidence/milestone1/catalog-api.proposal.openapi.json`. To intentionally
change a Java DTO or parameter contract:

```powershell
analytics/.venv/Scripts/python.exe scripts/api_contract.py --url http://127.0.0.1:18080 --update
```

Review the resulting OpenAPI and `web/src/lib/api.generated.ts` together. Normal
verification compares live OpenAPI and regenerated TypeScript for drift.

The bounded exporter uses in-memory source projection; the publisher streams
table rows and keeps compact relationship indexes. Neither is claimed to have
constant memory or proven full-catalog throughput. The benchmark records exact
seed, runtime, import wall time, process peak RSS, disk usage, EXPLAIN ANALYZE and
100 warm loopback requests at 20 readers. It proves this small integration only.
Full-catalog scale, public hosting, costs, backup restore, broad browser/screen-reader
coverage, tournament quality, public data/code licensing and Forge mapping remain
outside the verified local milestone.
