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

## Implemented in the first product conformance slice

- Added a Python-owned `card-catalog-v1` publication contract and atomic JSON
  writer.
- Added a deterministic demonstration catalog produced by the real score model
  from explicitly synthetic features.
- Added a Java 21/Spring Boot 4.1 API that loads the published contract behind a
  repository interface.
- Added card-name, set, and rarity filtering plus independent Staple,
  Build-around, Evidence, and Distinctiveness ordering.
- Added Oracle-ID lookup and integration tests over the actual HTTP boundary.
- Added a TypeScript/React/Next.js discovery page with filters, score explanations,
  demonstration labeling, and snapshot lineage.
- Added independent Python, Java, and web CI jobs.

This slice proves language and HTTP contracts. It does not constitute an empirical
score release, a PostgreSQL implementation, or a deployment.

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
7. Materialize stable, versioned gold tables for publication.
8. Introduce PostgreSQL when concurrent serving and indexed product queries
   justify an operational database.
9. Replace the demonstration catalog repository with PostgreSQL while preserving
   the Java API contract; then add user collections and saved searches.
10. Replace demonstration data in the Next.js interface only after the tournament
    slice produces useful explanations.

## Product application sequence

The product layer deliberately follows the analytical proof rather than preceding
it. See
[ADR 0001](adr/0001-polyglot-application-boundary.md) for the language boundary.

### 1. Publish one useful snapshot — empirical work pending

Python computes a bounded, reproducible score snapshot and its explanations.
DuckDB and Parquet remain the analytical substrate. Before an API exists, the
snapshot must already be useful as a CSV or terminal report.

### 2. Define the publication contract — JSON boundary implemented

`card-catalog-v1` now defines cards, printings, scores, explanations, and complete
snapshot identity. The demonstration file proves the boundary. Versioned
PostgreSQL gold tables remain pending for cards, score snapshots, feature
observations, explanations, and package memberships. Publishing a new snapshot
remains an explicit batch operation; an HTTP request never starts Python.

### 3. Add the Java API — read slice implemented

Introduce a Java 21/Spring Boot application around stable product queries:

- card search and Forge-oriented filters;
- independent Staple, Build-around, Evidence, and Distinctiveness ordering;
- score explanations and snapshot identity;
- owned-card collections, saved searches, and prospective deck packages;
- authentication, validation, and transactional product state.

The API now consumes the JSON publication through a repository interface and does
not reimplement experimental feature engineering or scoring. PostgreSQL,
authentication, and transactional user state remain later increments.

### 4. Add the React interface — discovery slice implemented

Introduce a TypeScript/React application using Next.js for routing, public page
metadata, and server rendering where useful. Its first vertical slice is card
discovery plus a score explanation—not a broad dashboard shell.

The browser calls the versioned Spring Boot API and never connects directly to
PostgreSQL, Parquet files, or external MTG sources. The current interface labels
its synthetic input prominently; empirical filters follow tournament ingestion.

## Deliberately unresolved

- The legal license for outside reuse. Choosing MIT, Apache-2.0, GPL, or another
  license is an owner decision, not a mechanical repository cleanup.
- The first historical corpus with sufficient depth beyond TopDeck.
- The exact clustering algorithm and association statistic.
- The product ranking above the two-dimensional score surface.
- Whether causal engine classification should incorporate card text, curated
  labels, deck variants, or all three.
- The deployment provider and authentication mechanism for the future product
  applications.
