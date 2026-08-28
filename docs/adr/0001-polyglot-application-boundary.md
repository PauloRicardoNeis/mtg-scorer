# ADR 0001: Polyglot application boundary

- **Status:** Accepted for the planned product layer
- **Date:** 2026-08-28

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
| Analytical pipeline | Python | ingestion, feature research, model evaluation, batch scoring, explanations |
| Analytical store | Parquet and DuckDB | immutable snapshots, scans, aggregations, exploratory queries |
| Serving store | PostgreSQL | published gold tables, snapshot identity, user and product state |
| Product API | Java 21 and Spring Boot | search, filtering, validation, authentication, collections, saved searches |
| Web interface | TypeScript, React, and Next.js | discovery flows, score inspection, Forge-oriented interaction |

Python publishes immutable, versioned results. Spring Boot reads those results and
adds transactional product behavior. Next.js communicates with Spring Boot through
a versioned HTTP contract.

## Invariants

1. An application request never invokes the Python runtime.
2. The browser never connects directly to PostgreSQL, Parquet, DuckDB, or an
   external data source.
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

1. Produce one credible score snapshot with Python.
2. Stabilize and test the publication schema.
3. Add the narrow Spring Boot read API.
4. Add the first Next.js discovery and explanation screen.
5. Introduce authentication and mutable user features only when the read path is
   already useful.

This sequencing keeps the language boundary congruent with a proven data boundary
instead of creating three empty applications in anticipation of future work.
