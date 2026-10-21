# Mutation testing

Line and branch coverage sit between 97% and 100% in every layer, so coverage can
no longer tell a strong test from a weak one. A mutation pilot on the analytics
core on 2026-10-18 killed 89.7% of 341 mutants; the 35 survivors are untested
boundaries and unpinned constants, not untested code. This document records the
pilot, sets one tool per layer with a weekly reporting run before any gate, and
lists every survivor with the test that kills it.

## Pilot results (2026-10-18)

A small AST mutator, run from outside the repository, generated one mutant per
operator site over 11 modules: comparison swaps, `+` and `-`, `*` and `/`, `and`
and `or`, `not` removal, and numeric constants plus one. Each mutant ran the tests
that exercise its module; survivors were re-run against the whole offline suite and
none was caught there either. 341 mutants, 306 killed, 35 survived, 6 minutes on
4 workers.

| Survivors by module | Count | Kind |
| --- | --- | --- |
| `scoring/foundation.py` | 9 | 6 formula constants and rounding digits, 3 equivalent |
| `tournament_features.py` | 7 | cohort window and coverage boundaries, one-of cards, archetype count |
| `ingest/topdeck.py` | 6 | top-cut size, tie at the cut, bracket columns |
| `domain.py` | 6 | valid-side boundaries (rank 1, round 1, zero games, copy counts), 1 equivalent |
| `features.py` | 4 | `opportunity_count` boundary, 2 ignorable defaults |
| `scoring/max_ratio.py`, `publish/score_run.py`, `publish/score_postgres.py` | 1 each | equivalent (empty stratum, excluded events, advisory lock id) |
| `scoring/registry.py`, `scoring/base.py`, `publish/score_validation.py` | 0 | every flip breaks an existing rejection test |

Per-module mutant totals were not retained from the pilot; only the overall totals
and the survivor list (appendix) are exact. Cohort selection and feature
validation had the lowest scores because both are comparisons against thresholds
and the tests stop at the invalid side of each threshold; the three modules with
no survivor are small and validation-heavy. Of the 35 survivors, 26 are real gaps
(20 boundaries, 6 formula constants) and 9 are equivalent mutants or defaults not
worth a test.

The modules added since the pilot (`scoring/signature.py`, `scoring/hidden_gem.py`,
`scoring/constructed.py`, `scoring/overall.py`, `publish/overall_run.py`,
`ingest/wizards.py`) were never mutated and are the first targets of the first
real run.

## Tool per layer

| Layer | Tool | Scope to mutate | Tests to run | Run mode | Gate |
| --- | --- | --- | --- | --- | --- |
| Python | **mutmut 3** in CI (needs `fork`, so Linux only) or **cosmic-ray** for Windows parity | `scoring/`, `features.py`, `tournament_features.py`, `ingest/topdeck.py`, `ingest/wizards.py`, `publish/score_run.py`, `publish/score_validation.py`, `publish/overall_run.py`, `domain.py` | offline suite only; exclude the six database- and API-gated files | weekly full run; on pull requests touching those paths, mutants in the diff only | report first; then the score must not drop for touched files; floor 85% after one baseline |
| Java | **PIT** (`pitest-maven` with `pitest-junit5-plugin`) in a `mutation` Maven profile | `io.mtgscorer.api.catalog.*`, `rankings.*`, `error.*`, `snapshots.*` | fast unit classes only; exclude `ApiApplicationTests` and the OpenAPI tests that boot a context | weekly, `withHistory` for incremental runs | same policy; `CursorCodec`, `CatalogQuery`, `RankingQuery`, `NameKey` are the classes to watch |
| Web | **Stryker** with `@stryker-mutator/vitest-runner` | `src/lib/**`, `src/components/**`, `src/i18n/**`, excluding tests and `api.generated.ts` | vitest suite | weekly, `incremental: true` | same policy |

### Configuration as committed on 2026-10-21

