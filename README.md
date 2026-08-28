# MTG Scorer

Historical Magic: The Gathering analytics for finding cards that are worth building around.

The immediate use case is **Forge Adventure / Quest**: given the sets and rarities currently available to a player, surface cards with evidence of competitive potential and explain *why* they are interesting. The broader goal is a historical card-discovery engine that distinguishes ubiquitous good cards from cards that enable distinctive strategies.

## Project status

This repository is at the **foundation stage**. The data model and scoring boundaries are being established before large-scale ingestion begins.

The scoring formulas are **not settled**. Treat every score as a versioned interpretation of historical evidence, not as ground truth. Contributors should preserve raw observations and derived features so formulas can change without re-ingesting the world.

## Core idea

A single `power` number conflates two different questions:

1. **Staple Score** — How broadly and repeatedly has a card proved competitively useful?
2. **Engine Score** — How much evidence suggests that a card enables, anchors, or is unusually specific to a strategy?

From those we can derive useful views such as:

- **Uniqueness** = Engine Score − Staple Score
- **Evidence** = how much trustworthy data supports the estimate
- later: **Generativity** = whether a card appears to spawn multiple packages rather than merely depend on one

A card can therefore be:

| Pattern | Staple | Engine | Interpretation |
| --- | ---: | ---: | --- |
| Ubiquitous format staple | High | Low | Generally powerful; useful in many decks |
| Archetype pillar | High | High | Powerful and strategically defining |
| Rogue / hidden engine | Low | High | Prime build-around candidate |
| Bulk / unsupported | Low | Low | Little historical evidence of either role |

The **low-Staple / high-Engine quadrant** is especially important for Forge: it is where unusual cards with real deckbuilding pedigree should emerge.

## Design principles

### 1. Store evidence, not conclusions

The durable record is:

> event → deck entry → cards → result

Scores are disposable views over that evidence. The repository should maintain a hard boundary between:

```text
FACTS
Which decks contained this card? At what event? When? In what quantity?

  ↓

FEATURES
How frequent? How concentrated? With what other cards? How successful?

  ↓

JUDGMENTS
Staple = 72, Engine = 91, Evidence = 48
```

### 2. Historical context is first-class

We do **not** want only the current metagame. Usage should remain attributable to format and time period so we can detect phenomena such as:

- Standard cards that disappear after rotation
- cards that survive into larger eternal card pools
- obscure cards that appear only in one successful strategy
- cards rediscovered years after printing
- strategies that recur independently across eras

### 3. Coverage quality matters

Historical Magic sources are heterogeneous. These are not equivalent datasets:

- every decklist and result from a 128-player event
- only the Top 8 from a 128-player event
- only undefeated / 5-0 lists
- decklists with no match results

Every imported event or observation must therefore retain a coverage classification. We must never infer field-wide win rates from a source that only publishes winners.

Initial coverage vocabulary:

```text
FULL_FIELD
FULL_FIELD_PARTIAL_MATCHES
TOP_CUT_ONLY
WINNING_DECKS_ONLY
UNKNOWN
```

### 4. Provenance is non-negotiable

Normalized data should retain enough source metadata to audit and rebuild it:

- source name
- source event/deck identifier when available
- retrieval timestamp
- raw source payload or snapshot reference
- parser version

If a parser assumption later proves wrong, we should be able to regenerate normalized data without guessing what the source originally said.

### 5. Archetypes should not become a prerequisite

Human archetype labels are useful but inconsistent across decades and sources. Initial analytics should work directly from decklists using card incidence, co-occurrence, concentration, and pairwise association.

Later, empirical deck clusters or external archetype labels can augment those signals.

## Planned data sources

The architecture is source-agnostic, but the intended initial sources are:

- **Scryfall** — canonical card identity and metadata; use Oracle identity rather than individual printings for scoring
- **TopDeck.gg** — structured tournament data where complete standings / decklists / match information are available
- **MTGTop8 or another deep historical corpus** — historical breadth; ingestion must respect the source's access rules and must record its more limited coverage semantics

No application request should depend on scraping a third-party site live. External data belongs in an ingestion pipeline; the product reads our normalized database.

## Data architecture

We use a simple bronze → silver → gold model:

```text
External sources
      │
      ▼
┌───────────────┐
│ Bronze        │ raw source snapshots / payloads
└───────┬───────┘
        ▼
┌───────────────┐
│ Silver        │ canonical cards, events, deck entries, results
└───────┬───────┘
        ▼
┌───────────────┐
│ Gold          │ analytical features and versioned scores
└───────────────┘
```

The intended production stack is deliberately mundane:

