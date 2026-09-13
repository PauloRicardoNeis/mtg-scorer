# MTG Scorer: progress, remaining work and next milestones

Status snapshot: 2026-09-07 local / 2026-09-08 UTC, following milestone 1.

**The project has a working Python foundation, a working Java API skeleton, and
an executable design contract for the first catalog application. It does not yet
have a catalog API, PostgreSQL publication, a browser application, or verified
tournament evidence.** The next implementation milestone is the local catalog
journey from ingestion to browser.

This is the consolidated progress report. The
[active implementation plan](implementation-plan.md#active-delivery-sequence-2026-09-07)
is the authoritative execution checklist; the
[portfolio plan](portfolio-plan.md) defines delivery direction and engineering
acceptance criteria. This report records status rather than introducing another
competing roadmap.

## Milestone 2 checkpoint log

### Checkpoint 1 - real seed and immutable face-aware export (2026-09-08)

- Preserved the pre-existing migration, tracked changes and untracked applications.
- Added the exact eight retained Scryfall responses under `analytics/seeds/`, with
  original source manifest/hashes and sample attribution. No live source in CI.
- Added deterministic Python normalization and shared executable validation;
  serving JSON plus face-aware Parquet finalize in one directory rename.
- Verified 7 cards / 8 printings / 10 faces / 17 aliases, null-vs-empty, aliases,
  representatives, corrupt raw/export rejection, failed normalization preservation,
  replay and concurrent export. Python: 26 passed; offline contracts: 6 passed.
- Resolved Python dependencies in `analytics/uv.lock`; local Python 3.12.10,
  Node 24.14.1/npm 11.11.0 and Temurin JDK 21 are available.
- Downloaded EDB PostgreSQL 17.11 portable binaries into ignored `.local/tools`;
  isolated database runs at 127.0.0.1:55432. Archive SHA-256:
  `4b8db0930c38f6ef845db919551dedda3b6b845aeb0927b3d79a6e8e9e4537cf`.
- Review: source projection owns layout/name rules; export owns files/validation.
  Analytical domain/features/scoring unchanged. No empirical claims added.
- Remaining: publication/permissions/concurrency, API, browser, integrated setup/CI,
  legacy bulk interruption tests, final language checks and measured handoff.

### Checkpoint 2 - PostgreSQL publication (2026-09-08)

- Added API-owned SQL migration: snapshot-scoped keys, same-card deferred printing
  FK, published views, restricted reader/publisher roles, protected transition
  functions and immutable published rows.
- Python now holds one dedicated advisory-locked connection across attempt/load/
  promotion; validates immutable source/export bytes before publication.
- Five real PostgreSQL tests passed (17.11, isolated `mtg_catalog_test`): integrity,
  idempotency and conflict; role denial; failed-load rollback and retry; concurrent
  publisher serialization with an old-snapshot reader paused before promotion;
  abandoned-attempt recovery; invalid FK rejection; guarded pointer rollback.
- Review: API owns SQL/schema; Python owns publication orchestration. Attempts are
  distinct from dataset IDs. Failure diagnostics retain stable codes and IDs.
- Remaining: validate Flyway startup and Java query behavior, complete OpenAPI and
  browser views, deterministic integrated runner/CI, final static checks/review.

### Checkpoint 3 - Spring and guest browser reference slice (2026-09-08)

- Flyway applied V1 successfully to a fresh real PostgreSQL demo database.
- Spring now serves cards, face detail, eligible printings and retained snapshots;
  strict query parsing and snapshot/filter/resource-bound keyset cursors are implemented.
- Maven verification passed (10 existing HTTP tests, now covering current routes),
  Spotless and JDK 21 enforcement passed. Additional query tests await the final run.
- Three Python -> PostgreSQL -> running Java HTTP checks passed, including literal
  search, joint printing counterexample and both pagination resources across promotion.
- Next.js discovery/detail/dataset routes now consume types generated from live
  Spring OpenAPI. Strict TypeScript and optimized production build passed.
- Four Chromium browser tests passed: guest filters/faces/dataset, clipboard and
  reopened pinned URL, Back/empty state, pagination after Python refresh, mobile
  layout and retry after an actual database permission fault. Axe found zero
  violations on tested discovery/detail/dataset/error views. Mobile screenshot reviewed.
- Initial browser failures were test synchronization mistakes (capturing the URL
  before navigation completed); fixed with observable URL waits. No sleeps/retries.
- Remaining: a fresh reproducible integration runner and CI, full edge-case tests
  (including explicit loading and unknown/colorless identity), dependency checks,
  legacy ingestion recovery, measurements, final correctness review and runbook.

## 1. What was already implemented before this milestone

These components existed in the checkout when this work began. They were inspected
and tested; milestone 1 did not implement them from scratch.

| Area | Implemented | Still missing |
| --- | --- | --- |
| Python factual model | Oracle cards and printings; tournaments, registered decks, standings and matches; provenance; independent decklist/standing/match coverage | Real tournament adapter and corpus; complete source-to-domain mappings |
| Analytical foundation | Missing-aware feature containers, provisional scoring and computational identity | Empirical feature computation, calibrated eligibility and evaluated recommendation quality |
| Scryfall ingestion | Raw download/checksum handling; JSON/JSONL/gzip parsing; Oracle and printing Parquet output | Face-aware normalization, aliases, image references, broader layout handling and robust failure/concurrency tests |
| Java API | Java 21/Spring Boot; application info, health, generated OpenAPI, Swagger UI, sanitized Problem Details and HTTP tests | Database, catalog/search/detail/snapshot/evidence endpoints |
| Build structure | Independent `analytics/` and `api/`; Maven Wrapper and root aggregator; Python and Java CI jobs | Fully pinned onboarding across languages, web tooling and integrated publication-to-browser CI |

Existing executable API routes include `/api/v1/info`, `/actuator/health`,
`/v3/api-docs` and Swagger UI. The proposed catalog routes are not available yet.
Existing numerical research scores are not evidence of competitive usefulness.

The working tree also contained an unfinished structural migration: deleted old
root Python paths and untracked `analytics/`, `api/` and Maven files. This work
preserved that state. The complete working tree still requires review before any
future commit; the visible diff includes work that predates this milestone.

## 2. What we completed in milestone 1

### Inspection and baseline verification

- Read the portfolio plan, measurement contract, implementation plan and ADR 0001.
- Inspected the checkout, including modified, deleted and untracked files.
- Verified the Python and Java baseline and documented local runtime differences.
- Checked the available project credential locations without printing secrets.
- Preserved application source and analytical formulas.

### Real-data feasibility investigation

We retrieved and retained a bounded real Scryfall sample: **8 printings, 7 Oracle
cards and 7 layouts**, totaling **49,570 raw bytes**. The layouts were normal,
transform, split, adventure, modal double-faced, flip and meld.

We ran the existing normalizer on those exact bytes. It produced 7 Oracle rows,
8 printing rows and no skipped records, but exposed concrete product gaps:

- Five canonical cards lost text stored on their faces.
- Delver of Secrets and Valakut Awakening projected empty colors despite having
  colored faces.
- Layout, face, image-reference and alias data are not currently exported.
- Lightning Bolt is common in M11 and uncommon in 2X2. This demonstrates why set
  and rarity constraints must be satisfied by the same printing.

We also retrieved the live bulk descriptor. It advertised a compressed JSONL file
of 78,058,821 bytes. That is source metadata, not a measured download or import;
the full bulk file was not downloaded.

The sample confirms catalog access and specific normalization defects. It does
not establish complete layout coverage, full-catalog performance, deck-name
resolution quality or tournament feasibility. See the
[detailed findings](data-feasibility.md) for requests, timestamps, limitations and
the unsuccessful preliminary lookup that was corrected.

### Decisions and contracts

We explicitly reconciled the roadmap conflicts:

- PostgreSQL and the first Next.js catalog flow now come before empirical scores.
- Python retains ingestion, normalization, feature, scoring and explanation ownership.
- Java owns product queries/filtering, API validation and database migrations.
- Next.js owns interaction and presentation through the Java API.
- Catalog facts carry catalog/source/parser identity. Analytical results retain
  the full measurement identity; no fictitious score version is attached to cards.
- Catalog v1 serves no scores or tournament rankings. Unknown evidence is not zero.
- Hosted preview is separated from the next local milestone under the current
  no-deployment instruction.

We defined the domain vocabulary, publication states and ownership, schema/table
mapping, exact manifest fields, atomic promotion/retry/rollback rules, filtering,
pagination, errors and future evidence-eligibility proposal. Three wireframes cover
discovery, card detail and dataset/methodology. These are implementable design
artifacts; the database transactions and screens themselves are still future work.

### Deliverable inventory

| Artifact | Purpose |
| --- | --- |
| [Data feasibility report](data-feasibility.md) | Source sample, measured defects, baseline evidence, data policy and dependencies |
| [ADR 0002](adr/0002-catalog-publication-and-delivery-order.md) | Roadmap reconciliation, domain/ownership map, architecture and publication protocol |
| [Catalog contract](catalog-contract.md) | Normalization, PostgreSQL mapping, API semantics, wireframes, workload assumptions and verification requirements |
| [Publication schema](../contracts/catalog-publication.schema.json) | Machine-readable catalog fields, types and nullability |
| [Manifest schema](../contracts/catalog-manifest.schema.json) | Export version, identity, checksums, sizes and row-count contract |
| [Proposed OpenAPI](../contracts/catalog-api.openapi.json) | Initial search, detail, printing and snapshot HTTP contract; explicitly not implemented server routes |
| [Synthetic catalog fixture](../contracts/fixtures/catalog-valid.json) and [response fixture](../contracts/fixtures/card-page.json) | Offline conformance examples, clearly separate from real-data evidence |
| [Contract verifier](../scripts/verify_contracts.py) | Executable validation and adverse cases for schemas, references, missingness and export integrity |
| [Contract tool requirements](../contracts/requirements.txt) | Pinned direct dependencies for contract validation |
| [Catalog probe](../scripts/probe_catalog.py) | Opt-in bounded live sample collection; excluded from normal CI |
| [Sample evidence](evidence/catalog-sample.json) and [bulk descriptor evidence](evidence/scryfall-bulk-metadata.json) | Portable IDs, request URLs, hashes, timestamps and observed metadata |
| [Active implementation plan](implementation-plan.md) | Dependency-ordered acceptance checklist and next autonomous goal |

We also updated README navigation, annotated ADR 0001 and the portfolio proposal
with the adopted direction, and added an offline contract CI job while preserving
the existing Python/Java jobs. Original raw sample files remain in ignored local
storage under `analytics/data/local/feasibility-20260908T0050Z/`.

## 3. What was verified, and what was not

These are results from the milestone-1 work in this conversation. Creating this
consolidated report does not imply a fresh rerun of the application tests.

| Verification | Result |
| --- | --- |
| Existing Python tests | 20 passed |
| Java Maven verification with JDK 21, offline | Build succeeded; 10 HTTP tests passed |
| New offline contract suite | 6 tests passed, including invalid-input subcases |
| Ruff lint and formatting | Passed for analytics and the new scripts |
| Sample integrity | All 8 retained raw response hashes matched the evidence manifest |
| Local documentation links / CI YAML structure | Checked successfully |
| Tracked diff whitespace check | Passed; existing CRLF conversion warnings remain informational |
| GitHub Actions execution | Not run remotely; the job was added and its local commands passed |
| PostgreSQL transactions / permissions / concurrency | Not implemented or tested |
| Cross-language publication integration / browser journeys | Not implemented or tested |
| Full catalog throughput, memory, latency or operating cost | Not measured |
| Authenticated tournament access / empirical scoring quality | Not verified |
| Deployment, backup restore or hosted preview | Not performed |

## 4. What is still missing and what it blocks

| Missing work or dependency | Consequence | When to resolve |
| --- | --- | --- |
| Face-aware catalog normalization | Current output cannot render reliable multi-face detail | Start of milestone 2 |
| Production serving exporter and manifest handling | Schemas exist, but no pipeline produces the final publication yet | Milestone 2 |
| PostgreSQL runtime, migrations, roles and publisher | No durable serving store or proven atomic publication | Milestone 2; Docker/psql were not on PATH during inspection |
| Catalog API and stable cursors | No card search/detail/filtering through Java | Milestone 2 |
| Next.js app and generated API client | No guest browser journey | Milestone 2 |
| Local seed/setup and integrated CI | A new checkout cannot yet start the full demo | Milestone 2 |
| TopDeck credential or permitted real alternative | No tournament sample, chosen cohort or coverage/resolution findings | Before milestone 3; does not block catalog work |
| Tournament corpus redistribution terms | Cannot claim a public deck/evidence dataset is cleared for reuse | Before public evidence delivery |
| Complete standing-denominator semantics | Partially known wins/losses/draws must not become a complete match total | Before tournament feature computation |
| Measured observations and evaluated public eligibility | Cannot responsibly expose competitive recommendations | Milestone 3 |
| Bulk profiling, operational visibility and recovery exercises | No evidence of scale or operational reliability | Broader milestone 4 work; core failure/atomicity tests already belong in milestone 2 |
| Code license, hosting provider and budget | Public release choices remain open | Before deployment/release |
| Accessibility/mobile review and portfolio materials | No finished showcase or evidence-backed case study | Milestone 5 |

No TopDeck credential was found in the environment/project dotenv locations
checked. Other secret stores were not inspected. We did not query authenticated
tournament endpoints, select an empirical cohort, or invent missing observations.

## 5. Milestones from here

| Milestone | Current status | What completion looks like |
| --- | --- | --- |
| **1. Data feasibility and product contract** | Catalog investigation and contract package delivered; tournament feasibility gate unresolved | Catalog implementation can proceed. A chosen tournament cohort and its coverage/resolution report remain pending access. |
| **2. Catalog from ingestion to local browser — next** | Not implemented | A real bounded seed travels through Python, PostgreSQL and Spring into three guest Next.js views; filtering, faces, pinned URLs, atomic publication and integrated tests work. |
| **3. Traceable tournament evidence** | Not implemented; source-dependent | One permitted bounded corpus yields reproducible observations, independent coverage, resolved cards, honest eligibility states and source-linked evidence in the application. |
| **4. Publication and query reliability** | Not implemented | Representative load/import measurements, diagnosable failed refreshes, retention, rollback and restore exercises support operational claims. |
| **5. Portfolio release** | Not implemented | Accessible/mobile guest flow, approved deployment, measured cost/performance, reproducible onboarding, README/demo and engineering case study describe delivered behavior. |

The detailed milestone-2 order is:

1. Pin toolchains and establish the real seed policy.
2. Fix normalization with the reviewed layouts and adversarial cases.
3. Implement serving export and manifest integrity.
4. Implement and test PostgreSQL publication.
5. Implement the Spring catalog/snapshot API.
6. Build discovery, detail and dataset pages.
7. Connect deterministic publication-to-browser verification.
8. Review the full slice, record measured limits and document local operation.

Each step's dependencies, observable acceptance criteria and required tests are in
the [implementation checklist](implementation-plan.md#dependency-ordered-implementation-checklist).
No delivery deadline has been agreed; earlier effort ranges are planning estimates,
not commitments or recorded time spent.

## 6. Exact next execution goal

> Implement the milestone-2 catalog journey from a documented bounded real
> Scryfall seed through face-aware Python normalization, immutable export,
> atomic PostgreSQL publication, Spring catalog/snapshot APIs and Next.js guest
> discovery/detail/dataset pages. Preserve measurement invariants and existing
> work. Prove the path with real PostgreSQL integration and deterministic browser
> tests, provide reproducible local setup, and report verification limits. Do not
> add tournament scores/accounts or commit, push, deploy or purchase services.

This goal can start without a TopDeck key. Real PostgreSQL availability must be
resolved before the database-dependent verification can complete. A catalog-only
demo is the next checkpoint; tournament evidence remains essential to the final
portfolio product's distinctive value.

## 7. Explicitly deferred scope

Authentication and cloud-saved pools follow the useful guest flow. Multiple
tournament sources, broad historical legality, advanced clustering, regularized
package discovery and model calibration depend on suitable empirical data.
Forge availability needs its own versioned mapping; printing existence alone is
not proof that an installed Forge version implements a card.

Causal engine classification, deck optimization, social features, payments and
an AI chat interface are outside the first release. Additional microservices,
Kafka, Kubernetes, Redis and a separate search service require an observed need.

No commits, pushes, deployments or purchases were made during milestone 1 or
this report follow-up.
