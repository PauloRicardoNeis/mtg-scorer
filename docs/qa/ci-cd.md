# CI/CD

Until 2026-10-21 one GitHub Actions job ran the whole verification chain in about
4 minutes and had been green on the last 15 runs; nothing protects `main` from
merging without it. The pull-request lane was restructured on 2026-10-21 (in the
working tree; the first GitHub run is pending): three layer jobs run in parallel
through `demo.py check`, an integration job reuses their build outputs, and a
`gate` job is the one status branch protection needs. `python scripts/demo.py
verify` stays the single local entry point; the weekly lane for the slow signals
exists for mutation testing and is still to grow; the gates and dependency hygiene
that cost nothing but a settings change remain to be switched on.

## Today

Since 2026-10-21 (working tree; the first GitHub run is pending):

```text
push to main / pull_request          concurrency: ci-<ref>, cancel-in-progress
  ├─ python        demo.py check --only python contracts       timeout 15 min
  │                ruff → pyright → pytest+cov+junit → contracts → boundaries
  │                artifacts: python-coverage (the .coverage data), junit-python
  ├─ java          demo.py check --only java                    timeout 15 min
  │                mvn verify (Spotless, Enforcer, Surefire, JaCoCo floors, jar)
  │                artifacts: api-jar, java-reports
  ├─ web           demo.py check --only web                     timeout 15 min
  │                prettier → eslint → vitest+cov+junit → next build → tsc
  │                artifacts: web-build (.next without cache/), web-coverage
  └─▶ integration  demo.py verify --skip-install --skip-build   timeout 20 min
                   postgres:17.11 service; downloads api-jar, web-build, python-coverage
                   API on 18081 (Flyway V1..V10) → api_contract → DB-stage pytest
                   (junit, --cov-append) → seed → HTTP pytest → next start 3301
                   → playwright (junit) → measure_catalog → merged coverage report
                   with the 95% floor
                   artifacts: catalog-verification, python-coverage-merged
      └─▶ gate     green only when the four jobs succeeded; the one required status
  every job: mikepenz/action-junit-report annotates failures on the pull request
```

| Property | Until 2026-10-20 (one job) | Since 2026-10-21 |
| --- | --- | --- |
| Triggers | push to `main`, every pull request | unchanged |
| Jobs | 1 (`catalog`) | 5: `python`, `java`, `web` in parallel, then `integration`, then `gate` |
| Wall clock | 3 min 59 s (2026-10-20) | first run 2026-10-22 (red on web and java, integration skipped): layer jobs 48 to 61 s, gate at 1 min 10 s; a green run's figure is pending |
| Required for merge | nothing; `main` is unprotected | still nothing; the check to require is `CI gate` |
| Concurrency, timeouts | none | group `ci-${{ github.ref }}` with cancel-in-progress; 15 min per layer job, 20 for integration, 5 for the gate |
| Test result annotations | none; failures are read from the step log | JUnit XML from pytest, Surefire, vitest and Playwright, annotated inline by `mikepenz/action-junit-report@v5` (annotate only, with a summary table) |
| Build reuse | the single job built and ran everything | the jar and `.next` are built once, in `java` and `web`, and downloaded by `integration` |
| Python coverage | offline stage only | one data file across both stages; the floor applies once, after the HTTP tests |
| Permissions | the default token | `contents: read` |
| Dependency updates | `.github/dependabot.yml` committed 2026-10-21 (active once on `main`); alerts and security updates still off in the settings | unchanged |
| Security scanning | GitHub secret scanning; `.github/workflows/codeql.yml` committed 2026-10-21 | unchanged |
| Scheduled jobs | `.github/workflows/weekly.yml` committed 2026-10-21: mutation testing in three layers, Mondays 06:00 UTC and on demand, scores in the job summary | unchanged |
| Platforms | Linux only | unchanged |
| Deployment | none; nothing is deployed | unchanged |

What works well: one command locally and in CI, real PostgreSQL and Chromium on
every pull request, the whole chain under 5 minutes, evidence retained as
artifacts, Maven and npm caches, a checksum-verified Maven wrapper and a locked
Python environment.

## Layout: done and still proposed

