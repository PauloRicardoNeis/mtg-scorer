# ADR 0002: Catalog publication and delivery order

- Status: Accepted and implemented for the locally verified milestone-2 catalog
- Date: 2026-09-07 (America/Sao_Paulo)
- Supersedes: sequencing in ADR 0001 and the older implementation roadmap only

## Problem and decision

Deliver guest catalog discovery before empirical scoring is ready. Use Python
normalization and batch publication, PostgreSQL, Spring JDBC/Flyway, and Next.js
with TypeScript. The first browser slice includes discovery, card detail, and
dataset/methodology pages. Scores and tournament sorting remain absent.

| Conflict | Resolution |
| --- | --- |
| Portfolio sections 4/8 bring the browser forward; ADR 0001 step 5 and the old roadmap wait for scores | Catalog publication, API and browser now precede scores. The early catalog is a checkpoint, not the completed evidence product. |
| Old research roadmap delays PostgreSQL until after clustering/gold tables | Introduce it for the catalog's indexed read path and atomic publication. Research continues in DuckDB/Parquet. |
| Old roadmap names TopDeck as the next corpus | TopDeck remains a candidate. No analytical cohort is selected without accessible event/deck evidence. Missing access does not delay catalog work. |
| ADR 0001 invariant 5 requires model identity on every published row, including catalog facts | Catalog facts carry catalog snapshot, source, parser and publication identity. Only analytical results require all four measurement identities. Inventing a score model for a catalog would be false provenance. This clarification preserves the measurement contract. |
| Portfolio increment 2 asks for a hosted preview | The next autonomous milestone ends with a locally runnable, CI-verified preview. Hosting is a separate step requiring provider/budget selection and authorization; this task forbids deployment. |
| Existing research scoring emits numeric values with little/no evidence | Keep the research implementation; no numeric scores enter catalog v1. Python will own a separate versioned public eligibility policy before evidence serving. |

## Options and consequences

| Option | Correctness / effort / operation | Decision and revisit condition |
| --- | --- | --- |
| Java reads Parquet directly | Few processes, but indexed filtering, publication locking and stable concurrent reads need extra file-lifecycle work | Retain for offline inspection only. Revisit if the product becomes a single-user offline tool. |
| Python publishes PostgreSQL; Java uses explicit SQL | One database to operate; native keys, transactions and explainable query plans; an additional publisher adapter | Selected. API owns migrations, Python targets the contract. No ORM, queue, cache service or search engine yet. |
| Java normalizes Scryfall or calls Python per request | Duplicate analytical/source rules or synchronous pipeline failures | Rejected by ADR 0001. Revisit only through a new ownership decision, never as an optimization shortcut. |

## Domain and ownership

| Concept / identity | Owner and invariant |
| --- | --- |
| Raw snapshot | Python; immutable bytes, SHA-256, retrieval timestamp and source record mapping |
| Catalog snapshot (`catalog_snapshot_id`) | Python-produced dataset, distinct from a database import attempt; digest includes inputs, parser and schema version |
| Oracle card (`oracle_id`) | Python canonical identity; versioned attributes and faces come from one deterministic representative printing |
| Face (`oracle_id`, `face_index`) | Python; source order, not a standalone deck card; never flatten away face text or invent a mana cost |
| Printing (`scryfall_id`) | Python factual mapping; set, rarity, games and images belong here |
| Alias (normalized name, Oracle ID) | Python; ambiguity is retained, never arbitrarily resolved |
| Publication attempt (`attempt_id`) | Python orchestration/PostgreSQL adapter; retry and diagnostic identity, separate from dataset identity |
| Active catalog pointer | PostgreSQL transaction; one published snapshot, guarded promotion |
| Pool selection | Java authoritative filter semantics; one printing must satisfy all printing constraints |
| Historical cohort | Python; source + format + bounded era + coverage class + explicit opportunity pool; independent of a user's present-day pool |
| Observation / derived estimate | Python only; unknown differs from zero; estimates retain dataset, feature pipeline, model, config hash and eligibility-policy identity |
| HTTP request / page state | Java resolves one snapshot per request; Next.js renders returned values and preserves snapshot/filter URLs |

Java dependencies: `catalog` uses the public `snapshots` resolver; both can use
`config`/`error`, never each other's SQL internals. Controller -> focused query
use case -> JDBC adapter. Pure rules do not depend on Spring or I/O. Python pure
domain/features/scoring do not import ingest/publish. Add dependency checks when
these modules exist. No interface-per-class requirement.

```mermaid
flowchart LR
  S[Scryfall / permitted tournament source] --> P[Python batch]
  P --> R[Immutable raw + Parquet + serving artifacts]
  R --> V[Python validate/publish adapter]
  V --> D[(PostgreSQL)]
  D --> J[Spring catalog / snapshots]
  J --> W[Next.js guest views]
```

## Publication state and consistency

Dataset states: `staging -> ready -> published`; rejected staging data never
becomes visible. Attempt states: `running -> succeeded | failed`. Published
datasets stay published after replacement; activity is represented by the pointer.
Never change published content. A retry of the same dataset/digest is a no-op;
the same ID with different content is an error. Retrying a failed attempt gets a
new attempt ID and rebuilds only unpublished staging data.

```mermaid
sequenceDiagram
  participant P as Python publisher
  participant DB as PostgreSQL
  participant API as Spring
  P->>DB: Take catalog advisory lock
  P->>DB: BEGIN; create staging header and running attempt; COMMIT
  P->>DB: BEGIN load-and-promote transaction
  P->>DB: Load staging rows with snapshot keys
  P->>DB: Validate schema, hashes, counts, references, domain rules
  P->>DB: ready -> published; compare-and-set active pointer; succeed attempt
  P->>DB: COMMIT
  API->>DB: Resolve explicit ID or active ID once
  API->>DB: Query only published rows at that ID
  Note over P,DB: Failure rolls back promotion; failed attempt recorded separately
```

Use one dedicated connection holding a session advisory lock for the complete
import. First persist the staging snapshot header and running attempt in a short
transaction; load child rows in a separate transaction. This leaves a valid
snapshot FK for the failure record even when loading rolls back. A failed
connection releases the lock; a subsequent run marks abandoned
running attempts failed while holding that lock. Promotion also checks the expected
previous pointer (including null) to prevent stale promotion. Readers cannot select
staging/ready datasets. The API role has read access to published views only;
publisher gets narrowly scoped staging/promote operations; migration credentials
are separate. Enforce immutability and valid transitions in database permissions
and promotion functions, not just Python conventions.

The first slice must already prove no partial visibility, idempotent retry and
snapshot-pinned pagination against PostgreSQL. Milestone 4 broadens operational
stress testing; it does not postpone these invariants. Retain all published
catalogs initially (budget two full snapshots for sizing); no deletion until an
explicit retention policy exists. Rollback moves the pointer to a retained
published ID under the same lock/guard, without rewriting data.

See [the contract](../catalog-contract.md) and
[the dependency-ordered plan](../implementation-plan.md) for executable checks,
workload assumptions and acceptance criteria.

## Implementation evidence (2026-09-08)

The migration is `api/src/main/resources/db/migration/V1__catalog_publication.sql`;
publication adapters are in `analytics/src/mtg_scorer/publish/`; catalog/snapshot
query capabilities are in `api/src/main/java/io/mtgscorer/api/`; guest views are
in `web/src/app/`. [The completion report](../project-status-report.md) maps
acceptance criteria to verification. [The local runbook](../local-catalog.md)
includes explicit retry and guarded pointer rollback commands.
