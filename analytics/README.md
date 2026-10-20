# MTG Scorer Analytics

Python 3.12 application for MTG data ingestion, source-independent facts,
missing-aware feature research, batch scoring, and publication artifacts.

The Python package owns analytical semantics. It does not serve HTTP requests;
the sibling Java application under `../api/` owns the product API.

From the repository root, install the locked analytical environment:

```powershell
python -m pip install uv==0.8.22
python -m uv sync --project analytics --locked --extra dev
python -m uv run --project analytics python -m pytest analytics/tests -q
python -m uv run --project analytics python -m pytest analytics/tests -q --cov --cov-config=analytics/pyproject.toml
python -m uv run --project analytics ruff check analytics scripts
```

The `--cov` run fails below `fail_under` in `pyproject.toml`; from the repository
root it needs `--cov-config`, because coverage only searches the working directory.
Plain `pytest` measures nothing, so single-file database runs are never gated.

`python scripts/demo.py verify` additionally runs real PostgreSQL publication,
Java HTTP and browser checks. Their required environment variables are supplied
by that runner; the offline Python phase reports them as skipped intentionally.

The catalog producer is in `normalize/` and `publish/`. It preserves top-level
missing values and ordered faces, chooses one deterministic representative, retains
printing images/provenance and ambiguous aliases, writes immutable JSON/Parquet,
and publishes through guarded PostgreSQL functions. The full serving exporter in
`publish/bulk.py` uses SQLite staging and streams the same logical contract;
validation uses disk indexes and PostgreSQL loading uses transactional COPY.
See [measured full import evidence](../docs/full-catalog-import-verification.md).

The real eight-response seed and its source hashes are under
`seeds/scryfall-layouts-v1`. See [the local runbook](../docs/local-catalog.md) for
`export-catalog`, `publish-catalog` and `rollback-catalog` commands. These batch
commands are separate from HTTP handling.

The legacy analytical bulk command remains available for an explicit online refresh:

```powershell
python -m uv run --project analytics mtg-scorer ingest-scryfall --data-dir analytics/data/local
```

It preserves raw bytes and legacy analytical Parquet. To populate the serving
catalog, operate `python -m mtg_scorer.import_worker` with `CATALOG_PUBLISH_DSN`
and enqueue through the protected administrative API. The worker connects raw
bulk data to face-aware normalization, immutable serving exports and atomic
publication. `--once` handles one queued job; `--source-dir` selects retained
source data for an offline rebuild. The [runbook](../docs/local-catalog.md)
documents credentials, refresh, retries and rollback. Live probes are not CI.

## Score methods

Scores come from replaceable methods in `src/mtg_scorer/scoring/`, so formulas can
change or coexist over time. A method receives every eligible card of one stratum
as `ScoringInput`s and returns a `ScoreRun`. Each run carries the method's id,
version and configuration hash plus the dataset and feature identities. Each
`CardScore` holds named outputs (`None` when unscorable, never a stand-in zero) and
the inputs that explain them.

| Method | Outputs | Notes |
| --- | --- | --- |
| `foundation` | Staple, Build-around, Evidence, coverage | The original weighted model; `ScoreConfig` sets its weights |
| `max-ratio` | `max_ratio` | Count ÷ the largest count in the stratum × 100; measures volume, not quality |

To add a method:

1. Create a module with a frozen configuration dataclass (a `version` label plus
   settings, hashed with `config_fingerprint`) and a method class providing
   `method_id`, `label`, `description`, `outputs`, `version`, `config_hash` and
   `score()`. Finish `score()` with `build_run`, which checks the declared outputs.
2. Add an instance to `SCORE_METHODS` in `scoring/registry.py`.
3. Add tests for its own behaviour. The shared contract tests in
   `tests/test_score_methods.py` already cover every registered method.

A new formula setting is a new configuration, not an edit. Changing it changes the
configuration hash, so existing results remain attributable to what produced them.

## Scoring saved TopDeck responses

`score-topdeck` turns a directory saved by `scripts/probe_tournaments.py` into one
score-run file. It makes no network calls:

```powershell
python -m uv run --project analytics mtg-scorer score-topdeck --source-dir analytics/data/local/<probe-dir> --cohort analytics/cohorts/topdeck-modern-2026-03-to-08.json --output-root analytics/data/local/score-runs
```

