# 1. Project overview

## Purpose

MTG Scorer is a historical analytics engine for Magic: The Gathering. Its question
is not "which card is strongest" in the abstract but "which cards have a competitive
pedigree, in which strategies, with how much evidence". The immediate use case is
Forge Adventure / Quest players choosing what to build around from a limited card
pool; the broader goal is a discovery engine that separates ubiquitous good cards
from cards that belong to distinctive strategies, and that can always show the
observations behind every number.

Three commitments shape everything downstream, and the
[measurement contract](../measurement-contract.md) states them as rules:

1. **Unknown is not zero.** A card with no recorded matches has no win rate, not a
   win rate of 0. Every feature carries a value or `None`, a support count and,
   where meaningful, a denominator. Every score output is `None` when it cannot be
   computed.
2. **Everything is relative to a bounded population.** Lifetime incidence across
   decades, formats and sources is meaningless. Counts are made inside one cohort
   and compared with that cohort's field.
3. **Everything is reproducible.** Raw responses are kept with their hashes. Every
   run file is named by a hash of the dataset, parser, feature pipeline, cohort
   rules, population rule and each method's version and configuration hash. A
   changed setting is a new configuration, never a silent edit.

## The three applications

| Application | Language | Owns |
| --- | --- | --- |
| `analytics/` | Python 3.12 | Ingestion, facts, cohort selection, features, every score formula, run files, publication to PostgreSQL |
| `api/` | Java 21, Spring Boot | Catalog, rankings, compare, commander and deck endpoints over published PostgreSQL rows; ranks, sorts and filters in SQL; computes no score |
| `web/` | TypeScript, Next.js | The pages: rankings, compare, commanders, card detail with decklists, dataset provenance; letter grades, tones and number formatting |

[ADR 0001](../adr/0001-polyglot-application-boundary.md) fixes the boundary: an
HTTP request never runs Python, Java never reimplements a score formula, and every
published row stays attributable to the versions that produced it. The API's only
arithmetic is a `rank()` window, the difference against the previous run's rank, an
average of stored counts (copies per deck) and score per dollar.

## The pipeline, stage by stage

```text
1. Probe            scripts/probe_tournaments.py, scripts/probe_wizards_coverage.py
   Saves raw responses/pages plus manifest.json with each file's SHA-256.
   Opt-in, never in CI. The API key is never written.

2. Adapter          analytics/src/mtg_scorer/ingest/topdeck.py, ingest/wizards.py
   Verifies every file against the manifest, parses it into source-independent
   facts (Tournament, DeckEntry, Standing) with coverage and provenance, and
   derives a dataset_snapshot_id from the source, parser version and file hashes.

3. Cohort           analytics/src/mtg_scorer/tournament_features.py  (select_cohort)
   Applies a cohort rules file (analytics/cohorts/*.json): format, window,
   minimum decklist coverage, explicit exclusions, players per game.

4. Usage            tournament_features.py  (card_usage, cohort_performance)
   Per card: decks, events, copies, playsets, top cuts with their denominator,
   archetype labels, match record, trend series. Per cohort: the field's record,
   top-cut rate, archetype cores and concentration, trend denominators.

5. Features         tournament_features.py  (card_features, card_performance)
   The missing-aware feature vector each method consumes, and the descriptive
   performance statistics the site shows (win rate, delta, 95% interval,
   top-cut lift, trend).

6. Scoring          analytics/src/mtg_scorer/scoring/*.py
   Every registered method scores the population (mainboard cards minus basic
   lands) and returns named outputs plus the inputs that explain them.

7. Run file         analytics/src/mtg_scorer/publish/score_run.py
   <score_run_id>.json: cohort summary, decks, cards with usage, each method's
   scores. Validated against contracts/score-run.schema.json and relationship
   checks before it is written.

8. Overall run      analytics/src/mtg_scorer/publish/overall_run.py
   Combines one run per format into the "Overall" run with the Overall grade.

9. Publication      analytics/src/mtg_scorer/publish/score_postgres.py
   Stages the rows, verifies counts, promotes atomically; one active run per
   (source, format); guarded rollback.

10. API             api/src/main/java/io/mtgscorer/api/rankings/*.java
    Ranks the active (or a pinned) run's scored cards by one method's output.

11. Web             web/src/app/rankings/*, web/src/components/ranking-*.tsx
    Letter grades, tones, sparklines, format bars, compare and commander views.
```

Stages 2 to 8 are pure functions of their inputs; given the same saved responses
and the same rules they produce byte-identical files, and `write_score_run`
refuses to overwrite a file of the same identity with different contents.

## Identity and reproducibility

Each layer names what it depends on, and the names compose:

