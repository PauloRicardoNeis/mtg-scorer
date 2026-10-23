# Test strategy and plan

Every behaviour is proved once, in the cheapest layer that can prove it, with
real infrastructure only where a double would hide the risk. This document is the
standing rule set: which test goes where, how tests are designed, what "done"
means for each kind of change, and how test data and environments are governed.

## Goals

1. **Protect the epistemic rules.** Unknown is never zero, provenance is never
   dropped, coverage limits are explicit, and a score is always attributable to the
   versions that produced it. These come from the
   [measurement contract](../measurement-contract.md) and are tested as invariants.
2. **Keep the Python, Java and web boundary intact.** The same formula is never
   maintained twice, no request path reaches a card source or a Python process, and
   the web consumes only the generated contract.
3. **Catch regressions before merge, in under five minutes of CI.** Slow signals
   run on a schedule, never on the pull-request path.
4. **Make every failure diagnosable from the artifacts.** Logs, reports and the
   disposable database are retained.

## Scope

In scope: everything under `analytics/`, `api/`, `web/`, `contracts/`,
`scripts/demo.py`, `scripts/*_contract*.py`, `scripts/check_boundaries.py`,
`scripts/e2e_control.py` and the CI workflow. Out of scope for automated
verification: the live probe scripts (they need network access and credentials and
are run by hand), deployment (nothing is deployed), and statistical validity of the
score formulas (research work, guarded by sentinels only).

## Layered model

| Runtime | Unit | Component / slice | Integration | End to end |
| --- | --- | --- | --- | --- |
| Python | pytest over pure functions: domain, features, scoring, cohort rules, parsers on fixture bytes | CLI through `main()` with temporary directories | pytest against real PostgreSQL (`TEST_DATABASE_DSN`): publication, roles, races, rollback | pytest against the running API (`CATALOG_TEST_API_URL`): HTTP contract and refresh |
| Java | JUnit for codecs, query parsing, name keys, models | `MockMvc` standalone controllers; repositories with a mocked JDBC template asserting SQL and parameters | proposed: `@JdbcTest` with Flyway on the CI PostgreSQL | `@SpringBootTest` on a random port for info, health, OpenAPI and Problem Details |
| Web | vitest for `lib` (formatting, URLs, API client) and `i18n` | vitest plus Testing Library for `components` with the router double | n/a | Playwright on the production build against the real API and database |
| Cross-cutting | JSON Schema validity, fixture conformance, boundary rules | | live OpenAPI drift, generated client drift | the whole `demo.py verify` chain |

Rules of placement:

- A pure computation gets a unit test and nothing else. Scoring arithmetic is
  never asserted through HTTP.
- SQL is asserted where it runs. A mocked JDBC template proves parameter binding,
  not query correctness; every repository query needs at least one test against
  PostgreSQL (today only through the Python HTTP tests, see the gaps document).
- A user journey gets one Playwright test and no unit test of the page. Page
  components that carry logic are extracted into `components` and unit-tested.
- A contract change is caught by the drift check first, the generated client's
  type errors second, the browser suite last.

## What each layer must prove

**Python.** Facts are parsed from retained bytes only after their hash is
verified. Coverage dimensions are kept apart and never collapsed. Cohort rules
include and exclude exactly the events and decks the cohort file states. Every
registered score method is deterministic, carries its identity, scores every
eligible card or returns `None`, and never emits a stand-in zero. Run files satisfy
their schema and the relationship checks before they are written; identical results
reuse the file and different results under the same id are refused. Publication is
atomic, replayable, visible only after promotion, role-restricted and reversible.

**Java.** Every query parameter is validated and bounded; unknown or duplicate
parameters are a 400 with a stable `code`. Cursors round-trip and any tampering is
rejected. Set, rarity and game filters combine on a single printing. Missing active
catalog is a 503, not an empty page. Problem Details never leak internals. The
generated OpenAPI lists only implemented endpoints.

**Web.** Components render every state they have (loading, empty, error, populated,
pending navigation). Every string reaches the screen through the translator.
URL builders preserve every filter and the pinned snapshot. The production build
serves each page to a guest with keyboard access and no axe violation.

**Cross-cutting.** Boundaries hold on every build. Schemas validate and fixtures
conform. The Python producer, the Java consumer and the web consumer agree on the
contract on every verify.

## Design rules for every test

1. **Name the behaviour, not the function.** `test_an_event_dated_exactly_ends_before_is_excluded`,
   not `test_select_cohort_2`.
2. **Test both sides of every boundary.** A threshold test asserts the last
   accepted value and the first rejected one. This is the single largest gap the
   mutation pilot found.
3. **Pin formula constants with sentinel expectations that state their meaning.**
   "8 decks alone give 63.2% of the deck weight" survives a refactor; a bare
   `assert evidence > 50` does not.
4. **Assert invariants and pairwise orderings, not fixture numbers**, unless the
   number is itself the contract (a hash, a schema version, a row count).
5. **Parametrize over registries and vocabularies** (score methods, locales,
   formats) so new entries are covered on arrival.
6. **Synthetic data must be unmistakable.** Derived ids, a `synthetic` marker in
   cohort files, never a real player or event name.
