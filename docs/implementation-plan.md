# Implementation plan

**Current position: milestone 2 is complete locally; milestone 3 is next.**
Completion evidence and remaining verification limits are in the
[project status report](project-status-report.md), updated 2026-09-08.

| Milestone | Status | Result |
| --- | --- | --- |
| 1. Data feasibility and contracts | Catalog groundwork delivered; tournament questions open | Reviewed source sample, ownership decisions, data/API/UX contracts |
| 2. Local catalog | Complete | Python → PostgreSQL → Spring API → Next.js catalog |
| 3. Tournament evidence | Next | Statistics traceable to source records and eligible observations |
| 4. Publication and query reliability | Planned; atomic publication already implemented | Representative load measurements and operational recovery |
| 5. Portfolio release | Planned | Public guest application, deployment evidence, demo and case study |

Read [milestone 3](#milestone-3-traceable-tournament-evidence) for the next work.
The completed catalog checklist and older roadmaps are expandable references below.

## Active delivery sequence (2026-09-07)

These documents have distinct roles:

- **This plan:** delivery order, scope, and completion requirements.
- **[Portfolio plan](portfolio-plan.md), section 6:** design and engineering-quality
  requirements for every increment.
- **[Measurement contract](measurement-contract.md):** the meaning of analytical
  features and scores.
- **[ADR 0002](adr/0002-catalog-publication-and-delivery-order.md):** why catalog and
  browser delivery moved earlier than the old roadmap. Python still owns ingestion,
  features, and scoring.

### Milestone 1: data feasibility and contracts

**Delivered:** [data feasibility](data-feasibility.md),
[domain and ownership decisions](adr/0002-catalog-publication-and-delivery-order.md),
[publication/API/UX contract](catalog-contract.md), and machine-readable schemas
with offline checks in `contracts/`.

**Still open:** TopDeck access, tournament cohort and coverage, and corpus
redistribution. The reviewed real sample establishes catalog feasibility only.

### Milestone 2: catalog from ingestion to local browser

**Delivered journey:** a documented, bounded real Scryfall sample → Python
normalization that preserves card faces → immutable export → atomic PostgreSQL
publication → Spring JDBC catalog/snapshot APIs → Next.js discovery, detail, and
dataset pages.

**Completion requirements:** a fresh checkout runs the seeded local demo without
production credentials or a TopDeck key; deterministic CI exercises Python →
PostgreSQL → Java → browser. Use `catalog-publication-v1` and the catalog HTTP
contract proposed for this milestone. Deliver reproducible run commands, a reviewed
diff, and documented limits. See the status report for actual verification evidence.

**Scope limits:** preserve existing user work. This milestone does not authorize
commits, pushes, deployment, purchases, accounts, research-score serving, destructive
host changes, or paid infrastructure. A hosted preview needs separate provider and
budget authorization.

<details>
<summary>Completed milestone 2: all eight acceptance checks and dependencies</summary>

### Dependency-ordered implementation checklist

For **every item**, review the design and diff against portfolio section 6,
refactor where appropriate, and update documentation. Complete one representative
path before generalizing. The [status report](project-status-report.md) maps these
original requirements to evidence.

**1. Toolchain and seed — no dependency**

- Pin Python dependency resolutions, JDK 21, and supported Node/package-manager
  versions. Use strict TypeScript, Java formatting/static checks, and Ruff.
- Document commands usable on other machines. A fresh environment must install
  and pass existing checks.
- Choose a small real-derived seed with source hashes, attribution, and a sample
  label. Keep synthetic adversarial fixtures separate.

**2. Card normalization — requires 1**

- Preserve raw snapshots/provenance, deterministic representative selection,
  complete faces, alias collisions, null versus empty values, printing images,
  and game metadata as specified by the contract. Do not change score formulas.
- The real sample must produce 7 Oracle-card rows and 8 printing rows, retaining
  face text.
- Test missing-Oracle-ID quarantine; multi-face, unknown, and reversible layouts;
  conflicting printings; literal/ambiguous aliases; and deterministic replay.

**3. Export and manifest — requires 2**

- Produce versioned artifacts with exact checksums, row counts, and exclusions.
  Reject schema drift, non-finite values, and invalid references.
- Finalize files atomically. Test interrupted downloads, checksum corruption,
  failed normalization, and reruns: none may leave a successful partial manifest.
  Preserve the last valid artifact on failure.
- Keep the probe script outside normal CI.

**4. PostgreSQL schema and publisher — requires 1 and 3**

- The API owns Flyway migrations, publication transition functions, and roles.
  Python stages, validates, and promotes data using one locked connection.
- Use real PostgreSQL tests for same-ID/different-content rejection, idempotent
  replay, failure rollback, old-snapshot visibility, hidden staging data, and
  serialized publishers.
- Pause before promotion and confirm a reader still sees old data. Test role
  permissions and recovery of abandoned publication attempts.

**5. Spring catalog/snapshot API — requires 4**

- Implement the proposed endpoints with parameterized JDBC, bounded input,
  deterministic keyset cursors, and sanitized Problem Details errors.
- Test the joint-printing counterexample (filters must match one printing),
  colorless/unknown identity, alias search, literal wildcards, empty results
  versus failures, unknown IDs, cursor tampering/mismatch, and pagination across
  publication promotion.
- HTTP requests must not call external sources or Python. Application info lists
  only delivered capabilities; generated OpenAPI must match actual HTTP behavior.

**6. Three guest web views — requires 5**

- Generate the TypeScript client from implemented Spring OpenAPI. Do not duplicate
  DTO definitions or formula rules.
- Implement the wireframe with responsive native controls, keyboard focus, and
  loading, empty, error, and retry states. Text-first card rendering is acceptable.
- Browser tests use accessible locators to filter, open faces/printings, follow
  dataset identity, copy/reopen a snapshot-pinned URL, and paginate after refresh
  without mixing snapshots. The browser must not fetch from MTG sources.

**7. Integrated verification — requires 4–6**

- Provide one documented, cross-platform setup/verify entry point, a disposable
  local database, and a versioned seed.
- CI publishes Python fixtures into real PostgreSQL, serves them through Java,
  and tests the guest browser without live MTG calls. H2 cannot substitute for
  transaction/query verification.
- Check actual Python/Java module boundaries and TypeScript client imports.

**8. Review, measurement, and handoff — requires 7**

- Run clean-install, build, and language checks once. Inspect the final tracked
  and untracked diff; record runtime, dataset, query plans, and import resources.
- A tiny seed proves integration only. Mark full-scale latency/memory unverified
  until measured on bulk data.
- Review a filter extension and a failed-refresh diagnosis scenario. Document
  startup, retry, and pointer rollback; hand off the local preview and remaining debt.

**Rules across checks:** items 2–6 preserve the measurement contract even without
served empirical results. Unknown evidence is not zero; filtering a card pool
does not change the cohort; current metadata cannot establish historical legality.
Basic recovery and concurrency tests belong here, not in a later cleanup.

**Original runtime gate:** if real PostgreSQL tests cannot run, complete independent
work and report the blocker; do not mark the milestone complete. Docker/psql were
absent from PATH at milestone 1, so inspect available runtimes before choosing a
test service.

</details>

### Later milestones and decision gates

#### Milestone 3: traceable tournament evidence

1. Resume the bounded probe in the [feasibility report](data-feasibility.md), using
   configured credentials or a permitted curated real corpus.
2. Evaluate coverage, card resolution, deck zones, and reuse permissions before
   choosing the cohort (the group of events/decks being analyzed).
3. Fix how incomplete standings affect denominators before computing measured
   features.
4. Publish raw observations and versioned eligibility rules owned by Python.
   Produce a useful report before serving scores through the API.

**Done when:** every displayed statistic can be rebuilt from its exact source,
stratum (analysis group), and denominator. The earlier
[tournament-slice deliverables](#next-analytical-increment-first-tournament-vertical-slice)
are retained in the historical reference below; the source/cohort gates above take
precedence.

#### Milestone 4: publication and query reliability

Extend the existing atomic publication protocol with representative bulk/load
measurements, failure injection, operational logging, readiness, retention, and
tested rollback/restore.

**Done when:** recorded results include their test conditions. Fixture tests alone
cannot establish performance at larger scale.

#### Milestone 5: portfolio release

Complete accessibility/mobile review, owner-approved hosting and licensing,
deployment and restore exercises, measured cost/performance, an accurate README,
a demo, and a case study. Retain public guest access; authentication is later scope.

**Release gate:** the reviews, approvals, exercises, measurements, and presentation
materials above are complete.

<details>
<summary>Historical reference: foundation changes and superseded roadmaps (preserved in full)</summary>

### Historical foundation and superseded roadmap

The sections below preserve earlier foundation history and research intent.
Their "next", database and React ordering is superseded by the active sequence
above and ADR 0002. They do not authorize a second analytical implementation.

This plan records the critique incorporated after the foundation release and
keeps deferred work explicit.

The two executable components have independent build roots: Python analytics in
`analytics/` and the Java product API in `api/`. Repository-level documentation
and CI remain at the root.

## Implemented in foundation v2

- Replaced scalar event coverage with independent decklist, standings, and match
  coverage dimensions.
- Added mandatory provenance with immutable snapshot references and parser
  versions.
- Separated registered decks, standings, and round-level matches.
- Added Oracle-card and printing identities so scoring can remain Oracle-level
  while Forge filters retain set and rarity information.
- Moved analytical features out of the factual domain layer.
- Made every semantic feature missing-aware and support-bearing.
- Renamed the internal engine estimate to **Build-around Signal** to avoid a
  causal claim unsupported by decklists alone.
- Added complete score identity: dataset snapshot, feature pipeline version,
  model version, and configuration hash.
- Recast Engine-minus-Staple as a descriptive Distinctiveness Delta rather than
  the default ranking objective.
- Added an immutable Scryfall default-cards downloader and a streaming
  canonicalizer that emits Oracle-card and printing Parquet tables.
- Added Ruff lint and formatting checks to CI.

## Implemented: API skeleton and Swagger

- Added an independent Java 21/Spring Boot application under `api/`.
- Added Maven Wrapper, generated OpenAPI and Swagger UI, health, and application
  info with build-derived version and implemented capabilities.
- Established Problem Details errors and real HTTP integration tests.
- Added Java build/test CI alongside the unchanged Python checks.
- No database, authentication, catalog, snapshot, or score endpoints were added.

The next product increment is real catalog and snapshot serving from
Python-published data. The next analytical increment remains the tournament slice
below; neither requires Java to duplicate scoring or ingestion logic.

## Next analytical increment: first tournament vertical slice

Use one bounded format and era from TopDeck rather than attempting historical
breadth immediately.

Deliverables:

1. API client with explicit rate-limit handling and no committed credentials.
2. Immutable bronze payloads and manifests.
3. Normalized tournaments, decks, standings, and matches.
4. Measured coverage profiles for every event.
5. Idempotent fixture-backed adapter tests.
6. Attribution metadata for the eventual user interface.
7. Baseline incidence, commitment, competitive-proof, and coverage features.
8. A CSV or terminal report showing scores, evidence, feature coverage, and raw
   reasons.

## Subsequent research increments

1. Add explicit card-pool and historical-legality snapshots.
2. Compute independent format-era strata and cross-era recurrence.
3. Introduce empirical deck-family clustering.
4. Add regularized pairwise association and package fingerprints.
5. Build a sentinel-card regression harness.
6. Calibrate model transformations and weights against observed failures.
7. Materialize stable, versioned gold tables for publication.
8. Introduce PostgreSQL when concurrent serving and indexed product queries
   justify an operational database.
9. Extend the Java 21/Spring Boot API for search, filters, score explanations, user
   collections, and saved searches.
10. Add a TypeScript/React interface with Next.js only after the vertical slice
    produces useful explanations.

## Product application sequence

The API skeleton establishes HTTP conventions now; business behavior follows
available published data, and score serving still requires analytical proof. See
[ADR 0001](adr/0001-polyglot-application-boundary.md) for the language boundary.

### 1. API skeleton and Swagger (implemented)

Provide a runnable application, `/api/v1/info`, `/actuator/health`, `/v3/api-docs`,
and Swagger UI. Keep the specification aligned with implemented endpoints and
leave speculative business routes out. No database is needed for this step.

### 2. Serve the real catalog

Define a versioned publication contract for the existing Python-produced card
catalog. Then add paginated card search, Oracle-card detail with printings, and
available snapshot metadata. Do not fetch Scryfall during an HTTP request.

### 3. Publish one useful score snapshot

Python computes a bounded, reproducible score snapshot and its explanations.
DuckDB and Parquet remain the analytical substrate. Before score endpoints exist,
the snapshot must already be useful as a CSV or terminal report.

### 4. Define the score publication contract

Create versioned PostgreSQL gold tables for cards, score snapshots, feature
observations, explanations, and package memberships. Publishing a new snapshot is
an explicit batch operation; an HTTP request never starts the Python pipeline.

### 5. Extend the Java API

Extend the Java 21/Spring Boot application around stable product queries:

- card search and Forge-oriented filters;
- independent Staple, Build-around, Evidence, and Distinctiveness ordering;
- score explanations and snapshot identity;
- owned-card collections, saved searches, and prospective deck packages;
- authentication, validation, and transactional product state.

The API consumes published results. It does not reimplement experimental feature
engineering or scoring.

### 6. Add the React interface

Introduce a TypeScript/React application using Next.js for routing, public page
metadata, and server rendering where useful. Its first vertical slice is card
discovery plus a score explanation—not a broad dashboard shell.

The browser calls a versioned Spring Boot API and never connects directly to
PostgreSQL, Parquet files, or external MTG sources.

</details>

## Deliberately unresolved

- The legal license for outside reuse. Choosing MIT, Apache-2.0, GPL, or another
  license is an owner decision, not a mechanical repository cleanup.
- The first historical corpus with sufficient depth beyond TopDeck.
- The exact clustering algorithm and association statistic.
- The product ranking above the two-dimensional score surface.
- Whether causal engine classification should incorporate card text, curated
  labels, deck variants, or all three.
- The deployment provider and authentication mechanism for the future product
  applications.