| Identity | Hashes | Where |
| --- | --- | --- |
| `dataset_snapshot_id` | source, parser version, the sorted list of raw file names and SHA-256s | `ingest/topdeck.py`, `ingest/wizards.py` |
| `cohort_rules_hash` | the complete `CohortRules` dataclass as canonical JSON | `tournament_features.py` via `config_fingerprint` |
| `method_config_hash` | the complete configuration dataclass of a method, including its version label | `scoring/base.py` `config_fingerprint` |
| `feature_pipeline_version` | a hand-maintained label, `card-usage-v8` today | `tournament_features.py` |
| `score_run_id` | `scores-` + SHA-256 of {dataset snapshot, parser version, feature pipeline version, cohort rules hash, population rule, [method id, version, config hash]...} | `publish/score_run.py` |
| `results_sha256` | the whole run file except raw-file retrieval metadata | `publish/score_run.py` |

`config_fingerprint` serialises a frozen dataclass with `dataclasses.asdict`,
`sort_keys=True` and compact separators, then takes SHA-256. Because the version
label is part of the dataclass, two configurations with the same label but
different weights hash differently, which is the point: a familiar label cannot
conceal changed weights.

## Where to look

| Question | File |
| --- | --- |
| What facts exist and what they may contain | `analytics/src/mtg_scorer/domain.py` |
| The feature vector and its missingness rules | `analytics/src/mtg_scorer/features.py` |
| Cohort selection, usage counts, performance, features | `analytics/src/mtg_scorer/tournament_features.py` |
| The method contract, percentiles, run assembly | `analytics/src/mtg_scorer/scoring/base.py` |
| The registered methods | `analytics/src/mtg_scorer/scoring/{constructed,signature,hidden_gem,max_ratio,foundation}.py` and `registry.py` |
| The overall grade | `analytics/src/mtg_scorer/scoring/overall.py`, `publish/overall_run.py` |
| Run files and validation | `analytics/src/mtg_scorer/publish/score_run.py`, `score_validation.py`, `contracts/score-run.schema.json`, `contracts/overall-run.schema.json` |
| Publication | `analytics/src/mtg_scorer/publish/score_postgres.py`, `api/src/main/resources/db/migration/V4__score_publication.sql` and later |
| Ranking SQL and query bounds | `api/src/main/java/io/mtgscorer/api/rankings/RankingRepository.java`, `RankingQuery.java` |
| Cross-format comparison | `CompareRepository.java`, `CompareQuery.java` |
| Commander rankings | `CommanderRepository.java` |
| Letter grades, tones, number formatting | `web/src/lib/format.ts` |
| Which methods carry grades and the default method | `web/src/components/ranking-data.tsx` |
| Prices | `analytics/src/mtg_scorer/publish/prices.py` |
| Cohort rules in use | `analytics/cohorts/*.json` |

## Commands

All commands run from the repository root. The analytics environment is the
locked `uv` project; `analytics/.venv/Scripts/python.exe` is its interpreter on
Windows.

Score one cohort of saved TopDeck responses into a run file:

```bash
analytics/.venv/Scripts/python.exe -m mtg_scorer.cli score-topdeck --source-dir analytics/data/local/<probe-dir> --cohort analytics/cohorts/topdeck-modern-2024-01-to-2026-09.json --output-root analytics/data/local/score-runs
```

Combine the active format runs into the overall run:

```bash
analytics/.venv/Scripts/python.exe -m mtg_scorer.cli score-overall --active-runs-dir analytics/data/local/score-runs --output-root analytics/data/local/score-runs
```

Publish a run file and make it active:

```bash
analytics/.venv/Scripts/python.exe -m mtg_scorer.cli publish-scores --run-file analytics/data/local/score-runs/<score_run_id>.json
```

`publish-scores` and `score-overall --active-runs-dir` read `SCORE_PUBLISH_DSN`;
`score-wizards` reads `CATALOG_READ_DSN` to resolve card names. See the
[analytics README](../../analytics/README.md) and the
[local runbook](../local-catalog.md) for the environment.

Run the scoring tests alone:

```bash
analytics/.venv/Scripts/python.exe -m pytest analytics/tests -q -k "score or feature or overall or domain"
```

## How the pieces are tested

- `tests/test_score_methods.py` holds contract tests parametrised over every
  registered method: each scores every card exactly once with exactly its declared
  outputs, carries its complete identity, is deterministic, describes itself for a
  methodology page, and scores an empty population as an empty run.
- Each method has its own file of pairwise expectations (`test_constructed_score.py`,
  `test_signature_score.py`, `test_hidden_gem_score.py`, `test_overall_score.py`,
  `test_scoring.py` for the foundation model) in the style the measurement contract
  asks for: "a better win rate scores higher when all else is equal", "a tiny sample
  is pulled toward the field", "the median card scores 50".
- `tests/test_tournament_features.py` pins cohort selection, counts, archetypes,
  concentration, the trend series and the draw rule.
- `tests/test_score_run.py`, `test_score_validation.py`, `test_overall_run.py` and
  `test_overall_validation.py` pin file identity, validation and pooling.
- The Java HTTP tests and the Python `test_rankings_http.py` exercise ranking,
  sorting, filtering and movement against a real PostgreSQL publication.
- A mutation-testing pilot on 2026-10-18 killed 89.7% of mutants in the analytics
  core; see [docs/qa/mutation-testing.md](../qa/mutation-testing.md).
