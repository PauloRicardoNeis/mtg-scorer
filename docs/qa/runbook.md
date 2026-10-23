# QA runbook

The commands to run every check locally, the environment each one needs, where
its report lands and what to do when it fails. All commands run from the
repository root in PowerShell unless stated; on POSIX replace `.exe`, `.cmd` and
backslashes as noted. The one-command path is first; the per-layer commands follow
for fast iteration.

## Prerequisites

| Tool | Version | Check |
| --- | --- | --- |
| Python | 3.12.10 | `python --version` |
| Node and npm | 24.14.1, 11.11.0 | `node --version`, `npm.cmd --version` |
| JDK | 21 | `& "$env:JAVA_HOME\bin\java.exe" -version` |
| PostgreSQL 17 | portable download on Windows, or `CATALOG_ADMIN_DSN` to an existing server | `demo.py` handles it |

`JAVA_HOME` must point at the JDK 21 folder in every new terminal; a machine whose
default is JDK 17 fails at the Maven Enforcer with "requires Java 21". Example:

```powershell
$env:JAVA_HOME = 'C:\Users\paulo\.jdks\temurin-21.0.12.1'
```

First-time install of locked dependencies and Chromium:

```powershell
python scripts/demo.py install
```

## The whole chain

```powershell
python scripts/demo.py verify --skip-install
```

About 3 minutes on the development machine, 2 min 42 s in CI. Runs the build stage
(lint, unit suites with coverage floors, contracts, boundaries, Maven, web build,
typecheck) and then the database and browser stage against a fresh
`mtg_verify_<id>` database on ports 18081 and 3301, then reports the Python coverage merged
across both stages, where the 95% floor applies once. Ends with `Verification
passed` and the path of the retained evidence directory. Ports 18081 and 3301 must
be free; the demo on 18080 and 3300 may keep running.

Flags: `--skip-build` reuses the existing jar and `.next` output (use only when no
source changed); `--seed-sample` is for `up`, not `verify`.

## One layer at a time

```powershell
python scripts/demo.py check --only python contracts
python scripts/demo.py check --only java
python scripts/demo.py check --only web
```

`check` runs the build-stage checks of the chosen layers in the runner's fixed order
(python, contracts, java, web) without installing anything first; it is what each CI
layer job runs. `java` and `web` need no Python environment. JUnit XML lands in
`.local/junit/` (pytest) and `web/reports/junit/vitest.xml`; the offline run's
coverage data stays in `.local/coverage/python/.coverage`, where a following
`verify --skip-build` appends the database stages before reporting the merged total.

## Per-layer commands

### Python

```powershell
analytics/.venv/Scripts/python.exe -m ruff check analytics scripts
analytics/.venv/Scripts/python.exe -m ruff format --check analytics scripts
analytics/.venv/Scripts/python.exe -m pyright
analytics/.venv/Scripts/python.exe -m pytest analytics/tests -q
analytics/.venv/Scripts/python.exe -m pytest analytics/tests -q --cov --cov-config=analytics/pyproject.toml --cov-report=term-missing
```

- Plain `pytest` measures nothing; only the `--cov` form enforces the 95% floor.
  From the root, `--cov-config=analytics/pyproject.toml` is required.
- `pyright` reads `pyrightconfig.json` at the repository root (standard mode on
  `analytics/src` and `scripts`, strict on `domain.py` and `features.py`).
- The offline suite runs in a random order (`pytest-randomly`); the header prints
  `Using --randomly-seed=N`. To reproduce an order, pass `--randomly-seed=N`; to
  keep the file order, `-p no:randomly`. Every test has a 120 s timeout.
- 65 cases skip offline with a reason naming the database or API they need; that
  is expected.
- Useful flags: `--durations=10`, `-k <expr>`, `-x`, `--lf`.
- To run the database-stage files by hand against a running stack, export the
  variables `demo.py` sets: `TEST_DATABASE_DSN`, `CATALOG_TEST_ADMIN_DSN`,
  `CATALOG_TEST_PUBLISH_DSN`, `CATALOG_TEST_API_URL`, `CATALOG_TEST_PYTHON`, and
  for the import test `CATALOG_IMPORT_ADMIN_TOKEN`. The simplest way is to let
  `verify` run them.
- Reports: terminal; `verify` writes `.local/coverage/python/coverage.xml` and
  `.local/coverage/python/html/index.html`. A `.coverage` file at the repository
  root from an ad-hoc run is not the gated number.

### Contracts and boundaries

```powershell
analytics/.venv/Scripts/python.exe scripts/verify_contracts.py
analytics/.venv/Scripts/python.exe scripts/check_boundaries.py
```

Against a running API (demo on 18080 or verify on 18081), check or update the
checked-in OpenAPI contract and the generated TypeScript client:

