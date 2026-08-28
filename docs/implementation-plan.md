# Implementation plan

This plan records the critique incorporated after the foundation release and
keeps deferred work explicit.

## Implemented in foundation v2

- Replaced scalar event coverage with independent decklist, standings, and match
  coverage dimensions.
- Added mandatory provenance with immutable snapshot references and parser
  versions.
- Separated registered decks, standings, and round-level matches.
- Added Oracle-card and printing identities so scoring can remain Oracle-level
  while Forge filters retain set and rarity information.
- Moved analytical features out of the factual domain layer.
- Made every semantic feature missing-aware and support-bearing.
- Renamed the internal engine estimate to **Build-around Signal** to avoid a
  causal claim unsupported by decklists alone.
- Added complete score identity: dataset snapshot, feature pipeline version,
  model version, and configuration hash.
- Recast Engine-minus-Staple as a descriptive Distinctiveness Delta rather than
  the default ranking objective.
- Added an immutable Scryfall default-cards downloader and a streaming
  canonicalizer that emits Oracle-card and printing Parquet tables.
- Added Ruff lint and formatting checks to CI.

## Next pull request: first tournament vertical slice

Use one bounded format and era from TopDeck rather than attempting historical
breadth immediately.

Deliverables:

1. API client with explicit rate-limit handling and no committed credentials.
2. Immutable bronze payloads and manifests.
3. Normalized tournaments, decks, standings, and matches.
4. Measured coverage profiles for every event.
5. Idempotent fixture-backed adapter tests.
6. Attribution metadata for the eventual user interface.
7. Baseline incidence, commitment, competitive-proof, and coverage features.
8. A CSV or terminal report showing scores, evidence, feature coverage, and raw
   reasons.

## Subsequent research increments

1. Add explicit card-pool and historical-legality snapshots.
2. Compute independent format-era strata and cross-era recurrence.
3. Introduce empirical deck-family clustering.
4. Add regularized pairwise association and package fingerprints.
5. Build a sentinel-card regression harness.
6. Calibrate model transformations and weights against observed failures.
7. Materialize stable gold tables for a read API.
8. Introduce PostgreSQL when concurrent serving and indexed product queries
   justify an operational database.
9. Add the Forge UI only after the vertical slice produces useful explanations.

## Deliberately unresolved

- The legal license for outside reuse. Choosing MIT, Apache-2.0, GPL, or another
  license is an owner decision, not a mechanical repository cleanup.
- The first historical corpus with sufficient depth beyond TopDeck.
- The exact clustering algorithm and association statistic.
- The product ranking above the two-dimensional score surface.
- Whether causal engine classification should incorporate card text, curated
  labels, deck variants, or all three.
