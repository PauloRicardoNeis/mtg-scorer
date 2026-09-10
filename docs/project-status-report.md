# MTG Scorer: milestone 2 implementation and verification

Status: **2026-09-08 — milestone 2 complete as a verified local catalog application.**

Retained real Scryfall bytes now pass through face-aware Python normalization,
immutable JSON/Parquet export, atomic PostgreSQL publication, Spring catalog and
snapshot APIs, and three guest Next.js views. This delivers the active milestone-2
checklist. It does not establish tournament feasibility or competitive score quality.

[Run the local application](local-catalog.md), read the
[design and maintainability review](milestone-2-review.md), or inspect the
[desktop browser capture](evidence/milestone2/discovery-desktop.png).
The [implementation plan](implementation-plan.md) remains the roadmap; portfolio
section 6 and the measurement contract remain acceptance/semantic authorities.
The superseded status and intermediate checkpoints are retained in the
[status archive](evidence/milestone1/project-status-report-before-completion.md).

## Acceptance audit

| Active checklist item | Delivered behavior | Direct evidence |
| --- | --- | --- |
| 1. Reproducible toolchain and real seed | Python 3.12.10/uv lock, JDK 21/Maven Wrapper, Node 24.14.1/npm 11.11.0/package lock; eight exact retained Scryfall responses with manifest, hashes, attribution and Git byte-preservation attributes | Fresh Python environment and npm ci followed by complete runner; seed/export hashes; [runbook](local-catalog.md), [seed policy](../analytics/seeds/scryfall-layouts-v1/README.md) |
| 2. Face-aware normalization | Deterministic English-preferred representative, original face order, colliding aliases, null versus empty, image/game metadata and explicit exclusions | Seven export tests cover real layouts, missing IDs, unknown/multi-face/reversible layouts, conflicts, unknown values, aliases and order independence; 7 cards / 8 printings / 10 faces / 17 aliases |
| 3. Immutable export | Atomic directory finalization, versioned serving JSON and analytical Parquet, separate hashes/manifests, closed schemas and relationship validation | Corrupt raw/export rejection, failed normalization/download preservation, replay and concurrent finalization; streaming publication validation; no live source in deterministic tests |
| 4. Atomic PostgreSQL publication | Flyway V1, scoped keys/FKs, immutable published rows, restricted roles, one locked publisher connection, retained snapshots and guarded rollback | Five real PostgreSQL 17.11 tests: integrity, replay, content conflict, role denial, failed load/retry, staging invisibility, two publishers with paused old-snapshot reader, abandoned attempt recovery, invalid references/counts and stale-pointer rejection |
| 5. Spring catalog/snapshot API | Parameterized JDBC, bounded input, joint-printing filters/counts, literal alias search, unknown/colorless identity, pinned keyset pagination, sanitized catalog errors and readiness | 15 Java tests and five live HTTP tests against Python-published PostgreSQL; both pagination resources across refresh, cursor tampering/mismatch, invalid/unknown resources, initially unavailable catalog; live OpenAPI/generated TS agreement |
| 6. Three guest browser views | Discovery, ordered face/detail/eligible printings and dataset/provenance pages; pinned shareable URL; native responsive controls; keyboard focus, loading, empty, error/retry | Five Chromium tests against production build: real guest journey, clipboard/reopen, Back, joint filters, refresh pagination, pending navigation and recovery after actual DB permission failure; axe and desktop/mobile visual inspection |
| 7. Deterministic integration and boundaries | One setup/verify runner creates a disposable real database, migrates, publishes, serves Java and tests Next; CI calls same runner | Fresh Windows end-to-end run passed; Python imports, Java capability cycles/access and web API-entry checks passed; GitHub Actions PostgreSQL job configured, remote execution not claimed |
| 8. Review, measurement and handoff | Source/diff review, query plan and resource measurements, filter extension/failed-refresh review, exact startup/retry/rollback instructions, preserved original work | [Review](milestone-2-review.md), [measurements](evidence/milestone2/measurements-windows.json), [clean-run log](evidence/milestone2/clean-verification-windows.log), runtime inventory and commands below |

## Reproduce and inspect

From `C:\Users\paulo\Documents\work\mtg-scorer` in PowerShell:

```powershell
$env:JAVA_HOME = 'C:\Users\paulo\.jdks\temurin-21.0.12.1'
python scripts/demo.py up
```

