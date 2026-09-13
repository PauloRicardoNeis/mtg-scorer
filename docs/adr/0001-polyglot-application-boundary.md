# ADR 0001: Polyglot application boundary

- **Status:** Accepted; catalog publication/API/guest browser implemented in milestone 2
- **Date:** 2026-08-28

**2026-09-07 amendment:** [ADR 0002](0002-catalog-publication-and-delivery-order.md)
supersedes the sequencing below by delivering the catalog browser before scores.
It clarifies invariant 5: catalog facts retain catalog/source/parser identity;
the full feature/model/configuration identity applies to analytical results.
Language ownership and all other measurement/publication invariants remain intact.

**2026-09-13 image delivery amendment:** The catalog browser may load card scans
directly from the image URLs already published by Python and returned by Java.
This is a narrow exception to invariant 2 for image delivery: the browser does
not query the Scryfall API or other external data APIs. Search previews use the
same jointly eligible printings as the Java query; details retain source face
order and artist attribution. Image bytes are not stored in the snapshot, so
availability depends on the image host; missing or failed images show a fallback.

## Context

MTG Scorer combines two workloads with different rates of change.

The analytical workload ingests heterogeneous historical sources, profiles data,
tests statistical transformations, calibrates score models, and performs batch
aggregation. Its definitions are still volatile and benefit from Python's data
and scientific ecosystem.

The eventual product workload serves stable searches, filters, explanations,
collections, and authenticated user state. It benefits from a strongly typed,
durable service boundary and aligns with Java/Spring expertise. The public
interface needs an interactive React application and useful server-rendered entry
pages.

A mixed-language system becomes harmful when the boundary is a function call or
when two implementations silently diverge. The decision must therefore allocate
ownership, not merely list preferred technologies.

## Decision

Use a polyglot product architecture with the following ownership:

| Component | Technology | Owns |
| --- | --- | --- |
| Analytical pipeline (`analytics/`) | Python | ingestion, feature research, model evaluation, batch scoring, explanations |
| Analytical store | Parquet and DuckDB | immutable snapshots, scans, aggregations, exploratory queries |
| Serving store | PostgreSQL | published gold tables, snapshot identity, user and product state |
| Product API (`api/`) | Java 21 and Spring Boot | search, filtering, validation, authentication, collections, saved searches |
| Web interface | TypeScript, React, and Next.js | discovery flows, score inspection, Forge-oriented interaction |

Python publishes immutable, versioned results. Spring Boot reads those results and
adds transactional product behavior. Next.js communicates with Spring Boot through
a versioned HTTP contract.

## Invariants

1. An application request never invokes the Python runtime.
2. The browser never connects directly to PostgreSQL, Parquet, DuckDB, or an
   external data source, except published card image URLs as described above.
3. Python is the single owner of experimental feature and scoring semantics.
4. Java does not independently reproduce a score formula. If real-time scoring is
   later required, it needs a separately reviewed contract and cross-language
   conformance tests.
5. Every published row remains attributable to a dataset snapshot, feature
   pipeline version, score model version, and score configuration hash.
6. A failed or incomplete batch publication cannot mutate the currently served
   snapshot in place.

## Data exchange

The preferred production boundary is a versioned PostgreSQL publication schema.
Immutable Parquet artifacts remain a valid interchange format for offline work and
reproducibility.

Publication should stage a complete snapshot, validate row counts and referential
integrity, and then atomically promote its identifier. The API selects an explicit
published snapshot rather than inferring "latest" from partially written rows.

## Why not all Python?

An all-Python system would be viable and initially smaller. It was rejected as the
planned product architecture because the API's responsibilities are operational
and transactional rather than analytical, and Java/Spring provides a useful,
durable product boundary without forcing the research pipeline out of its strongest
ecosystem.

## Why not all Java?

Java can ingest JSON, operate DuckDB, and write Parquet. The objection is not
capability or throughput. During model discovery, Python provides substantially
less friction for statistical inspection, calibration, clustering, notebooks, and
the wider scientific library ecosystem. Moving that volatile work to Java would
purchase structure before the correct structure is known.

## Why not a Python microservice?

A synchronous Python scoring service would add network and deployment failure
modes without serving a current requirement. Scores are batch-derived and can be
published ahead of requests. A separate modeling service becomes warranted only if
the product later requires genuinely request-specific computation that cannot be
precomputed.

## Sequencing

1. Add a narrow Java 21/Spring Boot skeleton with generated OpenAPI, Swagger UI,
   health, application info, consistent errors, and tests. This step is complete
   and needs no database or Python runtime.
2. Add real catalog and snapshot endpoints over data published by Python.
3. Produce one credible empirical score snapshot and report with Python.
4. Stabilize and test the score publication schema before adding score endpoints.
5. Add the first Next.js discovery and explanation screen.
6. Introduce authentication and mutable user features only when the read path is
   already useful.

The sequence was revised on 2026-08-28 to establish a runnable API and HTTP
conventions earlier. This does not change analytical ownership or justify mock
scores: Swagger describes implemented behavior, and score serving still depends
on a proven publication contract.
