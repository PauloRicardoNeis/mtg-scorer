# MTG Scorer

Historical Magic: The Gathering analytics for finding cards worth building
around.

The immediate use case is **Forge Adventure / Quest**: given the sets and
rarities currently available to a player, surface cards with competitive pedigree
and explain *why* they are interesting. The broader goal is a historical discovery
engine that distinguishes ubiquitous good cards from cards belonging to
distinctive strategies.

## Project status

The repository is at the **first vertical-slice stage**.

- Source-independent facts, provenance, coverage, missing-aware features, and
  reproducible scoring contracts are implemented.
- Scryfall bulk data can be preserved as an immutable raw snapshot and normalized
  into Oracle-card and printing Parquet tables.
- Tournament ingestion and empirical feature computation are next.
- Score weights remain provisional and must not be treated as ground truth.

Read the [measurement contract](docs/measurement-contract.md) before changing
feature semantics or scoring. The [implementation plan](docs/implementation-plan.md)
records what was changed after the foundation release and what remains deliberately
deferred. The
[polyglot application boundary](docs/adr/0001-polyglot-application-boundary.md)
records how the future Python, Java, and React applications will cooperate without
duplicating analytical logic.

## Core idea

A single `power` number conflates distinct questions:

1. **Staple Score** — How broadly and repeatedly has a card proved competitively
   useful?
2. **Build-around Signal** — How specifically and coherently does a card belong to
   a distinctive strategy package?
3. **Evidence Score** — How much trustworthy data supports those estimates?

A high Build-around Signal makes a card an **Engine Candidate**. It does not prove
that the card causally generated the deck: decklists alone cannot reliably
distinguish an engine from a narrow payoff, redundant enabler, or indispensable
support card.

| Pattern | Staple | Build-around | Interpretation |
| --- | ---: | ---: | --- |
| Ubiquitous format staple | High | Low | Broadly useful card |
| Archetype pillar | High | High | Powerful and strategically defining |
| Rogue engine candidate | Low | High | Prime discovery target |
| Unsupported card | Low | Low | Little historical evidence of either role |

`Build-around - Staple` is exposed as **Distinctiveness Delta**, but it is a
descriptive coordinate rather than the canonical ranking. A mediocre `50/0` card
should not automatically outrank a genuine `95/70` archetype pillar.

## Epistemic architecture

The durable record is:

```text
RAW SNAPSHOT
What exactly did the source return?

  ↓

FACTS
Events, deck registrations, standings, matches, and cards

  ↓

FEATURES
Incidence, commitment, concentration, recurrence, and proof

  ↓

JUDGMENTS
Staple, Build-around, Evidence, and explanations
```

Scores are disposable views. Raw observations and feature inputs must remain
rebuildable when a parser, normalization, or formula changes.

### Unknown is not zero

Unavailable competitive proof is not failed competitive proof. Each semantic
feature therefore carries:

- a normalized value or `None`;
- supporting observation count;
- an eligible denominator when meaningful.

Scoring reweights known features and reports feature coverage. Sparse data may
produce a strong signal, but never counterfeit completeness.

### Coverage is multidimensional

Historical sources may contain complete standings, partial decklists, and no
round data. Coverage is recorded independently for:

- decklists;
- standings;
- matches.

Each dimension retains a semantic scope (`FULL_FIELD`, `TOP_CUT`, `WINNERS`,
`PARTIAL`, `NONE`, or `UNKNOWN`) plus measured counts when available. Winners-only
data can describe published winning decks; it cannot establish field-wide win
rates or metagame share.

### Provenance is mandatory

Every normalized fact retains:

- source and source record identifier;
- timezone-aware retrieval timestamp;
- raw snapshot reference;
- parser version.

Every score additionally records:

```text
dataset_snapshot_id
feature_pipeline_version
score_model_version
score_config_hash
```

## Historical normalization

Global lifetime incidence is invalid because it conflates age, legality, format
popularity, tournament volume, and source coverage. Features must first be
computed inside bounded strata such as:

```text
source + format + era + coverage class
```

Only eligible decks belong in a card's opportunity denominator. Current legality
must not be projected backward into historical events.

Human archetype labels are also inconsistent across decades and sources. Initial
analytics should work from decklists directly. Empirical deck clusters or
externally versioned labels can later augment those observations.

## Co-occurrence and package discovery

Pairwise lift is useful for exploration:

```text
Lift(A, B) = P(A and B) / (P(A) × P(B))
```

Raw lift is unstable for rare cards. A single unique deck makes every pair inside
it look perfectly associated. Production features must therefore retain support
and use a regularized statistic such as smoothed log-lift, normalized PMI, or
prior-adjusted log odds.

Package discovery should eventually group adjacent engine candidates into one
strategy fingerprint. Otherwise a rogue deck may become ten apparently separate
recommendations that all lead to the same list.

## Data architecture

The pipeline follows a bronze → silver → gold model:

```text
External source
      ↓
Bronze: immutable payloads and manifests
      ↓
Silver: canonical facts in Parquet
      ↓
Gold: versioned features, packages, and scores
```