| Layer | Where | What it says |
| --- | --- | --- |
| Python | `[tool.mutmut]` in `analytics/pyproject.toml` | mutmut 3.8: `source_paths = ["src/mtg_scorer/"]`, `only_mutate` listing the nine core modules (domain, features, tournament features, every scoring module, the TopDeck and Wizards adapters, run writing, validation, the Overall run), `also_copy = ["seeds/", "cohorts/"]`, pytest without random order or cache. mutmut copies the sources into `analytics/mutants/` and runs the tests from there, so both validators now find `contracts/` by walking up (`contracts_dir()` in `publish/validation.py`) instead of counting four parents |
| Java | profile `mutation` in `api/pom.xml` | pitest-maven 1.19.1 with pitest-junit5-plugin 1.2.2; targets `io.mtgscorer.api.*` minus the application class and `config.*`; test classes minus `ApiApplicationTests` and `config.*`, which boot a Spring context; `DEFAULTS` mutators, 4 threads, HTML and XML reports without timestamps in `api/target/pit-reports/`, incremental history in `api/.pit-history/history.bin` |
| Web | `web/stryker.config.json`, `npm run mutation` | Stryker 10 with the vitest runner over `vitest.config.ts`; mutates `src/lib`, `src/components` and `src/i18n` minus tests, the generated client and the message files (data); `perTest` coverage analysis, static mutants ignored, incremental state in `web/reports/stryker-incremental.json`, HTML and JSON reports in `web/reports/mutation/` |
| Summary | `scripts/mutation_summary.py` | reads mutmut's `mutmut-cicd-stats.json`, PIT's `mutations.xml` and Stryker's `mutation.json` into one Markdown table; the weekly jobs append it to the job summary; tested by `analytics/tests/test_mutation_summary.py` |
| Schedule | `.github/workflows/weekly.yml` | three jobs on Mondays at 06:00 UTC and on demand, each restoring its incremental state from the Actions cache, printing the table and uploading the reports; 45 to 60 minute timeouts; never required for a merge |

mutmut needs `fork`, so it runs on Linux (the weekly job) or under WSL; on Windows it
refuses to start. PIT and Stryker run anywhere.

