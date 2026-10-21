# QA roadmap

Four phases, each with a measurable gate before the next starts. Everything under
a day of effort comes first because it closes the known gaps; the strength signals
come second because gating on them needs a baseline; the pipeline restructure
comes third because it changes where things run, not what is verified; the long
items come last. Effort: S under a day, M one to three days, L a week or more.
Gap ids refer to [gaps-and-risks.md](gaps-and-risks.md).

```text
Phase 1  Close known gaps        ──gate──▶  Phase 2  Install strength signals  ──gate──▶
         settings, boundary tests,            mutation tools, property tests,
         static analysis, merged coverage     schemathesis; first baselines

Phase 3  Restructure the pipeline ──gate──▶  Phase 4  Verify at realistic size
         two lanes, annotations,              generated dataset, @JdbcTest,
         browser hardening, weekly lane       migrations on data, sentinels, perf
```

## Phase 1: close the known gaps

Gate: every real mutation survivor from the appendix killed; branch protection
on; one merged coverage number; pyright and ESLint clean.

| Item | Effort | Closes | Status |
| --- | --- | --- | --- |
| Branch protection on `main` requiring the CI check; Dependabot alerts and security updates on; `dependabot.yml`; CodeQL default setup | S | G3, G4 | files done 2026-10-21 (`dependabot.yml`, `codeql.yml`); settings pending, by the maintainer |
| Boundary tests for the 20 boundary survivors and sentinel tests for the 6 formula constants ([appendix](mutation-testing.md#appendix-surviving-mutants-from-the-pilot)) | S | G2, G7 | done 2026-10-21, `tests/test_boundary_values.py` |
| Score-publisher race test mirroring the catalog one | S | G10 | done 2026-10-21, `tests/test_score_publication_race.py` |
| Validator parity with every `CHECK` in V4 to V10, with a test that lists uncovered CHECKs | S | G8 | done 2026-10-21, `tests/test_score_validation_parity.py` |
| `--cov-append` across the offline and database stages in `demo.py verify`; report once | S | G9 | not started |
| Ruff rule sets, pyright (standard, strict on the core), `pytest-randomly`, `pytest-timeout` | S | G5 | done 2026-10-21 |
| ESLint 10 flat config, `noImplicitOverride`, `exactOptionalPropertyTypes` | S | G5 | done 2026-10-21; `noUncheckedIndexedAccess` deferred (52 findings in 20 files) |
| `.editorconfig`, broadened `.gitattributes`, pre-commit hooks | S | G19 | done 2026-10-21 |
| Shared name-key fixture for Python and Java | S | G1 (partial) | not started |

## Phase 2: install the strength signals

Gate: a first mutation score per layer and module recorded; Hypothesis, jqwik and
fast-check suites in the PR lane; Schemathesis green in verify.

| Item | Effort | Closes | Status |
| --- | --- | --- | --- |
| mutmut (or cosmic-ray), PIT profile, Stryker config; weekly job, report only | M | G14 | done 2026-10-21; PIT and Stryker baselines measured locally, mutmut's comes from the first Linux run |
| Hypothesis properties for scoring, cohort selection, top cut, run writing, name keys | M | G17 | not started |
| jqwik properties for `CursorCodec`, query parsing, `NameKey` | S | G17 | not started |
| fast-check properties for `format.ts`, `urls.ts`, the translator | S | G17 | not started |
| Schemathesis in verify; `oasdiff breaking` in the PR lane | S | G18 | not started |
| Error Prone with NullAway; ArchUnit replacing the Java regex boundary scan | M | G5 | not started |
| Consumer-side fixture rendering test in the web unit suite | S | G18 | not started |

## Phase 3: restructure the pipeline

Gate: pull-request wall clock at or under 5 minutes with four parallel unit jobs;
failures annotated inline; a weekly lane that has run four times.

| Item | Effort | Closes | Status |
| --- | --- | --- | --- |
| Two-lane workflow: unit jobs in parallel, integration reusing build outputs, `concurrency`, `timeout-minutes`, JUnit annotations | M | G16 | done 2026-10-21 (`ci.yml`, `demo.py check --only`); first GitHub run pending |
| Python coverage merged across stages; patch coverage comment; coverage floors raised to achieved values | S | G9 | merged coverage done 2026-10-21; comment and floors not started |
| Browser hardening: `toHaveScreenshot`, `page.clock`, `toBeInViewport`; weekly Firefox, WebKit and mobile projects | S | G12, G13 | not started |
| Weekly lane: mutation, audit and SBOM, Windows, flake repeat, knip | M | G4, G15, G14 | not started |
| sqlfluff, actionlint, markdownlint, lychee in a `lint-files` job | S | G21 | not started |
| `demo.py` dry-run plan and tests of stage ordering | S | G20 | partly: `test_demo_runner.py` (8 tests) covers layer selection and order and the coverage stages; dry-run plan not started |

## Phase 4: verify at realistic size

Gate: SQL and migrations tested against generated data of realistic size on a
schedule; sentinel calibration running on real cohorts when present; mutation
thresholds enforced on pull requests.

| Item | Effort | Closes | Status |
| --- | --- | --- | --- |
| Deterministic generator for a realistic catalog and run; weekly publication and pagination walk; EXPLAIN index assertions | L | G1, G11 | not started |
| `@JdbcTest` with Flyway on the CI PostgreSQL for every repository class | L | G1 | not started |
| Migration-on-populated-data test for each new version | M | G6 | not started |
| Sentinel calibration tests from the measurement contract, skipped without a probe directory | M | semantics | not started |
| k6 performance budget and Lighthouse CI in the weekly lane | M | G11 | not started |
| Mutation score gate on touched files; per-layer floor | S | G14 | not started |
| OWASP ZAP baseline; security headers in `next.config` | S | security | not started |
| Pseudo-localization and keyboard-only journeys | M | a11y, i18n | not started |

## Dependencies

- Phase 2 gating (on mutation score) needs Phase 2's first baseline and Phase 3's
  weekly lane to have run; it is listed in Phase 4 for that reason.
- The realistic dataset generator (Phase 4) unblocks the pagination walk, the
  EXPLAIN assertions, k6 and the migration-on-data test; build it first in that
  phase.
- ArchUnit (Phase 2) retires the Java part of `check_boundaries.py`; keep both
  until ArchUnit covers every rule the script has.

## Progress log

| Date | Item | Note |
| --- | --- | --- |
| 2026-10-18 | Mutation pilot on the analytics core | 89.7%, 35 survivors; baseline for Phase 2 |
| 2026-10-19 | QA assessment written as a Claude doc | superseded by this folder |
| 2026-10-20 | This folder written; suites measured | Python 531 cases, Java 301, web 484, browser 28 |
| 2026-10-21 | Phase 1: boundary and sentinel tests, publisher race test, validator parity | G2, G7, G8, G10 closed; 23 of 24 targeted mutants killed in a scratch re-run, the 24th equivalent |
| 2026-10-21 | Phase 1: static analysis | Ruff rule sets, pyright, pytest-randomly and pytest-timeout, ESLint 10, two tsconfig flags; G5 closed except `noUncheckedIndexedAccess` |
| 2026-10-21 | Phase 1: repository hygiene | `dependabot.yml`, CodeQL workflow, `.editorconfig`, LF-everywhere `.gitattributes` (205 files converted), pre-commit config; G19 closed, G4 waits on settings |
| 2026-10-21 | Phase 2: mutation tooling | mutmut, PIT and Stryker configured, `weekly.yml` with the job summary; baselines Java 90.5% (455 mutants), web 83.2% (2,511 mutants); Python's comes from the first Linux run |
| 2026-10-21 | Phase 3: pipeline restructure | `demo.py check --only`; `ci.yml` with `python`, `java` and `web` in parallel, `integration` reusing the jar, `.next` and coverage data, and `gate`; concurrency, timeouts, JUnit annotations; Python coverage merged across stages (working tree 2026-10-21: offline 97.23%, merged 99%, publish/postgres.py from 22% to 98%); G9 and G16 closed; wall clock to be measured on the first run |
