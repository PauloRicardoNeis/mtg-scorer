# Static analysis and code quality tools

Formatting is enforced in all three layers; almost nothing else is. Adding a type
checker to Python, ESLint to the web application, Error Prone and ArchUnit to
Java, and a handful of file-level linters removes a whole class of defects before
any test runs, at a cost of about a day of setup plus the fixes the tools find.
This document lists what is in place, what to add in which order, and the policy
for adopting a tool without a flag day.

## Adoption policy

1. **Baseline, then ratchet.** A new tool starts with the existing violations
   either fixed or listed in a baseline file; from then on new violations fail the
   build. Never adopt a tool in "warn only" mode for more than one release.
2. **Warnings are errors in CI.** Locally a developer may see warnings; the
   pipeline treats them as failures so they cannot accumulate.
3. **One configuration file per tool, in the layer it belongs to**, referenced
   from `scripts/demo.py` so `verify` stays the single entry point.
4. **Pre-commit runs the fast checks** (format, lint, type-check of changed
   files); CI runs everything.

## Adopted on 2026-10-21

The first wave of this document landed in one session. In the build stage of
`demo.py` (and so in CI) the chain is now: Ruff with the extended rule sets,
`ruff format --check`, **pyright** (standard mode, strict on `domain.py` and
`features.py`), the offline pytest run under **pytest-randomly** and
**pytest-timeout** (120 s), Prettier, **ESLint 10** with type-checked rules, vitest,
`next build`, `tsc` with **`noImplicitOverride`** and **`exactOptionalPropertyTypes`**.

| Tool | Decision | Why |
| --- | --- | --- |
| Ruff rule sets S, PT, SIM, C4, RUF, PL, ARG, RET, TRY, PERF, N, DTZ | on; 1,654 findings measured, 55 fixed in code, the rest removed by eight documented ignores in `analytics/pyproject.toml` | TRY003, PLC0415, PLR09xx, PLR2004, S310, S603 and RUF001-003 contradict the project's style (inline validation messages, lazy imports, named constants, https constants, deliberate full-width test strings) |
| pyright | `pyrightconfig.json` at the root, `standard` mode on `analytics/src` and `scripts`, `strict` on `domain.py` and `features.py`; 67 findings fixed, 0 left | strict everywhere measured 723 findings, 72% of them `reportUnknown*` on JSON dictionaries; standard catches the Optional, unbound and protocol errors, which is where the 67 real ones were |
| pytest-randomly, pytest-timeout | on for the offline suite (two seeds verified green); the database stages pass `-p no:randomly` through `ORDERED` in `demo.py` | the database files run one at a time against one database and document their order |
| ESLint | version 10 with `typescript-eslint` type-checked, `react-hooks` (flat recommended), `jsx-a11y`, `@next/eslint-plugin-next`, `@vitest/eslint-plugin`, `eslint-plugin-playwright`; 347 findings measured, 52 fixed in code or config, `react-hooks/error-boundaries` off for `src/app/**` | that rule reads async Server Components' try/catch as catching render errors (295 of the 347); `eslint-plugin-jsx-a11y` 6.10.2 does not yet declare ESLint 10, so `package.json` carries an `overrides` entry for its peer |
| `noImplicitOverride`, `exactOptionalPropertyTypes` | on; 0 and 2 findings | free |
| `noUncheckedIndexedAccess` | **deferred**; 52 findings in 20 files on 2026-10-21, 13 of them in `src/app` pages and components other sessions were editing that day | enable once the rankings and deck pages settle; the list is reproducible with `tsc --noEmit --noUncheckedIndexedAccess` |
| `.gitattributes`, `.editorconfig` | `* text=auto eol=lf` with CRLF only for `*.cmd` and `*.bat`; seeds and `analytics/tests/fixtures/**` stay byte-exact (`-text`); the working tree's 205 CRLF files were converted to LF on 2026-10-21 and Spotless, Ruff and Prettier re-verified | one convention on every platform ends the "Prettier fails on CRLF, Spotless fails on LF" hazard; after an attribute change git may list unchanged files as modified until `git update-index --really-refresh -- <file>` |
| pre-commit | `.pre-commit-config.yaml`: pre-commit-hooks (large files, merge markers, YAML/JSON syntax, private keys, final newline, trailing whitespace, LF), the ruff mirror pinned to the locked ruff, pyright, Prettier, ESLint and Spotless (Java files only) as local hooks; `pre-commit` 4.7.0 in the dev extra; install per clone with `analytics/.venv/Scripts/pre-commit install` | fast checks before the commit, the whole chain in CI; the hook is not installed automatically because it changes what every commit in this shared checkout does |
| Dependabot, CodeQL | `.github/dependabot.yml` (uv, npm, Maven, Actions; weekly, grouped; Next and React majors by hand) and `.github/workflows/codeql.yml` (three languages, `build-mode: none`, weekly and on pull requests) | both take effect once merged to `main`; Dependabot alerts and security updates are repository settings still to switch on |