```text
PULL-REQUEST LANE (every PR and push to main; target < 5 min wall clock)

  python ──────┐   ruff · pyright · pytest+cov (junit) · contracts · boundaries      [done]
  java ────────┤   spotless · mvn verify (surefire junit, jacoco) · upload jar         [done]
  web ─────────┤   prettier · eslint · vitest+cov (junit) · next build · tsc · upload .next [done]
  lint-files ──┤   actionlint · sqlfluff · markdownlint · pre-commit --all-files      [proposed]
               └─▶ integration   demo.py verify --skip-install --skip-build           [done]
                                 (reuses jar, .next and coverage data; DB-stage pytest
                                  with --cov-append; playwright junit)
                                 + schemathesis · oasdiff                             [proposed]
                   └─▶ gate      "required: all PR-lane jobs green" (branch protection) [done]

WEEKLY LANE (schedule + workflow_dispatch; never blocks a merge)

  mutation      mutmut · PIT · Stryker → per-module table in the job summary   [done]
  property-long Hypothesis max_examples=2000 · Schemathesis 500 examples
  windows       windows-latest: demo.py install + offline suites
  audit         pip-audit · npm audit · dependency-check · knip · SBOM
  scale         generated realistic dataset → pagination walk · EXPLAIN asserts · k6 budget
  flake         pytest -p randomly ×5 · playwright --repeat-each 3 on one commit

ALWAYS-ON
  Dependabot (uv, npm, maven, github-actions; grouped, weekly)
  CodeQL default setup (java-kotlin, javascript-typescript, python)
```

The layer jobs start together (three today, four with `lint-files`) and the
integration job waits for all of them; the gate is the one status branch protection
points at. The weekly lane publishes
reports and score tables in the job summary and uploads HTML reports; a threshold
is added only once a baseline exists.

### Pull-request lane details

- **Concurrency** (done): `concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }`,
  so a newer push cancels the older run of the same branch.
- **Timeouts** (done): `timeout-minutes` on every job: 15 for the layer jobs, 20 for
  integration, 5 for the gate; a hung step fails instead of occupying the queue.
- **JUnit everywhere** (done): pytest `--junitxml` into `.local/junit/pytest-<stage>.xml`
  (the offline run plus one file per database stage), Surefire's XML, vitest
  `reporters: ["default", "junit"]` into `web/reports/junit/vitest.xml`, Playwright
  `["junit", { outputFile: "test-results/junit.xml" }]`. `mikepenz/action-junit-report@v5`
  runs `if: always()` in every job with `annotate_only` (no extra permission) and
  `detailed_summary`, so failures appear inline on the pull request and as a table in
  the job summary. The workflow grants `contents: read` only.
- **Build once** (done): `java` uploads the jar, `web` uploads `.next` without its
  `cache/`, `python` uploads the coverage data; `integration` downloads the three into
  place and runs `demo.py verify --skip-install --skip-build`. Dot-directories need
  `include-hidden-files: true` on upload, or the artifact comes out empty.
- **One runner, per layer** (done): `demo.py check --only {python,contracts,java,web}`
  runs the build-stage checks of the chosen layers in their fixed order, without the
  install step. Java and web need no Python environment, so the runner skips its
  re-exec into the virtualenv and the image's Python suffices. `verify` without
  `--skip-build` still runs all four before the database stage.
- **Merged Python coverage** (done, closes G9): the offline run writes its data to
  `.local/coverage/python/.coverage` (`COVERAGE_FILE`); each database-stage pytest run
  inside `demo.py verify` adds `--cov --cov-append --cov-report= --cov-fail-under=0`
  when that file exists, and after the HTTP tests the runner writes the XML and HTML
  reports and runs `coverage report`, where the 95% floor applies once. Locally the
  same happens when `verify` follows the build stage; a `--skip-build` run without
  offline data reports nothing and says so.
- **Patch coverage comment**: `py-cov-action/python-coverage-comment-action` (or
  Codecov with the three XML and lcov files) comments the patch coverage per layer.
- **Contract classification**: `oasdiff breaking` between the checked-in contract
  and the live `/v3/api-docs`; a breaking change fails unless the pull request
  carries a `contract-breaking` label.
- **Schemathesis** against the API started by the runner, 50 examples per
  endpoint, `--checks all`.
- **Playwright hardening**: `toHaveScreenshot` for the four captured screenshots;
  `page.clock` for the toast; `toBeInViewport` instead of pixel equality.
- **Path filters are not used.** Every change runs the whole lane; the chain is
  fast enough and a filter would reintroduce the "passed because it did not run"
  failure mode.

### Weekly lane details

- `schedule: cron "0 6 * * 1"` plus `workflow_dispatch` for on-demand runs.
- **Mutation** (see [mutation-testing.md](mutation-testing.md)): three jobs in
  parallel, incremental history restored from the previous run's artifact, scores
  written with `$GITHUB_STEP_SUMMARY`.
- **Windows**: `windows-latest`, `demo.py install`, then the offline suites of all
  three layers. Covers the documented developer platform and the portable
  PostgreSQL download path when `verify` is added later.
