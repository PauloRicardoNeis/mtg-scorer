# MTG Scorer API

Java 21 / Spring Boot 4.1.1 product queries over Python-published PostgreSQL
catalogs. Spring JDBC owns filtering/pagination; Flyway owns schema and database
transition functions. No request launches Python, fetches MTG sources or serves
research scores. The Next.js guest application consumes the generated HTTP contract.

## Run the seeded application

From the repository root with JDK 21 in `JAVA_HOME`:

```powershell
python scripts/demo.py up
```

Open [Swagger](http://127.0.0.1:18080/swagger-ui.html) or
[the guest catalog](http://127.0.0.1:3300/cards). The
[local runbook](../docs/local-catalog.md) covers toolchain installation, separate
migration/reader/publisher roles, exact environment variables, retry and rollback.

## Implemented resources

| Route | Purpose |
| --- | --- |
| `/api/v1/cards` | Literal canonical/face-name search, joint printing filters, pinned keyset pagination |
| `/api/v1/cards/{oracle_id}` | Canonical metadata with ordered faces |
| `/api/v1/cards/{oracle_id}/printings` | Paginated printings satisfying set/rarity/game together |
| `/api/v1/cards/{oracle_id}/decks` | Published tournament decks that played the card, one run at a time, newest event first |
| `/api/v1/decks/{score_run_id}/{position}` | One published deck and its whole list, with each card's catalog details |
| `/api/v1/snapshots` | Active catalog first, then up to 19 retained published catalogs |
| `/api/v1/snapshots/{catalog_snapshot_id}` | Provenance, set vocabulary, counts and explicit unavailable tournament evidence |
| `/api/v1/info` | Build version and implemented capabilities |
| `POST /api/v1/admin/catalog-imports` | Bearer-protected durable import enqueue; 202 and status URL |
| `GET /api/v1/admin/catalog-imports/{job_id}` | Bearer-protected job state, stages, timestamps, counts and result |
| `/v3/api-docs`, `/swagger-ui.html` | Generated OpenAPI and interactive documentation |
| `/actuator/health/liveness` | Process liveness |
| `/actuator/health/readiness` | Database and active published catalog readiness |

Query rules and all response types are in the generated
[OpenAPI](../contracts/catalog-api.openapi.json) and
[catalog contract](../docs/catalog-contract.md). Unknown/duplicate scalar parameters
are rejected. Set/rarity values use OR within each dimension, AND across dimensions
on a single printing. A missing active catalog is 503, not an empty success.
Every continuation cursor retains its snapshot, filters, resource, sort and limit.

Errors use sanitized Problem Details with stable `code` and `request_id` fields.
Invalid query/cursor is 400, unknown card/snapshot is 404, unavailable catalog is
503, and unexpected implementation failure is 500. Server logs retain the cause;
clients must not parse human-readable `detail`. Container-level rejections before
Spring dispatch remain outside the application error-handler contract.

## Standalone Java build

```powershell
.\api\mvnw.cmd -f pom.xml --batch-mode --no-transfer-progress verify
```

The root Maven aggregator supports IDE discovery; `api/pom.xml` remains the
independent Java build. On POSIX use `bash ./api/mvnw`. Maven Wrapper 3.9.16 checks
its download checksum. Enforcer requires JDK 21; Spotless uses Google Java Format.
The Java suite covers query/cursor rules, real embedded HTTP and disabled admin credentials. The full
`python scripts/demo.py verify` command adds actual Flyway/PostgreSQL publication,
Java HTTP behavior across refreshes, and browser checks. H2 is not used.
Import job checks use real PostgreSQL and fixture-backed Python workers, including
unauthorized requests, concurrent enqueue, source reuse and disconnected-worker
recovery. Set `CATALOG_IMPORT_ADMIN_TOKEN` only on the server and trusted clients;
the default disables both administrative endpoints. See the
[import runbook](../docs/local-catalog.md#full-catalog-import-worker-and-administration).

For intentional formatting or HTTP contract changes:

```powershell
.\api\mvnw.cmd -f api/pom.xml spotless:apply
analytics/.venv/Scripts/python.exe scripts/api_contract.py --url http://127.0.0.1:18080 --update
```

The latter regenerates TypeScript from Spring; review both artifacts. SQL internals
remain inside each Java capability. Catalog calls the public `SnapshotService`
resolver; dependency checks reject reverse/cyclic capability imports.
