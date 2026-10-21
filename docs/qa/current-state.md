# Current state of testing and quality checks

As of 2026-10-20, about 1,400 automated test cases run across four runtimes, every
unit layer is gated on coverage between 95% and 100%, a real PostgreSQL and a real
Chromium stage run in the single verification command, and the GitHub Actions job
finished in about 4 minutes. The signals missing then were test strength (no
mutation or property-based testing), static analysis beyond formatting (no Python
type checker, no ESLint), dependency scanning and any check of SQL at realistic
size. Phases 1 to 3 of the [roadmap](roadmap.md), on 2026-10-21, added the static
analysis, the mutation tooling, the repository hygiene and the parallel CI lane
described below; property-based testing and SQL at realistic size remain open.

Numbers below were measured on 2026-10-20 on the development machine (Windows 11,
Ryzen 7 7800X3D) from the `feat/all-formats` working tree, or taken from the CI run
of commit `183987b` on the same day. The working tree carried uncommitted work
from other sessions; see [Working-tree observations](#working-tree-observations).

## Toolchain and repository settings

| Item | Value | Where it is pinned |
| --- | --- | --- |
| Python | 3.12.10, dependencies locked with uv 0.8.22 | `.python-version`, `analytics/uv.lock`, `scripts/demo.py` |
| Java | 21 (Temurin in CI), Spring Boot 4.1.1, Maven 3.9.16 through Maven Wrapper 3.3.4 | `api/pom.xml` (enforcer `[21,22)`), `api/.mvn/wrapper/maven-wrapper.properties` |
| Node | 24.14.1, npm 11.11.0 | `.node-version`, `web/package.json` engines, `web/package-lock.json` |
| Web stack | Next.js 16.3.4, React 19.2.8, TypeScript 5.9.3 | `web/package.json` |
| PostgreSQL | 17.11 (portable download on Windows, `postgres:17.11` service in CI) | `scripts/demo.py`, `.github/workflows/ci.yml` |
| GitHub repository | `PauloRicardoNeis/mtg-scorer`, public, default branch `main` | GitHub |
| Branch protection on `main` | none (no required checks, no rulesets) | GitHub API, 2026-10-20 |
| Secret scanning | enabled, with push protection | GitHub settings |
| Dependabot | alerts and security updates disabled in the settings; `.github/dependabot.yml` committed 2026-10-21 for uv, npm, Maven and Actions | GitHub settings, repository |
| Code scanning (CodeQL) | `.github/workflows/codeql.yml` committed 2026-10-21 (Java, JavaScript/TypeScript, Python; weekly and on pull requests) | repository |
| Workflows | `ci.yml` on push to `main` and on pull requests (five jobs since 2026-10-21: `python`, `java`, `web`, `integration`, `gate`); `codeql.yml`; `weekly.yml` (mutation testing, Mondays and on demand) | repository |
| Line endings | `* text=auto eol=lf`, CRLF only for `*.cmd`/`*.bat`, byte-exact seeds and fixtures; `.editorconfig` matches (since 2026-10-21) | `.gitattributes`, `.editorconfig` |
| Pre-commit | `.pre-commit-config.yaml` (ruff, pyright, Prettier, ESLint, Spotless, standard hooks); installed per clone with `pre-commit install` | repository |
| CODEOWNERS, PR template | none | repository |

## The verification pipeline

`python scripts/demo.py verify` is the single entry point locally and in CI. It
runs three stages in order and stops at the first failure.

1. **Install** (`install`, skipped with `--skip-install`): `pip install uv`,
   `uv sync --locked --extra dev`, `npm ci`, Playwright Chromium.
2. **Build stage** (offline, skipped with `--skip-build`; since 2026-10-21 also
   runnable per layer as `demo.py check --only python contracts java web`), in this order:
   `ruff check analytics scripts`; `ruff format --check`; `pyright`;
   `pytest analytics/tests` in random order with coverage and the 95% floor;
   `scripts/verify_contracts.py`; `scripts/check_boundaries.py`; `mvnw verify`
   (Spotless, Enforcer, Surefire, JaCoCo floors, jar); `prettier --check`;
   `eslint .`; `vitest run --coverage` with its thresholds; `next build`;
   `tsc --noEmit`. pytest and vitest also write JUnit XML, to
   `.local/junit/pytest-offline.xml` and `web/reports/junit/vitest.xml`.
3. **Database and browser stage** (`verify` only): find or start PostgreSQL;
   create `mtg_verify_<id>`, the `catalog_api_local` and `catalog_publisher_local`
   roles; start the API jar on port 18081 with Flyway migrations V1 to V10; wait
   for liveness; `scripts/api_contract.py` (live OpenAPI equals the checked-in
   contract, regenerated TypeScript client unchanged); empty-catalog HTTP test
   (503, not an empty page); import-job test; PostgreSQL publication tests for
   catalog, scores (including the two-publisher race) and prices; export and
   publish the 7-card seed; score and
   publish the synthetic TopDeck run and the Overall run built from it; publish
   seed prices; wait for readiness; catalog and rankings HTTP tests (every
   database-stage pytest run writes `.local/junit/pytest-<stage>.xml` and appends
   to the offline coverage data); start
   `next start` on port 3301 with the primitives gallery enabled; Playwright;
   `scripts/measure_catalog.py` writes `measurements.json`. Since 2026-10-21 the
   stage ends with the merged Python coverage report (offline plus database stages,
   the 95% floor applied once, XML and HTML in `.local/coverage/python/`).

`demo.py up` runs stages 1 and 2 and then serves the demo database on ports 18080
and 3300 without the stage-3 tests.

### CI

Since 2026-10-21 (`ci.yml` in the working tree; the first GitHub run is pending)
the lane has five jobs on `ubuntu-latest`. `python`, `java` and `web` run in
parallel, each installing only its toolchain and running `demo.py check --only` for
its layer; `integration` starts the `postgres:17.11` service, installs the Python
and web environments and Chromium, downloads the jar, the `.next` build and the
offline coverage data from the three, and runs `demo.py verify --skip-install
--skip-build`; `gate` is green only when all four succeeded and is the status to
require on `main`. The workflow cancels superseded runs of the same ref, times out
every job (15, 15, 15, 20 and 5 minutes), grants `contents: read` only, and
annotates JUnit results inline with `mikepenz/action-junit-report@v5`. Artifacts:
`python-coverage`, `junit-python`, `api-jar`, `java-reports`, `web-build`,
`web-coverage`, `catalog-verification` (logs, measurements, `.local/junit/`,
Playwright report and traces) and `python-coverage-merged`. [ci-cd.md](ci-cd.md)
has the diagram.

Until then a single job `catalog` set up the three toolchains, ran `demo.py install`
and `demo.py verify --skip-install`, and uploaded `catalog-verification` and
`coverage`:

| CI fact (run 39461227262, 2026-10-20, single job) | Value |
| --- | --- |
| Wall clock | 3 min 59 s |
| Install step | 33 s |
| Verify step | 2 min 42 s |
| Last 15 runs on `main` and pull requests | all green |
| Concurrency control, `timeout-minutes`, test annotations, matrix, path filters | none then; all but matrix and path filters since 2026-10-21 |

## Inventory by layer

| Layer | Tests | Runtime | Coverage | Enforced floor | Runs in |
| --- | --- | --- | --- | --- | --- |
| Python offline (pytest) | 657 passed, 74 skipped (2026-10-21 13:50), from 405 test functions in 34 files | 13.1 s with coverage | 97.31% statements and branches | 95% `fail_under` | build stage, CI |
| Python database and HTTP stage (pytest) | the 74 skipped cases, in 7 files | inside verify | not measured | none | verify only |
| Contracts (`verify_contracts.py`, unittest) | 6 checks, one with 11 sub-cases | about 1 s | schemas and fixtures | pass/fail | build stage, CI |
| Boundaries (`check_boundaries.py`) | 4 rule groups | about 1 s | import graph | pass/fail | build stage, CI |
| Java (JUnit 5, Mockito, Spring Boot Test) | 301 executed from 227 annotated methods in 33 classes | 11.7 s test time (Surefire) | 99.7% instructions, 99.4% branches in the working-tree report | 0.99 instructions, 1.00 branches (JaCoCo) | `mvnw verify`, CI |
| Web unit (vitest, Testing Library, jsdom) | 484 executed from 396 declarations in 33 files | 8.9 s | thresholds hold on `lib`, `components`, `i18n` | 100 / 99 / 100 / 100 (statements, branches, functions, lines) | `npm run test:unit`, CI |
| Browser (Playwright, axe-core) | 28 tests in 5 spec files | inside verify | pages not measured; axe at 16 points | none | verify only |
| Live contract (`api_contract.py`) | 2 checks | inside verify | OpenAPI and TypeScript client drift | pass/fail | verify only |
| Measurements (`measure_catalog.py`) | 100 requests, EXPLAIN ANALYZE | inside verify | records p50, p95, max | fails only on request errors | verify only |

### Python (`analytics/`)

- 6,441 lines of source under `src/mtg_scorer`, 7,798 lines of tests. Ruff with
  the extended rule sets at line length 100 and `ruff format`; pyright in
  standard mode; `pytest-randomly` and `pytest-timeout` since 2026-10-21. No
  Hypothesis, no `pytest-xdist`.
- The offline suite covers ingestion (Scryfall bulk, TopDeck responses, Wizards
  coverage pages), face-aware normalization, immutable exports and bulk export,
  the domain model's validation, tournament features and cohort rules, every
  registered score method through a shared parametrized contract, run-file
  writing and validation, the Overall run, the CLI and two tests of `demo.py`
  itself.
- Added on 2026-10-21 (roadmap phase 1): `test_boundary_values.py` (valid-side
  boundaries and pinned Evidence constants), `test_score_validation_parity.py`
  (every CHECK of migrations V4 to V10 mapped to a rejected mutation) and
  `test_score_publication_race.py` (two score publishers racing, stage 3).
- The 74 cases that need a database or a running API skip with a reason naming
  the missing resource (`TEST_DATABASE_DSN`, `CATALOG_TEST_API_URL`, the import
  token). `demo.py verify` runs them explicitly in stage 3, so
  `publish/postgres.py` reports 22% in the gated offline run while being fully
  exercised later, uncovered.
- Fixtures: the 8-response real Scryfall seed with per-file hashes and
  attribution (`seeds/scryfall-layouts-v1`), one retained `default-cards.json`,
  synthetic TopDeck builders that derive oracle ids from names so invented data
  can never pass as evidence, a synthetic cohort file, and 8 archived Wizards
  coverage pages. Cohort rule files live in `analytics/cohorts`.

### Java (`api/`)

- 39 source files (3,719 lines) and 9 Flyway migrations; 34 test files (5,443
  lines). Spotless with google-java-format 1.25.2, Maven Enforcer for JDK 21,
  JaCoCo report and check. No Error Prone, SpotBugs, PMD, Checkstyle or ArchUnit.
- Repository tests mock `NamedParameterJdbcTemplate` or `JdbcTemplate` and assert
  the SQL text and parameters; controller tests use standalone `MockMvc`; one
  `@SpringBootTest` on a random port with an unreachable datasource (13 tests)
  checks `/api/v1/info`, liveness, the generated OpenAPI document, Problem Details
  and the error path. Three OpenAPI test classes pin the generated contract.
- No Java test opens PostgreSQL. The real SQL, the migrations and the plpgsql
  publication functions are exercised only by the Python HTTP and publication
  tests in stage 3, against 7 cards, 8 printings and a synthetic run of 2 events
  and 7 decks.

### Web (`web/`)

- Unit tests sit beside the code in `src/components`, `src/i18n` and `src/lib`;
  `src/app` pages are excluded from unit coverage and covered by Playwright. The
  App Router hooks are replaced by a test double in `src/test/navigation.ts`.
- The i18n suite enforces that each of the 10 non-English locales translates
  every English key and nothing else, keeps every placeholder and has exactly the
  plural forms `Intl.PluralRules` defines for the language.
- Playwright: Chromium desktop only, one worker, no retries, trace kept on
  failure, HTML and list reporters. Journeys: 9 catalog (filters, faces, dataset,
  shareable URL, keyboard access, pagination across a real Python refresh,
  responsive layout, database failure and recovery, image fallbacks, header search
  and the `/` shortcut), 9 rankings, 4 compare, 4 language, 2 primitives gallery.
  The Scryfall image CDN is stubbed in the catalog and rankings specs; the first
  catalog journey fails on any other outbound request; axe runs at 16 points in
  four of the five specs (the language spec has none).
- Prettier check and `tsc --noEmit` (strict). No ESLint, no Stryker, no
  fast-check, no visual snapshot assertions (four screenshots are captured but not
  compared), no Lighthouse.

### Contracts and boundaries (`contracts/`, `scripts/`)

- `verify_contracts.py`: the catalog publication and manifest schemas are valid
  Draft 2020-12; a valid catalog passes and 11 mutations are rejected (unsupported
  version, scores inside a catalog, duplicate card, orphan printing, lost faces or
  aliases, naive timestamp, missing checksum, three non-finite numbers); manifest
  verification detects changed bytes and counts; the OpenAPI document validates
  and the `card-page.json` fixture matches the `CardPage` schema.
- `api_contract.py`: the running API's `/v3/api-docs` equals
  `contracts/catalog-api.openapi.json` and regenerating `web/src/lib/api.generated.ts`
  changes nothing.
- `check_boundaries.py`: the Python domain, feature and scoring modules import no
  I/O adapter; normalization does not depend on ingestion or publication; Java
  capabilities form no cycle and the catalog package reaches snapshots only
  through `SnapshotService`; no Java source spawns processes, opens HTTP or names
  analytical artifacts; web code enters the generated DTOs only through `lib/api.ts`
  and never fetches a card source or a database directly.
- Live probes (`probe_tournaments.py`, `probe_wizards_coverage.py`,
  `probe_mtgtop8.py`, `probe_catalog.py`) are opt-in, need network or credentials
  and never run in CI.

## Tooling matrix

| Concern | Python | Java | Web | SQL / CI / docs |
| --- | --- | --- | --- | --- |
| Formatting | ruff format | Spotless (google-java-format) | Prettier | none |
| Linting | Ruff E, F, I, UP, B, S, PT, SIM, C4, RUF, PL, ARG, RET, TRY, PERF, N, DTZ (since 2026-10-21) | none beyond the compiler | ESLint 10, type-checked, with react-hooks, jsx-a11y, Next, vitest and Playwright rules (since 2026-10-21) | none (no sqlfluff, actionlint, markdownlint) |
| Type checking | pyright, standard mode, strict on `domain.py` and `features.py` (since 2026-10-21) | compiler | `tsc --strict` plus `noImplicitOverride` and `exactOptionalPropertyTypes` | n/a |
| Unit tests | pytest | JUnit 5, Mockito, AssertJ | vitest, Testing Library | n/a |
| Coverage gate | 95% | 99% / 100% | 100 / 99 / 100 / 100 | n/a |
| Integration | pytest against real PostgreSQL and the running API | none in Java | Playwright against the full stack | Flyway runs in verify |
| Contract | jsonschema, openapi-spec-validator, live drift check | OpenAPI tests | generated client drift | JSON Schema files |
| Architecture rules | `check_boundaries.py` (AST) | `check_boundaries.py` (regex) | `check_boundaries.py` (regex) | n/a |
| Accessibility | n/a | n/a | axe-core in Playwright | n/a |
| Mutation testing | mutmut config (weekly lane, Linux only) | PIT profile `mutation` (since 2026-10-21) | Stryker, `npm run mutation` (since 2026-10-21) | `weekly.yml`, `scripts/mutation_summary.py` |
| Property-based | none | none | none | n/a |
| Dependency updates / audit | uv lock; Dependabot config (since 2026-10-21) | BOM pins; Dependabot config | `npm ci --no-audit`; Dependabot config | Dependabot for Actions; no audit job yet |
| Security scanning | CodeQL workflow (since 2026-10-21) | CodeQL workflow | CodeQL workflow | secret scanning on |
| Performance | `measure_catalog.py` records, asserts nothing | none | none | n/a |

## Strengths worth preserving

The suite already follows contributor rule 7, "tests for invariants and pairwise
expectations, not only fixture numbers". Keep these patterns when extending it.

- **Behaviour-named tests with invariant assertions.** `test_scoring.py` asserts
  that Evidence grows monotonically and saturates per weight, that unknown
  features never become zero, and that distinctiveness equals build-around minus
  staple.
- **Shared contract tests over the method registry.** `test_score_methods.py`
  parametrizes over `SCORE_METHODS`, so a new method inherits determinism,
  identity and output-shape checks on the day it is registered.
- **Adversarial input matrices.** `CursorCodecTests` rejects malformed encodings
  and tampered fields; `CatalogQueryValidationTests` covers duplicate and unknown
  parameters; `verify_contracts.py` mutates a valid catalog eleven ways.
- **Synthetic data kept apart from the real seed.** Oracle ids derived from names,
  a cohort file marked synthetic, and only verify's disposable database ever
  receives them.
- **Real failure modes in the integration stage.** Failed loads, staging
  invisibility, abandoned attempts, stale promotion, role denial, two catalog
  publishers racing, and a browser journey that revokes a real table grant and
  checks recovery.
- **Deterministic browser journeys.** The image CDN is stubbed where cards
  render, the main catalog journey fails on any outbound request, axe runs at 16
  points, and one worker with zero retries keeps order-dependent database state
  honest.
- **Drift checks on every run.** Live OpenAPI against the checked-in contract and
  the generated TypeScript client; publication schemas against fixtures.
- **Internationalization enforced by test.** Key parity, placeholder parity and
  plural-form parity across 11 languages, which is what caught the in-progress
  work noted below.
- **Fast feedback.** Each unit suite finishes in under 20 seconds, which makes
  mutation testing affordable.

## Working-tree observations

Measured against the uncommitted working tree on 2026-10-20 at about 22:50, with
four other sessions editing the same checkout.

- `vitest`: 30 failures, all in `src/i18n/messages/messages.test.ts`, because
  `en.ts` gained about 240 keys for archetype and decklist pages that the other
  10 locales do not yet carry. The test is doing its job; the work is in
  progress. All 454 other cases pass.
- JaCoCo report generated at 22:37 shows 4 of 633 branches missed (99.4%), below
  the 100% branch floor, from the same in-progress API work.
- A `.coverage` data file at the repository root from a partial run reports 87%;
  it is not the gated number. The gated run writes to `.local/coverage/python`.
- Parallel sessions in one checkout make local suites fail on each other's
  partial work; CI on the pushed branch is the arbiter until the work is
  committed. The process document proposes worktrees for parallel work.

## Growth since the 2026-10-18 assessment

| Layer | 2026-10-18 | 2026-10-20 |
| --- | --- | --- |
| Python offline cases | 309 passed, 22 skipped | 531 passed, 65 skipped |
| Java tests executed | 186 | 301 |
| Web unit cases | 221 | 484 |
| Browser journeys | 11 | 28 |
| Flyway migrations | V1 to V4 | V1 to V9 |
| Languages | 1 | 11 |

The suites grew with the rankings, compare, commander, price and language
features. Coverage floors held throughout.