- **Audit**: `pip-audit`, `npm audit --audit-level=high`, OWASP dependency-check
  with a cached NVD database, `knip`, CycloneDX SBOMs uploaded as artifacts.
- **Scale and performance**: generate the realistic dataset, publish it into the
  service database, walk every page, assert index usage, run k6 with the budget
  from [advanced-testing.md](advanced-testing.md), upload the trend.
- **Flake detection**: the offline suites repeated five times with
  `pytest-randomly` seeds, Playwright `--repeat-each 3` on the same commit. Any
  failure opens an issue through the job summary; see the quarantine policy.
- **Multi-browser**: Playwright projects for `firefox`, `webkit` and a mobile
  Chromium device, weekly only.

## Gates to add, in order

1. **Branch protection on `main`** (or a repository ruleset): require a pull
   request, require the status check `CI gate` (the `gate` job; green only when
   `python`, `java`, `web` and `integration` all succeeded), require branches to be up to date, block force pushes. With one
   maintainer, do not require approvals; do require the checks.
2. **Patch coverage** at or above each layer's floor, as a comment first and a
   required check after a month.
3. **Mutation score not lower** for files touched by the pull request, soft at
   first, per the policy in [mutation-testing.md](mutation-testing.md).
4. **`contract-breaking` label** required when `oasdiff` reports a breaking change.

## Dependency updates

Committed as `.github/dependabot.yml` on 2026-10-21 (React majors are also held back,
beside Next):

```yaml
version: 2
updates:
  - package-ecosystem: uv            # falls back to pip if the account's Dependabot lacks uv support
    directory: /analytics
    schedule: { interval: weekly }
    groups: { python: { patterns: ["*"] } }
  - package-ecosystem: npm
    directory: /web
    schedule: { interval: weekly }
    groups: { web: { patterns: ["*"] } }
    ignore:
      - dependency-name: next        # major Next releases by hand; see the web README
        update-types: ["version-update:semver-major"]
  - package-ecosystem: maven
    directory: /api
    schedule: { interval: weekly }
    groups: { java: { patterns: ["*"] } }
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }
```

Enable Dependabot alerts and security updates in the repository settings. Grouped
pull requests keep the noise to four per week at most, each verified by the full
PR lane. The three toolchain versions (`.python-version`, `.node-version`, the
Java version in `pom.xml` and the README) are bumped by hand, together, with a
verify run on Windows and Linux.

## Code scanning

Committed as `.github/workflows/codeql.yml` on 2026-10-21 (advanced setup; do not
also enable "default setup" in the settings, the two conflict). The workflow, with
`codeql-action` v4 and a 30-minute timeout:

```yaml
name: CodeQL
on: { push: { branches: [main] }, pull_request: {}, schedule: [{ cron: "0 7 * * 1" }] }
jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions: { security-events: write, contents: read }
    strategy: { matrix: { language: [java-kotlin, javascript-typescript, python] } }
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with: { languages: "${{ matrix.language }}", build-mode: none }
      - uses: github/codeql-action/analyze@v3
```

`build-mode: none` avoids a second Maven build; CodeQL's Java extractor reads the
sources directly.

## Workflow hygiene

- Pin third-party actions to a commit SHA (Dependabot keeps them current); the
  `actions/*` ones may stay on major tags.
- `permissions: { contents: read }` at the workflow level; raise per job only
  where needed (`security-events: write` for CodeQL, `checks: write` for the JUnit
  publisher).
- Cache the Python dependency downloads: `astral-sh/setup-uv` with
  `enable-cache: true`, or `actions/cache` on `~/.cache/uv`. `setup-python` caches
  nothing today, so the install step fetches the Python tree on every run.
- `actionlint` in the `lint-files` job.
- Keep the artifact names and paths stable; the runbook and the metrics document
  point at them.

## When deployment arrives

Nothing is deployed today, so no release pipeline exists. When hosting is decided:

1. **Build once per commit**: the jar and the `next build` output already come
   out of the PR lane; publish them as a GitHub release or container images
   tagged with the commit SHA.
2. **Smoke test is the readiness probe**: start the image against a migrated
   database and poll `/actuator/health/readiness` and the web root, exactly as
   `demo.py` does.
3. **Promote, do not rebuild**: the same artifact moves from a staging
   environment to production after the HTTP tests pass against staging.
4. **Database migrations** run by the API on start (`CATALOG_MIGRATE=true`) under
   the migration role, as today; add `flyway:validate` before the deploy step and
   keep publication in the Python worker, never in the deploy.
5. **Rollback** is re-pointing to the previous image plus `rollback_catalog` or
   `rollback-scores` for data, both already tested.