## Python (`analytics/`, `scripts/`)

In place: Ruff lint with E, F, I, UP and B; `ruff format --check`; line length 100;
`py312` target.

| Add | Why | Sketch |
| --- | --- | --- |
| Ruff rule sets `S` (bandit), `PT` (pytest style), `SIM`, `C4`, `RUF`, `PL` (pylint subset), `ARG`, `RET`, `TRY`, `PERF`, `N`, `DTZ` | Security smells (`subprocess` without `check`, hashing), pytest idioms, dead arguments, naive datetimes (the domain requires timezone-aware timestamps) | `[tool.ruff.lint] select = ["E","F","I","UP","B","S","PT","SIM","C4","RUF","PL","ARG","RET","TRY","PERF","N","DTZ"]` with `per-file-ignores = { "tests/**" = ["S101","PLR2004"] }` |
| **pyright** in strict mode (or mypy `--strict`) | The source is fully type-hinted; `None` handling is the project's core rule and nothing checks it mechanically | `[tool.pyright] include = ["analytics/src", "scripts"]; typeCheckingMode = "strict"; pythonVersion = "3.12"`; run `pyright` in the build stage after Ruff. mypy alternative: `[tool.mypy] strict = true; packages = ["mtg_scorer"]` plus `types-jsonschema` |
| `pytest-randomly` and `pytest-timeout` | Shuffled order exposes shared state; a timeout turns a hang into a failure with a traceback | add to the `dev` extra; `[tool.pytest.ini_options] addopts = "--timeout=120"` |
| `uv lock --check` in CI | Catches a `pyproject.toml` edit without a lock update before `uv sync --locked` fails later with a less clear message | one line in the build stage |
| `pip-audit` (weekly) | Known vulnerabilities in the locked tree | `uv export --format requirements-txt \| pip-audit -r /dev/stdin` |

Expected first-run findings: pyright strict will flag `dict` access on parsed JSON
in the adapters and the `Optional` chains in `score_run.py`; budget a day.

## Java (`api/`)

In place: Spotless with google-java-format 1.25.2; Maven Enforcer requiring JDK 21;
JaCoCo report and check; private repository visibility as a compile-time boundary.

| Add | Why | Sketch |
| --- | --- | --- |
| **Error Prone** with **NullAway** | Compile-time bug patterns (misused `Optional`, format strings, equals on arrays) and null-safety on `io.mtgscorer` packages | `maven-compiler-plugin` with `<compilerArgs>-XDcompilePolicy=simple -Xplugin:ErrorProne -XepOpt:NullAway:AnnotatedPackages=io.mtgscorer</compilerArgs>` and `annotationProcessorPaths` for `com.google.errorprone:error_prone_core` and `com.uber.nullaway:nullaway`; `@NullMarked` on the package |
| `-Xlint:all -Werror` | Unchecked casts, deprecation, fall-through become build failures | compiler plugin `<showWarnings>true</showWarnings><failOnWarning>true</failOnWarning>` |
| **ArchUnit** tests | Replaces the regex scan of `check_boundaries.py` for Java with rules that see the real class graph: no cycles between capabilities, `catalog` depends on `snapshots` only through `SnapshotService`, no class in a request path uses `ProcessBuilder` or `java.net.http` | `com.tngtech.archunit:archunit-junit5` test scope; one `ArchitectureTests` class with `slices().matching("io.mtgscorer.api.(*)..").should().beFreeOfCycles()` and `noClasses().should().dependOnClassesThat().resideInAPackage("java.net.http..")` |
| **Enforcer** `dependencyConvergence` and `banDuplicatePomDependencyVersions` | The BOM pins most versions; convergence catches the ones it does not | two rules in the existing enforcer execution |
| SpotBugs (optional) | Overlaps with Error Prone; adopt only if Error Prone leaves a class of findings uncovered | `com.github.spotbugs:spotbugs-maven-plugin` with `<effort>Max</effort>` |
| OWASP dependency-check or `mvn versions:display-dependency-updates` (weekly) | CVEs and stale pins in the Maven tree | weekly lane; cache the NVD database |
| Flyway `validate` on the CI database | A changed checksum of an applied migration fails fast instead of at API start | `mvnw flyway:validate` with the CI DSN, or the API's own startup with `spring.flyway.validate-on-migrate=true` (default) kept on |