- **Python** for ingestion, feature computation, and scoring
- **PostgreSQL** for normalized observations and precomputed analytics
- **FastAPI** for the eventual read API
- **Next.js** for the eventual web UI

We should not introduce distributed infrastructure until the dataset demonstrates a need for it.

## Initial domain model

The first implementation models the analytical atoms rather than a database ORM:

- `Tournament`
- `DeckEntry`
- `DeckCard`
- `CoverageQuality`
- `CardFeatures`
- versioned score configuration / score result types

A future persistence layer can map these to PostgreSQL without coupling ingestion and scoring code to SQLAlchemy from day one.

## Scoring philosophy

### Staple Score

Should strongly reward **incidence and breadth**:

- repeated competitive appearances
- usage across multiple deck families
- usage across formats / eras
- competitive performance
- typical main-deck commitment

Incidence should use diminishing returns (for example logarithmic scaling) so the most ubiquitous cards do not numerically obliterate every merely common card.

### Engine Score

Should reward **strategic specificity** while letting repetition saturate quickly:

- archetype / deck-cluster concentration
- strong co-occurrence or lift with a distinctive package
- repeated 3–4-of main-deck commitment
- competitive proof
- survival / rediscovery in card pools with greater choice

One successful, highly coherent rogue deck should be allowed to produce a high Engine Score. Sparse evidence should lower **confidence**, not automatically erase the signal.

### Evidence Score

Evidence is deliberately separate from the estimate itself.

For example:

```text
Engine:   91
Evidence: 28
```

means "the observed pattern looks very engine-like, but we have little data." This is preferable to silently forcing every sparse card toward mediocrity.

### Uniqueness

Once Staple and Engine are normalized to comparable scales:

```text
Uniqueness = Engine − Staple
```

This should elevate unusual build-arounds without rewarding cards that are merely obscure. A card with no competitive evidence should have neither a meaningful Engine score nor meaningful positive uniqueness.

## Why co-occurrence matters

For cards `A` and `B`, a useful primitive is lift:

```text
Lift(A, B) = P(A and B) / (P(A) × P(B))
```

High lift means the pair occurs together far more often than chance would predict. A card whose competitive appearances repeatedly form a peculiar constellation of high-lift partners is strong evidence of a strategy-specific role.

This also permits later directional analysis:

```text
P(B | A) vs P(A | B)
```

which may help distinguish a generative engine from a card that simply depends on another engine.

## Repository layout

```text
src/mtg_scorer/
  domain.py      Source-independent observations and feature types
  scoring.py     Versioned, replaceable scoring logic

tests/
  test_scoring.py

README.md        Product, statistical, and contribution context
```

The layout will expand when ingestion and persistence are implemented. Keep new source adapters outside the domain/scoring core.

## Development

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## Contributor rules

When adding or changing functionality:

1. **Do not bake source-specific fields into the core domain unless they express a general concept.** Translate source quirks in adapters.
2. **Do not discard provenance or coverage limitations.** Unknown is preferable to fabricated precision.
3. **Do not make score formulas irreversible.** Derived values must be reproducible from stored observations/features.
4. **Version material scoring changes.** A score should be interpretable in terms of the model that produced it.
5. **Prefer explainable features.** Users should eventually be able to click a score and see why the card received it.
6. **Add tests for scoring invariants, not only exact fixture numbers.** Example: additional cross-archetype incidence should increase Staple evidence; mere obscurity should not manufacture Engine evidence.
7. **Keep the product use case in view.** We are ranking cards to help humans discover promising decks, not trying to produce an abstract universal ranking of Magic cards.

## Near-term roadmap

1. Establish domain types and versioned scoring interfaces. **(this foundation PR)**
2. Import Scryfall bulk card metadata and canonicalize names / Oracle IDs.
3. Add the first tournament-source adapter with explicit coverage semantics.
4. Persist normalized events, decks, and deck-card observations in PostgreSQL.
5. Compute incidence, breadth, commitment, result-quality, and evidence features.
6. Add card-pair co-occurrence / lift features.
7. Calibrate Staple and Engine formulas against hand-picked historical examples.
8. Expose read-only rankings and card explanations through an API.
9. Add Forge filters for available sets, rarity, format/card-pool constraints, and owned cards.

## What is explicitly *not* solved yet

Several important questions are intentionally open:

- the exact weights and nonlinear transforms for Staple / Engine
- how event prestige and field size should affect competitive proof
- the best normalization across formats and eras
- how to measure post-rotation survival without privileging formats with better data coverage
- how to infer independent archetypes / deck clusters robustly
- whether `Generativity` deserves its own score or should remain an explanatory feature

Those are research questions for this project, not omissions to hide behind arbitrary constants.