The initial analytical store is **Parquet queried through DuckDB**. This workload
is dominated by scans, aggregations, and co-occurrence computation rather than
transactions. PostgreSQL remains appropriate later for serving stable,
precomputed gold tables through an API.

Planned product stack:

- Python for ingestion, feature research, model evaluation, and batch scoring;
- Parquet/DuckDB for exploratory and batch computation;
- PostgreSQL for stable, versioned serving tables and product data;
- Java 21 and Spring Boot for the product API, authentication, collections, and
  saved searches;
- TypeScript, React, and Next.js for the public Forge-oriented interface.

No application request should scrape or query a third-party site live. External
data belongs in the ingestion pipeline.

### Product boundary

Python owns the volatile empirical work; Spring Boot owns the durable product
boundary. The two runtimes exchange versioned data through PostgreSQL or immutable
Parquet artifacts. Java must not spawn Python during an HTTP request, and the same
score formula must not be maintained independently in both languages.

```text
Batch publication
Scryfall / tournament sources -> Python -> Parquet/DuckDB -> PostgreSQL

User request
Browser -> Next.js -> Spring Boot -> PostgreSQL
```

The first interface should expose the score surface rather than hide it behind a
single ranking. A user should be able to:

- search and filter by set, date, color, legality, rarity, and owned cards;
- sort independently by Staple, Build-around, Evidence, and Distinctiveness;
- inspect the observations and coverage behind every score;
- discover coherent card packages rather than lists of near-duplicate candidates;
- save Forge card pools, searches, and prospective deck packages.

The current repository is still the Python analytical application. The Java API
and React interface will be introduced only after one empirical vertical slice
produces a useful, reproducible score snapshot.

## Current domain model

- `Provenance`
- `CoverageDimension` and `CoverageProfile`
- `OracleCard` and `CardPrinting`
- `Tournament`
- `DeckEntry`
- `Standing`
- `Match` and `MatchParticipant`
- `FeatureObservation` and `CardFeatures`
- `ScoreContext`, `ScoreConfig`, and `ScoreBreakdown`

Deck registration, standing, and match are separate facts. A source aggregate may
be retained, but round-level evidence must not be irreversibly collapsed into it.

## Data sources

### Scryfall

Scryfall supplies canonical card and printing metadata. Scoring uses Oracle IDs;
printing rows preserve set, rarity, and release information required by Forge
filters.

The importer:

1. fetches the current default-cards bulk manifest;
2. downloads the payload once;
3. records its checksum, retrieval time, source timestamp, and parser version;
4. streams JSON arrays or JSONL, including gzip-compressed payloads;
5. emits `oracle_cards.parquet` and `card_printings.parquet`;
6. reuses a verified existing snapshot rather than overwriting it.

### TopDeck

TopDeck is the intended first tournament adapter because it can expose standings,
structured decklists, and optional round data. It requires an API key and visible
attribution. The adapter will begin with one bounded format-era slice rather than
pretending that current coverage solves historical breadth.

### Historical corpus

MTGTop8 or another deep corpus may later add historical reach. Ingestion must obey
the source's access rules and encode its coverage limitations explicitly.

## Repository layout

```text
src/mtg_scorer/
  domain.py             source-independent facts
  features.py           missing-aware analytical features
  scoring.py            versioned, replaceable score model
  cli.py                local command-line entry point
  ingest/scryfall.py    immutable Scryfall snapshot pipeline

docs/
  adr/
    0001-polyglot-application-boundary.md
  measurement-contract.md
  implementation-plan.md

tests/
  fixtures/
  test_domain.py
  test_scoring.py
  test_scryfall_ingest.py
```

Keep source adapters outside the factual domain and scoring core.

## Development

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
```

Ingest the current Scryfall catalog locally:

```bash
mtg-scorer ingest-scryfall --data-dir data/local
```

Raw and generated local data are ignored by Git. Commit fixtures and contracts,
not downloaded corpora.

## Contributor rules

1. Do not bake source-specific quirks into the core domain.
2. Do not discard provenance or coverage limitations.
3. Do not turn unavailable features into zeros.
4. Preserve raw numerators, denominators, and intermediate statistics before
   normalization.
5. Version data snapshots, feature pipelines, and score configurations.
6. Prefer explainable features whose inputs can be shown to a user.
7. Add tests for invariants and pairwise expectations, not only fixture numbers.
8. Do not claim that co-occurrence proves causal engine status.
9. Keep the Forge discovery use case in view.

## Near-term roadmap

1. Import one bounded TopDeck format-era slice with raw snapshots.
2. Normalize events, decks, standings, matches, and coverage profiles.
3. Compute incidence, commitment, competitive proof, and evidence features.
4. Emit an explainable CSV or terminal ranking before building an API.
5. Add historical card-pool and legality snapshots.
6. Add deck-family clustering and regularized package association.
7. Calibrate against sentinel cards and known deck families.
8. Materialize stable gold tables and publish them to PostgreSQL.
9. Add the Java 21/Spring Boot read API over those immutable score snapshots.
10. Add the Next.js interface with Forge filters, score explanations, and owned
    card pools.

The unresolved statistical questions are research work, not empty spaces to fill
with arbitrary constants.