1. `ingest/topdeck.py` checks each saved response against its manifest SHA-256. It
   then parses the responses into source-independent facts: events with separate
   decklist, standings and match coverage; standings for every player; and decks for
   structured lists only.
   - Card lines without an oracle id are quarantined, and a mainboard that contains
     one counts as incomplete.
   - A missing sideboard stays unobserved, not empty.
2. The cohort file (`analytics/cohorts/`) sets the format and the window, the
   minimum decklist coverage and the events excluded on purpose, each with a reason.
   `tournament_features.py` applies these rules, leaves out decks whose mainboard is
   incomplete, and counts each mainboard card's decks, events and top cuts, plus its
   most common source archetype label. Top cuts count only decks whose result is
   known, and that denominator is kept with them.
3. Every registered method scores the population: all mainboard cards except basic
   lands. The file `<score_run_id>.json` keeps the cohort, every card's usage and
   each method's scores. The run id hashes the dataset, parser, features, cohort
   rules, population rule and method identities. A rerun with identical results
   reuses the file; different results under the same id are refused.

Top-cut membership comes from bracket wins and losses when a response includes
them. The saved Modern responses do not, so each event's top cut falls back to
the standings order. That order is undocumented, so it is used only when no player
below the cut has more wins than one inside it; otherwise the top cut stays
unknown. Each event records which basis it used.

Raw responses and run files stay under the ignored `analytics/data/local/`. The
TopDeck credit travels in each run file's `attribution`.

Every run file must satisfy
[`contracts/score-run.schema.json`](../contracts/score-run.schema.json) plus the
relationship checks in `publish/score_validation.py` before it is written or
published. `publish-scores` (`publish/score_postgres.py`) loads one file into the
`scores` schema and makes it the active run for its source and format. Like catalog
publication, rows can change only while the run is staging, and promotion verifies
row counts and that every method scored every scored card. See the
[runbook](../docs/local-catalog.md#full-catalog-import-worker-and-administration)
for roles and commands.

## Scoring saved Wizards Pro Tour coverage

`score-wizards` does the same for Pro Tours saved by
`scripts/probe_wizards_coverage.py` (constructed Pro Tours of about 2004–2010, read
from the Internet Archive). Each probe directory holds one event; repeat
`--source-dir` to score a format season. Card names are resolved against the active
catalog in `CATALOG_READ_DSN`, which is only read:

```powershell
$env:CATALOG_READ_DSN = 'postgresql://catalog_publisher_local:local-catalog-only@127.0.0.1:55432/mtg_catalog_demo'
analytics/.venv/Scripts/python.exe -m mtg_scorer.cli score-wizards --source-dir analytics/data/local/<ptcol05-dir> --source-dir analytics/data/local/<ptla05-dir> --cohort analytics/cohorts/wizards-extended-2004-10-to-2005-10.json --output-root analytics/data/local/score-runs
```

`ingest/wizards.py` verifies each page against the manifest, which also names the
event's format, first day and constructed rounds (for the mixed-format 2009–10 Pro
Tours, rounds 1–5 and 12–16; the probe checks them against the coverage's standings by
format). It reads the 2005 table and the 2009–10 `div.deck` decklist layouts, takes
the field from the alphabetical pages plus the pages that list the best records and
the top 8 apart, and corrects known typos in the coverage (`CARD_ALIASES`); names
that differ only in punctuation or accents resolve without an entry. Decklists name
players "First Last" and the standings "Last, First [CTRY]", so decks join their
standing in passes: same name, truncated name, surname and initial, then similar
spellings ("Odan" and "Oodan", "Billy" and "William", surname first). Results pages
that spell a player differently from the standings are merged onto the standings
name unless both spellings played the same round. Records count only the
constructed rounds and stay unknown when any of them was not archived. The final
standings give each deck its rank and the top 8. The dataset id hashes the pages,
the event, the alias table, the ignored card layouts and the catalog snapshot. Run
files carry the source `wizards-coverage` and credit Wizards and the archive in
`attribution`.

See the repository [README](../README.md),
[measurement contract](../docs/measurement-contract.md), and
[application boundary](../docs/adr/0001-polyglot-application-boundary.md) before
changing feature or scoring semantics.