```powershell
analytics/.venv/Scripts/python.exe scripts/api_contract.py --url http://127.0.0.1:18080
analytics/.venv/Scripts/python.exe scripts/api_contract.py --url http://127.0.0.1:18080 --update
```

After `--update`, review both `contracts/catalog-api.openapi.json` and
`web/src/lib/api.generated.ts` in the diff.

### Java

```powershell
.\api\mvnw.cmd -f api/pom.xml --batch-mode --no-transfer-progress verify
.\api\mvnw.cmd -f api/pom.xml --batch-mode test -Dtest=CursorCodecTests
.\api\mvnw.cmd -f api/pom.xml spotless:apply
```

POSIX: `bash ./api/mvnw -f api/pom.xml ...`.

- `verify` runs Spotless check, Enforcer, Surefire, the JaCoCo report and check
  (0.99 instructions, 1.00 branches) and packages the jar.
- Reports: `api/target/surefire-reports/`, `api/target/site/jacoco/index.html`.
- A Spotless failure on a file you did not touch usually means a line-ending flip;
  see the line-endings note below.

### Web

```powershell
npm.cmd --prefix web run format:check
npm.cmd --prefix web run lint
npm.cmd --prefix web run typecheck
npm.cmd --prefix web run test:unit
npm.cmd --prefix web run test:unit:watch
npm.cmd --prefix web run build
```

- `lint` runs ESLint 10 with the type-checked rules from `web/eslint.config.mjs`;
  `npx eslint --fix .` applies the safe fixes. A finding that is wrong for a reason
  gets an `eslint-disable` comment that states the reason, as the existing ones do.

- `test:unit` runs vitest with coverage and the thresholds (100 / 99 / 100 / 100
  on `lib`, `components`, `i18n`). Report: `web/coverage/index.html`.
- `format` (without `:check`) rewrites files with Prettier.
- `generate:api` regenerates the client from the checked-in contract; normally
  invoked through `api_contract.py`.

### Browser (Playwright)

The journeys need the full verify stack: a published seed, the synthetic run, the
prices, the API and `next start`. The reliable way is `demo.py verify`. To iterate
on one spec against a stack that `verify` left running or that you started by
hand with the same environment:

```powershell
$env:WEB_TEST_URL = 'http://127.0.0.1:3301'
npm.cmd --prefix web run test:e2e -- tests/rankings.spec.ts
npm.cmd --prefix web run test:e2e -- --headed --debug tests/catalog.spec.ts
```

- The catalog spec calls `scripts/e2e_control.py` through `CATALOG_TEST_PYTHON`
  and `CATALOG_TEST_PUBLISH_DSN`, so those must be set for it; the rankings,
  compare, language and primitives specs need only the URL.
- The primitives journey needs the server started with `PRIMITIVES_GALLERY=1`.
- Reports: `web/playwright-report/index.html` (`npx playwright show-report web/playwright-report`),
  traces and screenshots under `web/test-results/`.
- The demo API on 18080 serves the real catalog, not the fixtures, so the specs
  only pass against a verify-style stack.

## Databases and ports

| | Database | API | Web |
| --- | --- | --- | --- |
| Demo (`up`) | `mtg_catalog_demo` | 18080 | 3300 |
| Verify | `mtg_verify_<id>` | 18081 | 3301 |

The local cluster listens on `127.0.0.1:55432` with data under
`.local/postgres-data`; `demo.py` starts it when it is not running and leaves it
running. Stop it with `pg_ctl -D .local/postgres-data stop` using the binaries
under `.local/tools/postgresql-17.11/pgsql/bin` (or your own installation).

Verification databases are retained for diagnosis. To list and drop old ones:

```powershell
& .local/tools/postgresql-17.11/pgsql/bin/psql.exe -h 127.0.0.1 -p 55432 -U postgres -c "SELECT datname FROM pg_database WHERE datname LIKE 'mtg_verify_%' ORDER BY 1"
& .local/tools/postgresql-17.11/pgsql/bin/psql.exe -h 127.0.0.1 -p 55432 -U postgres -c "DROP DATABASE mtg_verify_<id>"
Remove-Item -Recurse .local/mtg_verify_<id>
```

## Evidence locations

| Artifact | Local path | CI artifact |
| --- | --- | --- |
| API and web logs, measurements | `.local/mtg_verify_<id>/api.log`, `web.log`, `measurements.json` | `catalog-verification` |
| Playwright report, traces, screenshots, JUnit | `web/playwright-report/`, `web/test-results/` (`junit.xml`) | `catalog-verification` |
| pytest JUnit, the offline run and one file per database stage | `.local/junit/pytest-*.xml` | `junit-python`, `catalog-verification` |
| Surefire XML | `api/target/surefire-reports/` | `java-reports` |
| vitest JUnit | `web/reports/junit/vitest.xml` | not uploaded; annotated in the `web` job |
| Python coverage, offline then merged with the database stages | `.local/coverage/python/` (`.coverage`, `coverage.xml`, `html/`) | `python-coverage`, `python-coverage-merged` |
| JaCoCo | `api/target/site/jacoco/` | `java-reports` |
| vitest coverage | `web/coverage/` | `web-coverage` |
| Catalog, score and price artifacts published by verify | `.local/mtg_verify_<id>/catalog`, `scores`, `prices` | not uploaded |

