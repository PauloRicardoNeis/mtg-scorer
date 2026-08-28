# Measurement contract

This document defines what MTG Scorer may infer from historical deck data. It is
the contract between ingestion, feature computation, scoring, and the eventual
product. Formula weights may change; these epistemic boundaries should not change
silently.

## Terminology

- **Staple Score** estimates broad, repeated competitive usefulness.
- **Build-around Signal** estimates how specifically and coherently a card belongs
  to a distinctive strategy package. In the UI, a high-scoring card may be called
  an **Engine Candidate**.
- **Evidence Score** summarizes sample volume, source coverage, and feature
  availability. It does not convert a noisy estimate into certainty.
- **Distinctiveness Delta** is `Build-around Signal - Staple Score`. It is a
  descriptive coordinate, not the default ranking objective.

Decklists alone do not identify causation. A narrow payoff, enabler, redundant
copy, and indispensable engine can have nearly identical incidence patterns.
Therefore the system says that a card is *strategy-specific*, not that it caused
the strategy to exist.

## Missingness

Unknown is not zero.

Every normalized semantic feature is represented as:

```text
value: normalized estimate in [0, 1], or unknown
support: observations contributing to it
opportunity_count: eligible denominator, when meaningful
```

Scoring reweights only known features and reports the percentage of configured
feature weight that was observable. A result with 100% Build-around Signal and
25% feature coverage is not equivalent to one with 100% coverage.

## Coverage

Coverage is measured separately for:

1. decklists;
2. standings;
3. matches.

Each dimension records a semantic scope (`FULL_FIELD`, `TOP_CUT`, `WINNERS`,
`PARTIAL`, `NONE`, or `UNKNOWN`) and observed/expected counts when available.

Feature eligibility follows these rules:

- Field incidence requires full-field or measured partial decklist coverage.
- Top-cut and winners-only corpora may measure incidence *among published
  successes*, never field-wide metagame share.
- Competitive proof uses match results only when match coverage is known. Final
  standing is a separate, weaker observation.
- Missing decklists, standings, and rounds must never be filled with synthetic
  losses, zero copies, or zero win rate.

## Provenance and reproducibility

Every normalized fact retains:

- source and source record identifier;
- timezone-aware retrieval timestamp;
- parser version;
- immutable raw snapshot reference.

Every score retains the following computational identity:

```text
dataset_snapshot_id
feature_pipeline_version
score_model_version
score_config_hash
```

The full configuration hash prevents a familiar version label from concealing
changed weights.

## Feature contracts

The first feature pipeline should compute only the measurable baseline below.
Later features remain specified but unavailable until their prerequisites exist.

| Feature | Contract | Initial status |
| --- | --- | --- |
| `incidence` | Decks containing the card divided by eligible observed decks, calculated within format-era-source strata | First tournament slice |
| `commitment` | Robustly normalized mainboard copy count among decks containing the card; sideboard observations remain separate | First tournament slice |
| `competitive_proof` | Coverage-aware match and standing evidence relative to the same stratum | First tournament slice |
| `format_era_breadth` | Breadth across independently observed format-era strata, not raw lifetime | After multiple strata |
| `deck_family_breadth` | Breadth across empirical deck clusters or externally versioned labels | After clustering |
| `specificity` | Concentration within a small number of deck families, with sample-size shrinkage | After clustering |
| `package_coherence` | Regularized association with a stable constellation of partners | After co-occurrence |
| `recurrence` | Independent reappearance across events or separated eras | After multiple strata |
| `choice_freedom` | Survival in card pools offering materially more alternatives | Research stage |
| `coverage_strength` | Quality of the observations legally used for the other features | First tournament slice |

Raw numerators, denominators, stratum identifiers, and intermediate statistics
must be persisted before normalization.

## Historical denominators

Global lifetime incidence is invalid. It confounds card age, legality, format
popularity, source coverage, and tournament volume.

Features are first computed within a stratum such as:

```text
source + format + bounded era + coverage class
```

Only decks in which the card was a genuine option belong in its opportunity
denominator. Historical legality is its own versioned dataset; current legality
must not be projected backward. Until that dataset exists, use homogeneous eras
whose card pool can be specified explicitly.

## Co-occurrence

Raw lift is an exploratory primitive, not a production feature. Rare pairs can
produce enormous lift from a single shared deck, and every card in a unique deck
becomes perfectly associated with every other card in it.

Production association must therefore retain pair support and use a regularized
measure such as smoothed log-lift, normalized PMI, or prior-adjusted log odds. It
must be calculated within format-era strata before aggregation.

Package discovery should ultimately return a strategy fingerprint. The product
can then show one representative Engine Candidate with its associated package
instead of presenting ten adjacent cards from the same rogue deck as ten separate
discoveries.

## Ranking and calibration

Distinctiveness Delta is not the master ordering. The default discovery view
should use the Staple/Build-around plane, filters, or a Pareto frontier. Otherwise
a mediocre `50/0` card can outrank a genuine `95/70` archetype pillar.

Calibration uses sentinel cards and pairwise expectations rather than sacred
target numbers. Useful assertions include:

- a ubiquitous removal spell is more staple-like than a narrow engine;
- a known engine is more build-around-specific than its generic support cards;
- one unsupported deck does not create high Evidence;
- additional eligible observations increase Evidence without mechanically
  changing the substantive estimate;
- unavailable competitive data does not become zero competitive proof.

Sentinels detect regressions and conceptual failures; they do not constitute a
training set large enough to establish truth.