7. **Deterministic by construction.** Fixed timestamps, stubbed CDN, no live
   network, no `sleep` in assertions; use the test framework's clock.
8. **Skips name the missing resource.** A skip reason reads as an instruction to
   obtain the resource, never as "flaky".
9. **No retries in CI.** A test that needs a retry is a defect to fix or
   quarantine with an issue, never to mask.
10. **One failure mode per test.** A failing test says what broke without reading
    its body.
11. **Keep order independence.** Tests that publish restore the active snapshot
    or run; the browser suite's single worker is the only accepted ordering
    dependence, and it is documented in the spec.

## Definition of done by kind of change

| Change | Required tests and checks |
| --- | --- |
| New score method | Module tests for its own behaviour and boundaries; registered in `SCORE_METHODS` so the shared contract tests run; a sentinel pairwise expectation on the synthetic cohort; `score-run.schema.json` updated if outputs change; the rankings HTTP test lists the method; the web grading menu test includes it |
| New or changed feature in `tournament_features.py` | Both-side boundary tests; `measurement-contract.md` row updated; validator parity with any new database CHECK; run-file fixture regenerated |
| New ingest adapter | Fixture bytes with hashes and attribution under `tests/fixtures`; manifest verification test; quarantine behaviour for incomplete records; coverage dimensions asserted; an opt-in probe script, never in CI |
| New Flyway migration | Runs in verify on an empty database (automatic); a publication test exercises the new columns, CHECKs and functions; Python validator extended to match every CHECK; proposed: a migration test on a populated snapshot |
| New API endpoint or parameter | Query validation tests (valid, invalid, duplicate, unknown); repository test asserting SQL and parameters; controller test; OpenAPI test pins the path; `api_contract.py --update` and a regenerated client reviewed; a Python HTTP test against the published seed; Problem Details with a stable `code` |
| New web component | vitest for every state and interaction; translator used for every string; axe-covered in the journey that shows it; coverage thresholds hold |
| New page | A Playwright journey covering its states, keyboard access and URL pinning; `loading.tsx` and error state exercised; added to the i18n journey when it has user-visible text |
| New locale | Message file passes parity, placeholder and plural-form tests automatically; added to `locales`; the language journey exercises it once |
| New script under `scripts/` | Ruff clean; unit test when it has logic; if it needs network or credentials it is opt-in and documented as such |
| Dependency bump | `uv.lock`, `package-lock.json` or the BOM pin updated; verify green; for Playwright or Node, the Chromium install step rechecked |
| Change to `demo.py` | A test in `test_demo_runner.py` when it changes decisions; a full local `verify` run; CI run on the pull request |

## Test data policy

- **Real seed, retained bytes.** `analytics/seeds/scryfall-layouts-v1` is the only
  real card data in the repository: 8 Scryfall responses, each with URL, retrieval
  time and SHA-256, byte-preserved by `.gitattributes`.
- **Fixtures carry provenance.** Every retained fixture states its source, date
  and hash, and the licence or attribution the source requires.
- **Synthetic by default for tournaments.** No real tournament data is committed.
  Synthetic builders generate events, decks and standings with derived ids; verify
  publishes them only into its disposable database.
- **Size tiers.** Unit and contract tests use the 7-card seed. A realistic-size
  dataset (thousands of generated cards and decks) is proposed for SQL and
  pagination tests and would be generated, not downloaded.
- **Never in the repository:** downloaded corpora, local databases, probe output
  (`analytics/data/local`, `.local/`), credentials.

## Environments

| Purpose | Database | API port | Web port | Created by |
| --- | --- | --- | --- | --- |
| Demo preview | `mtg_catalog_demo` | 18080 | 3300 | `demo.py up` |
| Verification | `mtg_verify_<12 hex>` (one per run, retained) | 18081 | 3301 | `demo.py verify` |
| Local PostgreSQL | cluster on `127.0.0.1:55432`, data in `.local/postgres-data` | | | `demo.py` unless `CATALOG_ADMIN_DSN` is set |
| CI | `postgres:17.11` service on 5432 via `CATALOG_ADMIN_DSN` | 18081 | 3301 | workflow |

Roles: `catalog_api_local` reads (granted `catalog_reader`, `score_reader`,
`price_reader`, `catalog_import_admin`); `catalog_publisher_local` publishes
(granted `catalog_publisher`, `score_publisher`, `price_publisher`). Tests that
check role denial depend on this split.

## Flaky-test and quarantine policy

- A test that fails without a code change is a defect. Open an issue, mark the
  test skipped with the issue number in the reason, and keep the suite green.
- Quarantine lasts at most two weeks; after that the test is fixed or deleted.
- `retries` stays at 0 in Playwright; `pytest-rerunfailures` is not adopted.
- The weekly lane repeats the suites on one commit to measure the flake rate (see
  [metrics and process](metrics-and-process.md)).

## Exit criteria

A pull request is mergeable when the CI job is green, which today means: lint and
format clean in all three layers, every coverage floor met, contracts and
boundaries pass, the full stage-3 chain passes, and the OpenAPI contract and
generated client are current. Branch protection enforcing this is proposed in
[ci-cd.md](ci-cd.md). A release process does not exist yet; its criteria are
sketched there for when deployment arrives.