## Line endings

Since 2026-10-21 `.gitattributes` sets `* text=auto eol=lf`: every text file is LF in
the repository and in every working tree, on every platform; only `*.cmd` and `*.bat`
are CRLF, and the seeds plus `analytics/tests/fixtures/**` are byte-exact (`-text`).
`.editorconfig` tells editors the same. Prettier, Spotless and Ruff all expect LF.
Check with `git ls-files --eol -- <paths>` (the `w/` column is the working tree);
scripted edits must write `\n` (Python: `write_text(..., newline="\n")`). A tool that
writes CRLF is caught by the `mixed-line-ending` pre-commit hook, which fixes it. After
a `.gitattributes` change git can list unchanged files as modified although `git diff`
is empty; `git update-index --really-refresh -- <file>` clears that for one file at a
time without staging anything (`git add --renormalize` would stage everything).

## Pre-commit hooks

```powershell
analytics/.venv/Scripts/pre-commit.exe install
analytics/.venv/Scripts/pre-commit.exe run --all-files
```

POSIX: `analytics/.venv/bin/pre-commit`. The hooks run ruff (with fixes), pyright,
Prettier and ESLint on the staged web files, Spotless when a Java file is staged, and
the standard file checks (large files, merge markers, YAML and JSON syntax, private
keys, final newline, trailing whitespace, LF). Spotless needs Maven to start, about
20 s; the other hooks take seconds. The first run installs the hook environments.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Maven: `requires Java 21` | `JAVA_HOME` points at another JDK | Set `JAVA_HOME` in this terminal; check `java.exe` and `javac.exe` |
| `Port 18081 is already in use` | an earlier verify's API still running | Stop it (`Get-Process java`), or wait; never reuse the demo ports for verify |
| `Coverage failure: total of N is less than fail-under=95` | new code without tests, or a partial `-k` run with `--cov` | Run the whole offline suite; add tests |
| vitest: `translate every English message and nothing else` fails for every locale | `en.ts` gained keys the other locale files lack | Add the translations; the test lists the missing keys |
| JaCoCo check fails on branches | a new branch in Java without a test | Open `api/target/site/jacoco/index.html`, find the red branch |
| Spotless or Prettier fails on an untouched file | line-ending flip | `git ls-files --eol`; restore the ending |
| `Spring OpenAPI drift` | an API change without `api_contract.py --update` | Run it with `--update`, review both files |
| `Generated TypeScript drift` | contract updated but client not regenerated | `npm run generate:api` through `api_contract.py --update` |
| Playwright: `Catalog unavailable` on every page | API not ready or seed not published | Use `verify`; by hand, publish the seed and wait for readiness |
| `Dependency boundaries` failure | an import across the layering rules | Read the message; move the code or route through the public service |
| `uv sync --locked` fails | `pyproject.toml` changed without `uv lock` | `python -m uv lock --project analytics`, commit `uv.lock` |

## Mutation testing

Weekly in CI (`.github/workflows/weekly.yml`); on demand locally:

```powershell
.\api\mvnw.cmd -f api/pom.xml -Pmutation -Djacoco.skip=true --batch-mode test-compile org.pitest:pitest-maven:mutationCoverage
npm.cmd --prefix web run mutation
python scripts/mutation_summary.py --pit api/target/pit-reports/mutations.xml --stryker web/reports/mutation/mutation.json
```

- PIT takes about a minute (455 mutants, 4 threads); its report is
  `api/target/pit-reports/index.html`, its incremental history `api/.pit-history/`.
  Create that folder once if Maven complains it is missing.
- Stryker needs a green vitest run first; it stops with "failed tests in the initial
  test run" otherwise. Report: `web/reports/mutation/mutation.html`; incremental state
  `web/reports/stryker-incremental.json`; `.stryker-tmp/` is its sandbox. A run that
  reports 0% with every mutant "survived" and `testsCompleted: 0` means the Vitest 5
  patch in `web/patches/` was not applied: run `npm --prefix web ci` (its `postinstall`
  applies it) and retry.
- mutmut runs only on Linux or WSL (`uv run mutmut run`, `mutmut results`,
  `mutmut browse` from `analytics/`); its state is `analytics/mutants/`. On Windows,
  read the weekly job's summary and `mutmut` artifact instead.
- All three state folders are ignored by git; delete them to force a full run.

## Still to come

Commands to add here when each tool lands:
`schemathesis run http://127.0.0.1:18081/v3/api-docs --checks all`; the k6 script
path and the realistic-dataset generator.