Checkstyle and PMD are not proposed: google-java-format settles style, and Error
Prone covers the bug-pattern half of PMD.

## Web (`web/`)

In place: Prettier check; `tsc --noEmit` with `strict`; `check_boundaries.py`
rules for generated DTO entry and no direct source fetches.

| Add | Why | Sketch |
| --- | --- | --- |
| **ESLint 9 flat config** with `typescript-eslint` (type-checked rules), `eslint-plugin-react-hooks`, `eslint-plugin-jsx-a11y`, `@next/eslint-plugin-next`, `eslint-plugin-playwright` for `tests/`, `@vitest/eslint-plugin` for `*.test.*` | Hook dependency arrays, `no-floating-promises`, accessible markup before axe sees it, `await`-less Playwright expectations, focused tests left behind | `web/eslint.config.mjs`; script `"lint": "eslint ."`; Next 16 no longer ships `next lint`, so ESLint runs directly |
| `tsconfig` strictness: `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride` | Array and record access on API payloads is where `undefined` slips through | `web/tsconfig.json` |
| **knip** | Unused exports, files and dependencies, which grow with every page added | `npx knip` in the weekly lane first, then the build stage |
| `npm audit --audit-level=high` (weekly) and Dependabot | `npm ci --no-audit` is right for the PR path; the audit belongs on a schedule | weekly lane |
| `stylelint` (optional) | `styles.css` and `tokens.css` are hand-written; catches invalid properties and duplicate selectors | `stylelint-config-standard` |

## SQL, workflows, documentation and repository files

| Add | Scope | Why |
| --- | --- | --- |
| **sqlfluff** (dialect `postgres`) | `api/src/main/resources/db/migration/*.sql` | Consistent casing and layout; catches a missing `IF NOT EXISTS` or an unqualified name before Flyway runs it |
| **actionlint** | `.github/workflows/*.yml` | Workflow syntax, expression typos and unknown action inputs |
| **markdownlint** and **lychee** | `docs/**/*.md`, `README.md` | Broken links and inconsistent headings; this folder's "numbers carry dates" rule is a review rule, not a lint |
| **check-jsonschema** | `contracts/*.schema.json`, `analytics/cohorts/*.json` | Already partly done by `verify_contracts.py` for the schemas; cohort files have no schema yet and would get one |
| `.editorconfig` | whole repository | `end_of_line` per path matching `.gitattributes`, so editors stop flipping CRLF and LF |
| Broaden `.gitattributes` | `*.java text eol=lf`, `*.py text eol=lf`, `*.md text eol=lf` | Today only web sources and `api/mvnw` are forced to LF; the rest follows `core.autocrlf`, which differs per machine and breaks Spotless or Prettier when a scripted edit writes the wrong ending |

## Pre-commit

A `.pre-commit-config.yaml` at the root running, on changed files only: `ruff`
(check and format), `prettier`, `pyright` (changed Python files), `eslint`,
`sqlfluff`, `actionlint`, `markdownlint`, plus `check-added-large-files` and
`detect-private-key`. Spotless has no fast changed-file mode; run
`mvnw spotless:apply` from a hook only when a `.java` file is staged. Install with
`pre-commit install`; CI runs `pre-commit run --all-files` in the PR lane so the
hooks cannot be bypassed.

## Hosted analysis

- **CodeQL** is free for public repositories and covers Java, JavaScript and
  TypeScript, and Python. Enable "default setup" in the repository's code-scanning
  settings or commit a `codeql.yml` workflow (see [ci-cd.md](ci-cd.md)).
- **SonarCloud** is also free for public repositories and would aggregate the
  three coverage reports, duplication and the rule sets above in one dashboard.
  Worth it only if a second contributor joins; otherwise the job summary tables in
  the CI design are enough.

## Order of adoption

1. Branch protection and Dependabot (settings only).
2. Ruff rule sets, pyright, `pytest-randomly`, `pytest-timeout`: one session.
3. ESLint flat config and the tsconfig flags: one session.
4. Error Prone and NullAway, ArchUnit: one session; retire the Java part of
   `check_boundaries.py` once ArchUnit covers it.
5. sqlfluff, actionlint, markdownlint, `.editorconfig`, `.gitattributes`,
   pre-commit: one session.
6. knip and the weekly audits once the weekly lane exists.
