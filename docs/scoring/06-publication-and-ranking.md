# 6. Publication and ranking

Scores leave Python as one file per run, enter PostgreSQL through a guarded
staging-and-promotion protocol, are ranked by SQL in the Java API, and are shown
by the site as letter grades with movement, tones and prices. This document
follows a score from the run file to the page.

## The run file

`build_score_run()` in `analytics/src/mtg_scorer/publish/score_run.py` writes one
JSON document per cohort, `<score_run_id>.json`, with schema
`score-run-file-v2` (`contracts/score-run.schema.json`):

| Section | Contents |
| --- | --- |
| identity | `score_run_id`, `dataset_snapshot_id`, `parser_version`, `feature_pipeline_version`, `cohort_rules_hash`, `population_rule`, `method_identities` (one `[id, version, config hash]` per method), `source`, `attribution` |
| `raw_files` | every saved response with name, SHA-256, size, retrieval time and whether that time came from the manifest or the file's modification time |
| `cohort` | the rules with their hash; every included event with name, URL, date, players, decklists, top-cut size and basis; every excluded event with its reason; totals; the field's record, win rate and top-cut rate; the trend series; every archetype with its core, commanders, record, performance and series |
| `population` | the rule, how many cards were scored, the names of the excluded cards (basic lands) |
| `cards` | every mainboard card, scored or not, with its usage, record, performance, series, archetypes and the positions and copies of its decks |
| `decks` | every cohort deck, newest event first, with its archetype, final rank, top-cut result, record, commanders and sideboard (or `null` when the sideboard was not fully observed) |
| `runs` | per method: id, version, config hash, label, description, outputs, and per scored card its `values` and `inputs` |

The run id is `scores-` + SHA-256 of the canonical JSON of the identity fields.
It does not hash the results, so it names "what was computed from what", and
`results_sha256` (everything but `raw_files`, whose retrieval times may differ
between copies of the same responses) names the outcome. `write_score_run`:

- validates the document first (schema, then the relationship checks in
  `score_validation.py`: top-cut counts unknown exactly when nothing is known,
  archetype label and labelled count agree, record and copies never exceed the
  card's decks, win rate unknown exactly without games, every method scored every
  scored card exactly once with exactly its outputs, and from `card-usage-v7` the
  deck lists recount every card's counts);
- writes atomically through a temporary file and `os.replace`;
- returns the existing file untouched when a rerun produces the same results;
- raises when a file of the same id holds different results: "bump the version of
  whatever changed".

The overall run (`overall-run-file-v1`, `contracts/overall-run.schema.json`) has
the same shape with `components` in place of a cohort of events, a pooled card
record, and each card's `formats` map of per-format grades.

## Publication to PostgreSQL

`publish_score_run()` in `publish/score_postgres.py` loads a validated file under
one advisory lock (`724603`) through functions defined in
`api/src/main/resources/db/migration/V4__score_publication.sql` and later:

1. `begin_score_publication(header, attempt, expected_previous)` inserts the run
   row in state `staging` (or refuses a run of the same id with a different
   `results_sha256` or row counts: `score_run_content_conflict`), and marks any
   earlier running attempt as abandoned. A run already published returns
   `already_published` without touching anything.
2. The rows are loaded with `COPY` into `score_run_card`,
   `score_run_card_archetype`, `score_run_archetype`, `score_run_deck`,
   `score_run_method`, `card_score` and `card_score_input`. A trigger on each
   table refuses any change to a run that is not staging, so published rows are
   immutable. The tables are then `ANALYZE`d so the planner has statistics before
   the first read.
3. `promote_score_publication(attempt)` checks that the active run for the source
   and format is still the one the publisher saw (`stale_promotion` otherwise),
   that every row count matches the header, that the run has scored cards and
   methods, that scores belong only to scored cards and declared outputs, and that
   `count(card_score) = sum(cardinality(outputs)) × scored cards` so every method
   scored every scored card. It then sets `state = published` and points
   `active_score_run (source, format_name)` at the run.
4. On any failure `fail_score_publication` records a stable code; the staging
   rows remain for diagnosis and a retry clears them.

`rollback_score_run(target, expected)` points a source and format back at an
earlier published run, guarded by the same expected-pointer check. Published runs
are never deleted, which is what makes "movement since the previous run" and
pinned URLs possible.

The API reads only the `published_*` views (rows whose run is published) under a
read-only role.

## Ranking in the API

`RankingRepository` (`api/src/main/java/io/mtgscorer/api/rankings/`) computes no
score. For one run, one method and one output it builds:

```sql
SELECT k.*, s.value score,
       rank() OVER (ORDER BY s.value DESC NULLS LAST) ranking
FROM scores.published_score_run_card k
JOIN scores.published_card_score s
  ON s.score_run_id = k.score_run_id AND s.oracle_id = k.oracle_id
WHERE k.score_run_id = :run AND k.scored
  AND s.method_id = :method AND s.output = :output
```

Points to note:

- `rank()` gives tied scores the same rank and skips the following ranks (1, 2,
  2, 4), and cards whose score is `NULL` rank last. Ranks run over every scored
  card of the run.
- Ranks are computed **before** filters. A card keeps its rank when the reader
  filters by name, type or color; the page shows "47 of 3,112 ranked cards" with
  the rank the card has in the whole cohort.
- The same subquery over the **previous run** is left-joined by oracle id, and
  `rank_change = prev.ranking - r.ranking`: positive means the card rose. The
  previous run is the latest published run of the same source and format whose
  window ended earlier and that holds the same method; without one the change is
  `null`.
- Card details (mana cost, type line, colors, preview printing) come from the
  active catalog when the card is in it; a card outside the catalog is still
  ranked and matched by the run's name.

**Choosing the run and method.** Without parameters the API serves the format
`Overall` if an overall run is active, else `Modern`. A `format` selects that
format's active run; a `score_run_id` pins a specific published run so every page
of a listing stays on the same results across republication. Without a `method`
the API uses the first of `constructed-score`, `max-ratio` that the run has, else
the run's first method; the ranked output is the method's first declared output.

**Sorts.** `score` (the output), `decks`, `top_cuts`, `name`, `win_rate` (orders by
the stored `win_rate_delta`, the gap to the field, which is the only win-rate
figure an overall run has), `top_cut_lift`, `trend` (`share_delta`), `movement`
(`prev.ranking - r.ranking`), `price` and `value` (`score / usd`). Unknowns sort
last; ties fall back to name then oracle id. Every sort defaults to descending
except name.

**Views.** `all`, `risers` (`prev.ranking > r.ranking`) and `fallers`, with a
count of each under the same filters so the tabs can show them.

**Bounds.** `limit` 1-100 (default 25), `offset` up to 10,000, search text up to
100 characters normalised by `NameKey`, formats and methods pattern-checked.

## The compare page

`CompareRepository` ranks cards across the active runs of several formats by one
graded method (`constructed-score` or `signature-score`, the only two whose
0-100 percentiles are alike in every format). For each run it ranks the method's
scored cards with `rank() OVER (PARTITION BY format ORDER BY score DESC)`, then
groups by card:

- `ranked_in`: how many compared formats rank the card;
- `best_format`, `best_score`: the format where the card scores highest;
- per format: rank, score, win-rate delta, share (`deck_count / the run's decks`),
  top-cut lift and share delta.

A format in which the method scored no card (a Signature score without archetype
labels) is left out of the comparison and reported as unavailable. `every=true`
keeps only cards ranked in every compared format. Sorts are `best`, `count`,
`name` or `{format}:{metric}`.

## The commander page

`CommanderRepository` ranks the archetypes that commanders name, by the decks
they lead, with `rank()` over `deck_count`, a `previous_run` of the same kind, the
commanders' combined color identity, and the archetype's own win-rate delta,
interval, top-cut lift, trend and core-card count. It uses no score method; the
commander's "performance" is `archetype_performance` from the run file.

## Letter grades, tones and labels on the site

`web/src/lib/format.ts` and `web/src/components/ranking-data.tsx` turn stored
numbers into what the reader sees.

**Which methods carry grades.** `GRADED_METHODS = constructed-score,
signature-score, hidden-gem-score, overall-grade`: the methods whose output is a
0-100 percentile. Relative volume is shown as a number, not a letter.

**Letter bands** (`grade(score)`): the first band whose floor the score reaches.

| Score | Grade | Label | Share of a cohort (ideal) |
| ---: | --- | --- | ---: |
| ≥ 90 | A+ | Top tier | 10% |
| ≥ 85 | A | Top tier | 5% |
| ≥ 80 | A− | Top tier | 5% |
| ≥ 75 | B+ | Strong | 5% |
| ≥ 70 | B | Strong | 5% |
| ≥ 65 | B− | Strong | 5% |
| ≥ 60 | C+ | Playable | 5% |
| ≥ 50 | C | Playable | 10% |
| ≥ 45 | C− | Playable | 5% |
| ≥ 35 | D | Fringe | 10% |
| < 35 | F | Underperforming | 35% |

Because a graded score is a percentile, the share column is exact up to ties and
rounding: an A grade of any kind is the top fifth of the scored cards of that
cohort, a C is the band around the median, an F is the bottom 35%. The grade is a
position in the field, not a verdict on the card in isolation. For the Hidden gem
score the percentile is among cards with a positive gem product, so the bands
describe that subset and every card at or below the field reads F.

The grade ring fills `score × 3.6` degrees and glows only for A grades; a `null`
score shows a dash labelled "No grade".

**Tones** (`deltaTone`, `liftTone`, `trendTone`):

| Statistic | Positive | Negative |
| --- | --- | --- |
| win-rate delta | ≥ +0.05 points | ≤ −0.05 points |
| top-cut lift | ≥ 1.10× | < 0.97× |
| trend | > +0.15 points of share | < −0.15 points |

These thresholds are display choices, not significance tests; the interval is
shown beside the win rate so the reader can judge.

**Other derived figures.**

- `Top X%` beside a rank: `ceil(100 × rank / scored_cards)`, at least 1.
- Meta share bar: the card's decks over the run's most-played card's decks, so
  the bar is relative to the leader; the printed value is `decks / cohort decks`.
  In the overall run the deck count is shown instead of a share, because a share
  of every deck would mostly measure the largest format.
- Copies per deck: `mainboard_copies / deck_count`, rounded to 2 decimals in SQL.
- Score per dollar: `score / price_usd`, `null` without either.
- Movement: `▲ n` places gained, `▼ n` lost, `—` unchanged or unknown.
- The window: ISO start and exclusive end shown as inclusive days in the reader's
  locale.

## Prices

`publish/prices.py` publishes, from a retained Scryfall bulk file, each oracle
card's cheapest USD price among its paper printings that a sanctioned deck can
play (not digital, oversized, memorabilia or gold-bordered), in any finish
(`usd`, `usd_foil`, `usd_etched`), rule `cheapest-playable-paper-usd-v1`. Scryfall's
prices are daily TCGplayer market estimates meant for trends and general value,
so the site shows them with their date and never as a price to buy at. The price
snapshot id hashes the source bytes and the rule, and one snapshot is active at a
time.

## Reading a published run back

Everything the site shows can be traced:

```text
rank on the page
  -> scores.published_card_score (score_run_id, method_id, oracle_id, output, value)
  -> scores.published_card_score_input (the method's intermediate values)
  -> scores.published_score_run_card (usage, record, performance, deck positions)
  -> scores.published_score_run_deck (the decks, newest first, each with its result)
  -> scores.published_score_run.summary (cohort rules, events, exclusions, baselines, raw files)
  -> the run file on disk, named by the same score_run_id
  -> the saved responses named in raw_files, each with its SHA-256
```

On the site, the rankings page header shows the run's source, window, publication
date, event, player, deck and match totals and the source attribution; the card
page's "Inspect source and methodology" link leads to the catalog dataset page,
which documents the card data's provenance rather than the score run's.
