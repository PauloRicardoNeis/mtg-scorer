# Metrics and process

Four numbers tracked over time, three checklists, one flaky-test rule and a weekly
cadence are enough process for a project of this size. Anything more would cost
more to maintain than the defects it would catch.

## Test analytics

| Metric | Source | Where it shows | Act when |
| --- | --- | --- | --- |
| Suite duration per layer | pytest `--durations=10` and JUnit XML timings, Surefire reports, vitest JUnit reporter, Playwright JUnit reporter | One line per layer in the job summary; the ten slowest tests listed on every run | A layer doubles, or the pull-request wall clock passes 5 minutes |
| Flake rate | Weekly repeat run: offline suites five times with `pytest-randomly` seeds, Playwright `--repeat-each 3`, on one commit | Failures with no code change, listed in the weekly summary | Any test fails once in the repeat run: fix it or quarantine it with an issue, never add retries |
| Coverage by stage | Merged Python `coverage.xml` (offline plus database stages; written by `demo.py verify` since 2026-10-21), JaCoCo XML, vitest lcov | Patch-coverage comment on the pull request; totals in the job summary | Patch coverage below the layer's floor, or a total within 0.5 points of its floor (raise the floor or add tests) |
| Mutation score per module | mutmut, PIT and Stryker reports | Table in the weekly job summary; previous run kept as an artifact for comparison | A module touched by the pull request drops |

Baselines as of 2026-10-20: Python offline 19.5 s with coverage and 97.08%
coverage (2026-10-21: 97.23% offline, 99% merged with the database stages); Java 11.7 s of test time and 99.7% / 99.4% (working tree); web 8.9 s;
verify step in CI 2 min 42 s; CI wall clock 3 min 59 s; flake rate not yet
measured. Mutation scores on 2026-10-21: Java 90.5% (PIT, 455 mutants), web
83.2% (Stryker, 2,511 mutants); Python awaits the first weekly Linux
run, with the 2026-10-18 pilot's 89.7% as the reference.

Two plugins make the Python suite self-diagnosing at no cost: `pytest-randomly`
shuffles test order on every run and exposes shared-state dependence;
`pytest-timeout` turns a hang into a failure with a traceback.

The CI artifacts (`catalog-verification`, `java-reports`, `web-coverage`,
`python-coverage-merged`, the JUnit files, and the retained `.local/mtg_verify_<id>`
directories) already hold the raw material for all four
metrics; the work is to print them in the job summary and keep the previous run
for comparison.

## Pull-request checklist

The author confirms before requesting review or merging:

- [ ] `python scripts/demo.py verify --skip-install` passed locally, or the CI run
      on the branch is green.
- [ ] Every new behaviour has a test in the layer the
      [test strategy](test-strategy.md) assigns it; every threshold has a test on
      both sides.
- [ ] A bug fix adds the regression test first and shows it failing in the first
      commit.
- [ ] Contract changes: `api_contract.py --update` run, the regenerated client
      reviewed, `oasdiff` consulted for breaking changes, the OpenAPI tests
      updated.
- [ ] Migration changes: the Python validator mirrors every new `CHECK`; the
      publication tests exercise the new columns.
- [ ] Measurement contract or README updated when semantics changed.
- [ ] New strings go through the translator and every locale file; the i18n
      parity test passes.
- [ ] No new skip without a reason naming the missing resource; no `retries`, no
      `sleep` in assertions.
- [ ] Fixtures added carry source, date, hash and attribution.
- [ ] `git status` shows only this change; nothing from another session rides
      along.

## Review checklist

The reviewer, or the author reviewing their own diff a day later, asks:

1. Does each test name a behaviour, and would it fail if the behaviour broke?
   Read the assertion before the setup.
2. Is the boundary tested from both sides? Is the constant pinned with a sentinel
   that states its meaning?
3. Could this logic have been tested one layer lower? (SQL in HTTP tests, scoring
   through the API, page logic through Playwright are smells.)
4. Does any test depend on wall-clock time, network, locale of the machine or
   test order? Is the browser suite's single-worker ordering respected?
5. Does an unknown become a zero anywhere? Does a `None` get a default?
6. Is provenance kept: hashes, timestamps with zone, parser and config versions?
7. Would the error be diagnosable from the artifacts alone?
8. Is anything added to the request path that belongs in the batch pipeline?

## Defect handling

- **Every bug gets a regression test** at the layer where it was observable
  first, committed before the fix, named after the symptom.
- **Severity** by the question "what did the user or the published data see":
  wrong published number (highest), wrong page or error (high), wrong message or
  layout (medium), developer-only (low).
- **Root cause in the commit message**, one sentence, so the next reader of
  `git log` learns why, not only what.

## Flaky tests and quarantine

1. A test that fails without a code change is a defect. Capture the artifacts
   from the failing run.
2. Quarantine within the day: skip it with the issue number in the reason. The
   suite stays green and honest about what it is not checking.
3. Fix or delete within two weeks. The weekly summary lists quarantined tests and
   their age.
4. Retries stay off everywhere. A test fixed by a retry is still broken.

## Cadence

| When | What | Output |
| --- | --- | --- |
| Every pull request | PR lane; author checklist | Green gate or a fix |
| Every merge to `main` | Same lane on `main`; artifacts retained 90 days | Baseline for the next comparison |
| Weekly (Monday) | Weekly lane: mutation, audit, Windows, scale, flake; Dependabot pull requests | Job summaries read, one issue per finding worth acting on, dependency pull requests merged or closed |
| Monthly | Review the four metrics against last month; raise coverage floors to the achieved value rounded down; adopt the next roadmap item | A short note appended to [roadmap.md](roadmap.md) |
| Quarterly | Backup and restore drill; re-read the measurement contract against the tests that claim to protect it; prune quarantined tests | Runbook updated |

## Ownership

One maintainer owns everything today. The documents stand in for a second
reviewer: required checks enforce the strategy, the checklists enforce the
review, the weekly lane enforces the slow signals. If a second contributor joins,
`CODEOWNERS` maps `analytics/` , `api/` and `web/` and the review checklist becomes
a pull-request template.

## Working-tree hygiene for parallel work

Several sessions editing one checkout make the local suites fail on each other's
partial work; on 2026-10-20 that produced 30 i18n failures and 4 missed JaCoCo
branches that belonged to nobody's finished change.

- Each task in its own git worktree when more than one task is active; the
  worktree's branch is what CI verifies.
- Before running a gated suite in a shared checkout, `git status`; if files from
  another task are modified, run the suite in CI on the pushed branch instead and
  treat the local result as informational.
- Never regenerate shared artifacts (`contracts/catalog-api.openapi.json`,
  `web/src/lib/api.generated.ts`) in a checkout where another task has API changes
  in flight.
- Score runs published to a shared development database change the active run for
  every session using it; announce or use a per-task database.

## Evidence retention

- CI artifacts: 90 days (the default) for the pull-request lane's artifacts
  (`catalog-verification`, `python-coverage-merged`, `java-reports`, `web-coverage`
  and the rest);
  weekly reports 1 year, so year-over-year mutation and performance trends exist.
- Local `.local/mtg_verify_<id>` directories and databases: delete those older
  than a week; the runbook has the command.
- Measured numbers in these documents carry their date and origin; a number that
  has no date is a target.
