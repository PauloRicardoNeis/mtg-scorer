# Milestone 2 design and completion review

Reviewed against portfolio section 6, the active implementation checklist,
measurement contract and ADRs 0001/0002. This is the local catalog increment,
not an evidence-ranking release. The earlier source/contract/status material is
retained under `docs/evidence/milestone1/` where it was superseded.

## Reference slice and ownership

The reference is Lightning Bolt plus Delver of Secrets: Bolt proves that an M11
common printing must not combine with a 2X2 uncommon printing to satisfy
2X2/common; Delver proves that missing top-level text/cost must not erase faces.
The same real bytes produce a validated artifact, protected database publication,
Java HTTP results and guest pages. The tests follow that slice through all layers.

| Concern | Owning implementation | Enforced dependency |
| --- | --- | --- |
| Source/layout/name projection | `analytics/src/mtg_scorer/normalize/` | Does not import publication or ingestion orchestration |
| Files, hashes, validation, streaming publication | `analytics/src/mtg_scorer/publish/` | Batch only; uses API-owned database protocol |
| Facts and experimental analysis | `domain.py`, `features.py`, `scoring.py` | No I/O adapters; unchanged from the tracked foundation |
| State transitions and immutable storage | Flyway V1 under `api/src/main/resources/db/migration/` | Reader views only; publisher has no schema/header mutation rights |
| Search/pool/cursor semantics | Java `catalog` capability | Calls only public `snapshots.SnapshotService` across the capability boundary |
| Snapshot identity/provenance/readiness | Java `snapshots` capability | Does not reach into catalog query internals |
| Interaction and presentation | `web/src/app/`, `web/src/components/` | Typed Java API entry, no Python/DB/MTG source calls |

`scripts/check_boundaries.py` checks these actual imports and cycles. Private
Java repository visibility adds a compile-time boundary. Record DTOs are generated
into TypeScript through live Spring OpenAPI; no separate hand-maintained web DTOs
or score formula exist. Source normalization is not repeated as Java ingestion.

## Publication design and recovery

The selected design remains the ADR's explicit PostgreSQL schema and JDBC read
path. File-backed querying would avoid a database process but require a second
solution for indexed pools, concurrent publication and stable readers. An ORM,
queue or independent Python request service would add machinery without helping
this bounded read path. Revisit storage/query indexes after representative scale
measurements, not because the sample is fast.

Dataset identity differs from attempt identity. A dedicated connection owns a
session advisory lock; a short transaction persists the staging header/attempt,
and the next transaction loads, validates, promotes and changes the active pointer.
Failure rolls back that transaction and records a stable attempt failure separately.
Published rows cannot be updated/deleted by the publisher role. The previous
published snapshot remains addressable after promotion and explicit rollback.

The artifact validator streams tables, validates row schemas and preserves compact
identity indexes for cross-table checks. Exported analytical Parquet has separate
hashes; the public serving manifest retains the agreed closed v1 shape. The input
JSON hash is rechecked after loading to detect a changed artifact before promotion.
No constant-memory or full-bulk-throughput claim follows from streaming parsing.

The ADR's context, identity/entity table and publication sequence diagram correspond
to the delivered migration and adapters. The runbook gives failure/retry/rollback
commands. Broader retention, restore and operational stress work remains later scope.

## Change scenario: extend a printing filter

The delivered game filter is the representative extension to set/rarity filtering.
Its value is normalized/validated in `CatalogQuery`, added once to the repository's
shared printing predicate, included in cursor filter identity, described by Spring
OpenAPI and offered in the guest form. Both search counts and printing pages use
that same predicate. Normalization, publication orchestration and analytical
features need no rewrite because `games` already belongs to each printing.

For a future language filter, the same extension points would apply. A new query
parameter and cursor fingerprint require explicit contract evolution and consumer
regeneration. It would be incorrect to filter Oracle representatives by language
or apply a second independent printing EXISTS condition. The actual joint-printing
counterexample and shared predicates make this consequence reviewable.

Review also found that preset-only controls could lose valid shareable URL values.
The UI now represents all color combinations and retains unknown well-formed set
codes and arbitrary valid page sizes returned through a successful query. Java
still decides validity and eligibility; the UI only preserves presentation state.

## Change scenario: diagnose a failed refresh

The reader need not know whether the publisher failed schema validation, lost a
connection or encountered stale promotion. It continues to resolve the active
published pointer. Operators start from the logged dataset/attempt ID, inspect the
stable attempt code and source/export checksums, correct the new batch and retry.
No recovery step requires editing published rows. The tests pause an import while
a reader verifies old data, inject failure, check staging invisibility, and prove
retry/serialization/abandonment behavior on PostgreSQL itself.

Two Windows setup defects were found through execution: the running JAR blocked
Maven repackaging, and a persistent PostgreSQL child inherited a redirected output
pipe. The runner now launches a per-run JAR copy and detaches PostgreSQL's standard
handles into its startup log. Cold start was exercised after stopping only this
task's preview/runtime; the setup process returned normally and retained data.

## Measurement and verification interpretation

See [the status report](project-status-report.md) for the criterion matrix and
[recorded measurements](evidence/milestone2/measurements-windows.json) for conditions,
raw query plan and resource values. The observed warm p95 is about **8.3 ms** for
100 loopback catalog requests at 20 workers over seven cards, with zero errors.
This is integration evidence, not proof of the proposed full-catalog 300 ms target.
The plan uses the ordinary B-tree `card_name_page`, `printing_pool` and snapshot
primary-key indexes; no GIN, trigram index or cache is justified by this sample alone.

The final clean environment passed Python, Java, TypeScript, formatting, contract,
database and browser checks. Axe and visual inspection covered desktop discovery
and narrow discovery/detail/dataset/error views. Automated checks do not establish
screen-reader usability on every platform. Remote GitHub Actions, a full catalog,
tournament statistics, deployment, cost, backup restore and public licensing were
not verified or claimed. No milestone-3 work was started.
