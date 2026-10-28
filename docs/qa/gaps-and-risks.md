# Gaps and risks

Twenty-two gaps, ranked by what can break unnoticed; ten (G2, G4 in files, G5 but
one flag, G7, G8, G9, G10, G14, G16, G19) were closed on 2026-10-21, see the end. The first five are where a regression would
ship with a green build today: SQL and migrations verified only end to end on a
7-card seed, boundaries tested on the invalid side only, no protection on `main`,
no dependency or vulnerability scanning, and no static analysis beyond formatting. Severity combines impact and likelihood; effort is
S (under a day), M (one to three days), L (a week or more). Evidence is as of
2026-10-20.

| # | Gap | Evidence | What can go wrong unnoticed | Severity | Fix | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| G1 | SQL verified only end to end, on tiny data | Every Java repository test mocks the JDBC template; real queries run through 8 catalog and 17 rankings HTTP test functions over 7 cards, 8 printings, 2 events and 7 decks | Keyset pagination past one page, the `\m` type regex, color-array filters, sorting ties and the rankings window functions are never exercised at realistic size or beyond ASCII | High | `@JdbcTest` with Flyway on the CI PostgreSQL, or a generated catalog of a few thousand cards walked page by page in the HTTP tests ([advanced-testing.md](advanced-testing.md)) | L |
| G2 | Boundaries tested on the invalid side only | 26 of 35 mutation survivors flip `<` to `<=` or shift a constant by one ([mutation-testing.md](mutation-testing.md)) | An event dated on `ends_before` leaks into a cohort; a wins tie at the top cut reads as a clean cut; a one-of mainboard card is dropped; rank 1 is rejected | High | Write the 26 boundary tests in the appendix | S |
| G3 | No protection on `main` | GitHub API: branch not protected, no rulesets; squash and merge commits both allowed | A push or merge with a red or absent CI run lands on `main` | High | Required status check `CI gate` (the `gate` job of `ci.yml`), require a pull request, linear history ([ci-cd.md](ci-cd.md)) | S |
| G4 | No dependency update or vulnerability scanning | No `dependabot.yml`; Dependabot alerts disabled; `npm ci --no-audit`; no `pip-audit`, no OWASP dependency-check; no CodeQL on a public repository | A known CVE in a transitive dependency ships; pins rot until an upgrade becomes a project | High | Dependabot for uv, npm, Maven and Actions; weekly audit job; CodeQL default setup ([ci-cd.md](ci-cd.md)) | S |
| G5 | No static analysis beyond formatting | No pyright or mypy despite full type hints; no ESLint; Ruff limited to E, F, I, UP, B; no Error Prone or ArchUnit | Nullability and typing mistakes, hook misuse, accessibility regressions and dead code reach tests or production | High | [static-analysis.md](static-analysis.md) | S to M |
| G6 | Migrations and plpgsql functions run only in verify, only on an empty database | V1 to V9 apply once per verify to a fresh database; no Java test touches PostgreSQL; no test migrates a populated snapshot | A migration that passes on an empty database and breaks on published rows is caught after merge, on the demo database | High | A migration test that publishes a snapshot on V(n-1) and then applies V(n); Flyway `validate` in CI | M |
| G7 | Evidence formula constants unpinned | Scales 8, 4 and 40 and the feature-availability divisor survive mutation; only monotonicity and the asymptote are asserted | A refactor changes Evidence for every card while the suite stays green | Medium | Sentinel expectations stating each constant's meaning | S |
| G8 | Python validator weaker than the schema it feeds | `score_validation.py` does not check `archetype_deck_count` while V4 has a CHECK for it; later migrations added CHECKs too | A run file passes the Python gate and fails on `COPY`, surfacing only in stage 3 | Medium | Mirror every CHECK of V4 to V9 in the validator; a test that reads the migrations and lists CHECKs not covered | S |
| G9 | Coverage floor measures one stage | Database-stage files skip offline; `publish/postgres.py` at 22%, `score_postgres.py` at 59% in the gated run; stage 3 runs uncovered | The 95% floor overstates and understates at once; regressions in publication code bypass the gate | Medium | `--cov-append` across stages inside `demo.py verify`, report once | S |
| G10 | No score-publisher concurrency test | Catalog publication tests two publishers racing; score publication does not; the advisory lock id is a surviving mutant | Two `publish-scores` runs interleave without a test noticing | Medium | Mirror `test_publishers_serialize_while_readers_keep_previous_snapshot` for score runs | S |
| G11 | Scale unverified | All database, HTTP and browser tests use the 7-card seed; `measure_catalog.py` records p95 and EXPLAIN but asserts nothing; the one full-catalog measurement (p95 181 ms, 2026-09-28) was manual | Index misses and pagination gaps appear only with the full catalog; a slow query lands silently | Medium | Generated realistic dataset; assert index usage in the EXPLAIN JSON; a scheduled k6 run with a budget | L |
| G12 | Brittle browser assertions | Toolbar `y` must equal 60; a hover `transform` must equal an exact matrix; the toast test waits 4 real seconds; `retries: 0` | First flaky failures on slower runners, then retries get switched on and real flakes hide | Medium | `toBeInViewport`, tolerance-free semantic assertions, Playwright `clock` for the toast | S |
| G13 | Web pages have no unit coverage and only Chromium desktop coverage | `src/app` excluded from vitest coverage; one Playwright project; mobile layout checked in one journey; the CDN stub and the outbound-request guard exist only in the catalog and rankings specs, and the language spec runs no axe | A page-level regression (metadata, loading boundary, server component wiring) is caught only by a journey that happens to pass through it; WebKit and Firefox never run | Medium | Keep the exclusion but add page-level journey coverage per state; a weekly multi-browser and mobile Playwright project | M |
| G14 | No test strength signal | No mutation tool in the repository; the pilot harness lived outside it | Assertion-free or tautological tests count as coverage | Medium | mutmut or cosmic-ray, PIT, Stryker on a weekly schedule ([mutation-testing.md](mutation-testing.md)) | M |
| G15 | Windows untested in CI | CI is `ubuntu-latest`; the documented developer platform is Windows; `demo.py` has Windows-only paths (portable PostgreSQL download and checksum, `npm.cmd`, process flags) | Setup regressions reach the next contributor on the documented path | Medium | Weekly `windows-latest` job running `demo.py install` and the offline suites | S |
| G16 | Single CI job, no annotations, no timeouts | One 4-minute job; no `concurrency`, no `timeout-minutes`, no JUnit publishing; failures read from a 2,000-line log | A hung step blocks the queue; a failing test takes minutes to locate; unit and integration cannot run in parallel | Low | Two-lane layout with JUnit reporters ([ci-cd.md](ci-cd.md)) | M |
| G17 | No property-based tests | Invariants exist in prose (measurement contract, docstrings) and as example tests | Ordering, permutation and round-trip bugs between the enumerated examples | Low | Hypothesis, jqwik, fast-check on the listed properties ([advanced-testing.md](advanced-testing.md)) | M |
| G18 | No API fuzzing or contract classification | HTTP tests are hand-written; `api_contract.py` detects any drift but does not say whether it is breaking | A 500 on an unanticipated parameter combination; a breaking contract change merged as "drift accepted" | Low | Schemathesis in verify; `oasdiff breaking` on the contract in the PR lane | S |
| G19 | No pre-commit hooks or editor config | Formatting failures reach CI; `core.autocrlf=true` plus a partial `.gitattributes` means Prettier fails on a CRLF web file and Spotless on an LF Java file | Format-only CI failures; scripted edits flip line endings | Low | `pre-commit` with ruff, prettier and spotless; `.editorconfig`; broaden `.gitattributes` | S |
| G20 | `demo.py` orchestration mostly untested | Two tests cover environment selection and the seed decision; stage ordering, port checks, role grants and cleanup are proved only by running it | A change to the runner breaks verify for everyone and is diagnosed from the runner's own output | Low | Extract stage lists into testable data; a dry-run flag that prints the plan and is asserted in a test | S |
| G21 | Documentation drift undetected | `project-status-report.md` cites 39 Python tests; README floors are prose; no link checker | Stale numbers mislead a new contributor | Low | `lychee` or `markdown-link-check` weekly; this folder's rule that numbers carry dates | S |
| G22 | Parallel sessions in one checkout | On 2026-10-20 four sessions edited the same working tree; the local suites failed on others' partial work (30 i18n failures, 4 missed JaCoCo branches) | A contributor cannot trust a local red or green; CI is the only arbiter | Low | Worktrees per task; `git status` before running the gated suites ([metrics-and-process.md](metrics-and-process.md)) | S |