**Stryker on Vitest 5 needs a patch.** Vitest 5 matches `testNamePattern` against the
suite chain joined with `' > '`; `@stryker-mutator/vitest-runner` 10.0.0 still joins it
with a space, so the per-mutant test filter matches nothing, zero tests run and every
covered mutant is reported as survived (stryker-js issue
[#6210](https://github.com/stryker-mutator/stryker-js/issues/6210), fix in PR #6214,
unreleased on 2026-10-21). The first run here scored 0% for exactly that reason.
`web/patches/@stryker-mutator+vitest-runner+10.0.0.patch` changes both copies of
`collectTestName` to join with `' > '`; `patch-package` applies it from the
`postinstall` script on every `npm ci`. Drop the patch, `patch-package` and the script
once a runner release includes the fix.

## Baseline (2026-10-21)

Measured on the development machine (Ryzen 7 7800X3D, Windows 11) from the
`feat/all-formats` working tree, with the configuration above.

| Layer | Tool | Mutants tested | Killed | Survived | No coverage | Score | Run time |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Java (api) | PIT 1.19.1 | 455 | 412 | 40 | 3 | 90.5% | 1 min 05 s, 4 threads |
| Web (lib, components, i18n) | Stryker 10.0.0 | 2,511 | 2,089 | 369 | 53 | 83.2% | 9 min 24 s, 15 runners |
| Python (analytics core) | mutmut 3.8.0 | first weekly run on Linux | | | | pilot: 89.7% on 2026-10-18 | |

**Java survivors, by kind.** 17 `EmptyObjectReturnVals` in the repositories
(`RankingRepository` 8, `DeckRepository` 5, `CatalogRepository` 4, `CommanderRepository`
4, `CompareRepository` 3): the repository tests assert the SQL text and the bound
parameters but not the rows the mapper returns, so a repository that returns an empty
list passes. 12 `ConditionalsBoundary` in `CompareQuery`, `RankingQuery`, `CursorCodec`
and `CommanderQuery`: the same valid-side boundary gap the Python pilot had, now on
limits and ranges parsed from the query string. 9 `RemoveConditional` (equal-else) and
one each of null and boolean returns. The three uncovered mutants are in `DeckQuery`
and `DeckService`, code another session added that day.

**Web.** Measured after the Vitest 5 patch; the first run scored 0% for the reason above. The dry run excluded the i18n parity test, which another session's unfinished translations were failing that day, and 175 static mutants were ignored (`ignoreStatic`). Survivors concentrate in two tables: `compare-table.tsx` (95 of 275 tested) and `commander-table.tsx` (59 of 115), whose tests render the happy path and check a few cells; then `ranking-filters.tsx` (40 of 336), `translator.ts` (28 of 72), `format.ts` (23 of 172), `compare-filters.tsx` and `card-decks.tsx` (22 each). `lib/metagame.ts` has no tests at all (25 uncovered), code added the same day. By mutator: 98 `ConditionalExpression` (branches rendered but never asserted on both sides), 76 `StringLiteral` (class names and labels no test reads), 46 `EqualityOperator`, 32 `ArrowFunction`, 24 `ArithmeticOperator`. The pattern matches the Java and Python survivors: boundaries and branches tested from one side only.

## How to read a run

Survivors fall into three classes; only the first two deserve work.

- **Boundary survivors** (`<` to `<=`, a constant plus one): add a test on the
  valid side of the boundary. 26 of the pilot's 35.
- **Formula survivors** (a weight, a scale, a divisor): pin the constant with a
  sentinel expectation that states what the number means, for example "8 decks
  alone give 63.2% of the deck weight".
- **Equivalent mutants** (a `default=` that only matters for an empty input, an
  unreachable clamp, the advisory lock id): mark them ignored in the tool's
  configuration with one line saying why, and never chase them.

**Operator set.** Each tool's default operators are enough; the pilot used
comparison swaps, arithmetic swaps, boolean swaps, `not` removal and numeric
constants. Return-value and statement-deletion mutators inflate the count with
trivial kills and are worth turning off for the Python core.

**Cost.** The pilot ran 341 mutants in 6 minutes on 4 workers with targeted test
selection. A weekly run across all three layers fits inside a 30-minute job; PIT's
history and Stryker's incremental mode keep later runs shorter.

## Gating policy

1. First run: report only, publish the HTML reports as artifacts and a per-module
   score table in the job summary. Record the baseline in
   [metrics-and-process.md](metrics-and-process.md).
2. Second month: on pull requests that touch a mutated path, run the diff's
   mutants and fail if the score of a touched module drops below its baseline.
3. After the weekly number has been stable for a month: a floor per layer (85%
   Python core to start, set from the first real run, never from a guess).

## Appendix: surviving mutants from the pilot

Every survivor with the test that kills it, paths relative to
`analytics/src/mtg_scorer`. Line numbers are from the 2026-10-18 tree and have
shifted since. 26 were real gaps, 9 equivalent or ignorable. On 2026-10-21
`analytics/tests/test_boundary_values.py` added a test for every gap row; applying
the same 24 mutations to a scratch copy of the package killed 23, and the one
survivor (`len(rows) > size`) proved equivalent under the current code. Two rows
were already dead by then: a missing `topCut` has its own test, and the bracket
column flip now fails with a `TypeError` on the existing fixtures.

| File:line | Mutation | Verdict | Test that kills it |
| --- | --- | --- | --- |
| `scoring/foundation.py:19` | `>` to `>=` on the weight-sum tolerance | equivalent | none; the exact 1e-9 boundary is unreachable |
| `scoring/foundation.py:147` | feature-availability divisor 2.0 to 3.0 | gap | pin the feature-availability term of Evidence against `evidence_feature_availability` |
| `scoring/foundation.py:150` | deck scale 8.0 to 9.0 | gap | 8 decks alone give `100 × evidence_decks × (1 − e^−1)` within 0.05 |
| `scoring/foundation.py:151` | event scale 4.0 to 5.0 | gap | 4 events alone give `100 × evidence_events × (1 − e^−1)` |
| `scoring/foundation.py:153` | match scale 40.0 to 41.0 | gap | 40 full-field matches alone give `100 × evidence_matches × (1 − e^−1)` |
| `scoring/foundation.py:171` | rounding digits 1 to 0 on staple coverage | gap | a coverage that is not a whole number keeps one decimal |
| `scoring/foundation.py:172` | rounding digits 1 to 0 on build-around coverage | gap | same assertion on the build-around side |
| `scoring/foundation.py:228` | `<=` to `<` on `count <= 0` | equivalent | `1 − e^0` is already 0 |
| `scoring/foundation.py:234` | clamp 100.0 to 101.0 | equivalent | weighted means of values in [0, 1] never exceed 100 |
| `scoring/max_ratio.py:63` | `default=0` to 1 on the leader | equivalent | only reached with an empty stratum, which yields no scores |
| `features.py:18` | default `support` 0 to 1 | ignore | default value only; optionally assert `known(0.5).support == 0` |
| `features.py:26` | `<` to `<=` and 0 to 1 on `opportunity_count` (2 mutants) | gap | `opportunity_count=0` with `support=0` is valid |
| `features.py:44` | default `support` 0 to 1 in `known()` | ignore | same as line 18 |
| `tournament_features.py:53` | `<=` to `<` on `min_decklist_coverage` | gap | `min_decklist_coverage=1.0` is accepted |
| `tournament_features.py:138` | `<=` to `<` on `starts_on` | gap | an event dated exactly `starts_on` is included |
| `tournament_features.py:138` | `<` to `<=` on `ends_before` | gap | an event dated exactly `ends_before` is excluded |
| `tournament_features.py:143` | `<` to `<=` on coverage | gap | coverage equal to the minimum is included |
| `tournament_features.py:156` | `mainboard_count > 0` to `> 1` | gap | a deck with one copy of a card counts that card |
| `tournament_features.py:158` | name counter `+= 1` to `+= 0` | gap | the majority name wins over the alphabetically first one |
| `tournament_features.py:186` | `(None, 0)` to `(None, 1)` | gap | unlabelled decks have `archetype_deck_count == 0`, and `score_validation.py` enforces it |
| `ingest/topdeck.py:173` | `or 0` to `or 1` on `topCut` | gap | an event without a cut has `top_cut_size == 0` |
| `ingest/topdeck.py:196` | `and` to `or` on bracket columns | gap | a row with `winsBracket` but no `lossesBracket` is not a bracket record |
| `ingest/topdeck.py:204` | `>` to `>=` on `len(rows) > size` | equivalent (2026-10-21) | when the cut equals the field, the wins comparison runs over an empty tail and is always false, so the result is the same; the equal-size test exists anyway |
| `ingest/topdeck.py:204` | `<` to `<=` on the wins comparison | gap | a wins tie across the cut boundary keeps `STANDING_ORDER` (the docstring allows ties; only a player below the cut with *more* wins contradicts the order) |
| `ingest/topdeck.py:204` | `default=0` to 1 (2 mutants) | gap | covered by the two tests above |
| `publish/score_run.py:150` | `or 0` to `or 1` on `player_count` | equivalent | zero-player events are excluded by coverage before summing |
| `publish/score_postgres.py:21` | `LOCK_ID` 724603 to 724604 | equivalent offline | only a database race test with two publishers can exercise it |
| `domain.py:84` | `or` to `and` on the tzinfo check | equivalent in practice | a tzinfo whose `utcoffset()` is None is exotic |
| `domain.py:160` | `+` to `-` on copy counts | gap | a `DeckCard` with equal mainboard and sideboard counts is valid; assert `total_count` |
| `domain.py:216` | `final_rank <= 0` to `<= 1` | gap | `final_rank=1` is valid |
| `domain.py:248` | `games_won < 0` to `< 1` and 0 to 1 (2 mutants) | gap | `games_won=0` is valid |
| `domain.py:272` | `round_number`/`table_number` `<= 0` to `<= 1` | gap | round 1 and table 1 are valid |