Use your own JDK 21 path on another machine. Open
[discovery](http://127.0.0.1:3300/cards) or
[Swagger](http://127.0.0.1:18080/swagger-ui.html). The preview uses
`mtg_catalog_demo`; the local PostgreSQL cluster listens on `127.0.0.1:55432`.
Ctrl+C stops the runner's Java/web processes while preserving data and PostgreSQL.
After installing and building, `python scripts/demo.py up --skip-install --skip-build`
starts the same verified preview. Full verification is `python scripts/demo.py verify`.
See the runbook for existing PostgreSQL, POSIX setup, failure diagnosis and rollback.

The clean verification used a fresh Python environment:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.local/clean-python-m2"
python scripts/demo.py verify
Remove-Item Env:UV_PROJECT_ENVIRONMENT
```

The retained disposable database is `mtg_verify_63cb2b7c225b`; original evidence
remains under `.local/mtg_verify_63cb2b7c225b/`. The archived log records the complete
install/build/test sequence. Offline Python shows ten integration skips because
those tests run explicitly later: initial-state HTTP (1), publication (5), then
populated HTTP (4). The populated phase skips only the already-executed initial
state test. Totals: **39 distinct Python tests, 6 contract checks, 15 Java tests
and 5 browser tests**, all passed in their relevant phases. Ruff lint/format,
Spotless, Maven Enforcer/build, Next production build, strict TypeScript, Prettier,
dependency boundaries and live schema/client checks passed.

After the clean run, browser checks were expanded to inspect narrow detail and
dataset views as well as discovery; all five passed again. The desktop capture
was corrected to wait for rendered content. A Windows PostgreSQL output-handle
issue was then fixed in the setup script and verified with an actual cluster
stop/cold start: startup returned normally and retained data. The clean-run log
predates that lifecycle fix and expanded mobile assertions; it is not presented
as a verbatim record of those later checks. Final Ruff, contract, boundary and
format checks cover the final files. The preview was restarted successfully.

## Dataset and measured conditions

The real seed contains seven layouts in eight printing responses (49,570 raw
bytes), including Lightning Bolt's M11/common versus 2X2/uncommon counterexample,
Delver's faces, Fire // Ice, Adventure, modal double-face, flip and meld examples.
The original retained manifest supplies source URLs, timestamps and individual
hashes. Synthetic adversarial records exist only in tests/disposable databases.

| Identity | Value |
| --- | --- |
| Source manifest SHA-256 | `263bef0fc5d4833af02db85207c19df16e0e8c60a3847df997e3e9a8faa8cc4a` |
| Catalog snapshot | `catalog-5d2a2464059d4c02fcedbc47c3687262066338961421f84a7d03eb5021744d6e` |
| Serving export SHA-256 | `2fb9361608e316a4743dc18b027a94ac03984999fcd15cd8c7ea7a5a76501e8d` |
| Deterministic creation timestamp | `2026-09-08T00:46:15Z` |
| Published rows | 7 Oracle cards, 8 printings, 10 faces, 17 aliases; zero exclusions in this sample |

[Measurements](evidence/milestone2/measurements-windows.json) record the exact
workload, source/export IDs, EXPLAIN ANALYZE, timings and storage. The
[runtime inventory](evidence/milestone2/runtime-inventory-windows.json) records
Windows 11, Ryzen 7 7800X3D (8 cores / 16 logical processors), about 31.1 GiB reported
physical memory, Python 3.12.10, Temurin 21.0.12.1, Node 24.14.1 and npm 11.11.0.
The measurement records PostgreSQL 17.11's actual server version.

- Export: 0.037 s; publication: 0.046 s; Python process peak RSS through import:
  60,952,576 bytes (about 58.1 MiB).
- Serving JSON: 13,759 bytes; complete artifact: 33,045 bytes. Disposable database:
  9,467,571 bytes including retained synthetic/test snapshots.
- 100 warm loopback HTTP requests, 20 workers: p50 5.19 ms, p95 8.32 ms,
  maximum 10.82 ms, zero errors. Browser assets excluded.
- The joint-printing plan uses `card_name_page`, `printing_pool` and snapshot
  primary-key indexes. No full-catalog index/performance conclusion follows.

These figures prove a small integration works. Full-catalog latency, memory,
throughput, cold-start performance and the proposed 300 ms scale target remain
unverified. No performance target was claimed from seven cards.

## Correctness, ownership and remaining scope

Python retains ingestion, normalization, export and publication orchestration,
plus all analytical ownership. Java owns the database schema, publication protocol,
product queries and API validation. Next consumes Java and owns presentation.
No application request runs Python, fetches live MTG data or serves a research
score. Automated dependency checks and the [review](milestone-2-review.md) document
boundaries, alternatives, recovery and the concrete printing-filter extension.

The original tracked modifications, deleted root Python paths and untracked
application migration were preserved. Nothing was staged, committed, pushed or
deployed. Normalized text comparisons against the tracked foundation confirm
`domain.py`, `features.py` and `scoring.py` retain their original contents. Unknown
evidence remains unavailable; pool filters do not redefine a tournament cohort
and current card facts do not claim historical legality. The browser explicitly
says tournament observations and scores are unavailable.

**No unmet milestone-2 criterion or runtime blocker remains.** Explicit limits:

- Windows local execution and Chromium were verified. Linux/remote GitHub Actions
  has not run remotely. Axe and visual checks do not establish broad browser or
  assistive-technology usability.
- The seed is intentionally incomplete. Full bulk load, operational stress,
  retention/backup restore, hosting, public licensing and cost remain later work.
- Tournament access/coverage, source resolution, historical legality and empirical
  features/score evaluation remain unresolved analytical work. TopDeck was neither
  needed nor used. The known standing-denominator research issue remains deferred;
  no measured feature was built on it.
- Authentication, user accounts, deployment and milestone 3 were not started.

## Final checkpoints

4. Added deterministic runner and PostgreSQL CI job, resolved API/TS contracts,
   completed unknown/colorless and loading/failure cases, hardened legacy ingestion
   interruption/replay, and enforced actual module boundaries.
5. Passed clean locked installation and all verification phases; inspected desktop
   and narrow guest pages; recorded bounded measurements; reviewed filter extension,
   failed-refresh diagnosis and query plan; corrected Windows process lifecycle
   and Git seed-byte preservation; completed runbook and acceptance audit.