## Closed since 2026-10-20

| Gap | Closed on | How |
| --- | --- | --- |
| G2 | 2026-10-21 | `analytics/tests/test_boundary_values.py`: 21 tests on the valid side of every boundary the pilot found; a scratch re-run of the 24 targeted mutations killed 23, the last being equivalent (`len(rows) > size`, see the appendix) |
| G7 | 2026-10-21 | Same file: the 8, 4 and 40 saturation scales are pinned at 1 − 1/e of their weight, the feature-availability divisor at half its weight, and coverage rounding at one decimal |
| G8 | 2026-10-21 | `analytics/tests/test_score_validation_parity.py` reads every CHECK of migrations V4 to V10 (97) and maps each to a rejected mutation or a stated reason; `score_validation.py` gained the window order, event and top-cut bounds, labelled-deck bounds, finite score values and sideboard names it was missing |
| G10 | 2026-10-21 | `analytics/tests/test_score_publication_race.py`: two score publishers racing while a reader keeps the active run; `demo.py verify` runs it in stage 3 |
| G4 | 2026-10-21 (files) | `.github/dependabot.yml` and `.github/workflows/codeql.yml` committed; they act once merged to `main`. Still to do in the settings: Dependabot alerts and security updates, and branch protection (G3) |
| G19 | 2026-10-21 | `.editorconfig`, `.gitattributes` with LF everywhere but `*.cmd`/`*.bat`, 205 working-tree files converted, `.pre-commit-config.yaml` with ruff, pyright, Prettier, ESLint, Spotless and the standard hooks |
| G14 | 2026-10-21 | mutmut, PIT (`-Pmutation`) and Stryker (`npm run mutation`) configured; `.github/workflows/weekly.yml` runs them on Mondays and prints `scripts/mutation_summary.py`'s table to the job summary; first baselines in [mutation-testing.md](mutation-testing.md) |
| G5 | 2026-10-21 (except one flag) | Ruff rule sets, pyright standard mode (strict on the core), pytest-randomly and pytest-timeout, ESLint 10 with type-checked rules, `noImplicitOverride` and `exactOptionalPropertyTypes`, all in the `demo.py` build stage; pyright found 67 real issues (unguarded Optionals, variables possibly unbound, a protocol mismatch), ESLint 52. `noUncheckedIndexedAccess` stays off until the web pages under active work settle ([static-analysis.md](static-analysis.md)) |
| G9 | 2026-10-21 | `demo.py verify` keeps one coverage data file across the offline and database stages (`COVERAGE_FILE`, `--cov-append` on every database-stage pytest run) and applies the 95% floor once, after the HTTP tests (working tree 2026-10-21: offline 97.23%, merged 99%, publish/postgres.py from 22% to 98%); the merged XML and HTML land in `.local/coverage/python/` and in the `python-coverage-merged` artifact |
| G16 | 2026-10-21 | `ci.yml` rewritten: `python`, `java` and `web` jobs in parallel through `demo.py check --only`, `integration` reusing their jar, `.next` and coverage data, a `gate` job for branch protection; `concurrency` with cancel-in-progress, `timeout-minutes` on every job, JUnit XML from pytest, Surefire, vitest and Playwright annotated by `mikepenz/action-junit-report`; first run on GitHub 2026-10-22; integration green locally on 2026-10-23 once the rankings HTTP and browser specs followed the new default run and filter toolbar |

## Top five to act on

1. **G2 and G7** together: a single session of boundary and sentinel tests, with
   the appendix as the checklist. Cheapest strength gain available.
2. **G3 and G4**: branch protection, Dependabot, CodeQL. Three settings and one
   YAML file; no code changes.
3. **G5**: Ruff rule sets, pyright, ESLint. A day, mostly fixing what the tools
   find.
4. **G9 and G8**: merged coverage and validator parity, so the gate means what it
   says and run files fail early.
5. **G1 and G6**: SQL and migrations tested where they live. The longest item and
   the one that protects the serving path.

## Risks outside the test suite

- **Source access.** TopDeck and archived Wizards coverage are the only tournament
  sources; a change in their terms or shape stops ingestion. Mitigation: the
  retained bytes and manifests make every published run reproducible without the
  source; probes are opt-in and documented.
- **Research validity.** No test can show that a score formula measures what it
  claims. Sentinel tests catch regressions and conceptual failures, not truth; the
  measurement contract says so and the UI must keep saying so.
- **Single maintainer.** Review happens in sessions, not by a second person.
  Required checks, mutation scores and the review checklist in
  [metrics-and-process.md](metrics-and-process.md) stand in for a second reviewer.
