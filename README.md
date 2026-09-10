# MTG Scorer

Historical Magic: The Gathering analytics for finding cards worth building
around.

The immediate use case is **Forge Adventure / Quest**: given the sets and
rarities currently available to a player, surface cards with competitive pedigree
and explain *why* they are interesting. The broader goal is a historical discovery
engine that distinguishes ubiquitous good cards from cards belonging to
distinctive strategies.

## Project status

Read the [consolidated progress report](docs/project-status-report.md) for what is
implemented, what milestone 1 produced, verification limits, remaining work and
the next milestones. The [implementation plan](docs/implementation-plan.md) contains
the detailed execution checklist.

The local catalog application is implemented: a documented real Scryfall seed
travels through face-aware Python normalization and immutable export, atomic
PostgreSQL publication, Spring queries, and three guest Next.js pages.

- Search canonical and face names; filter jointly by printing set, rarity and game.
- Inspect complete faces, eligible printings, source dates and dataset identity.
- Share snapshot-pinned URLs that remain stable across publication refreshes.
- Missing tournament evidence is explicit. No research scores are served.

**To try the program, follow [Run the app on Windows](#run-the-app-on-windows)
below.** The preview runs on your computer and is not deployed publicly.

Read the [measurement contract](docs/measurement-contract.md) before changing
feature semantics or scoring. The [implementation plan](docs/implementation-plan.md)
records what was changed after the foundation release and what remains deliberately
deferred. The
[polyglot application boundary](docs/adr/0001-polyglot-application-boundary.md)
records how the Python, Java, and Next.js applications cooperate without
duplicating analytical logic.

## Run the app on Windows

You use MTG Scorer in a browser. One Python command prepares the data and starts
the database, Java API, and Next.js website for you.

The included demo contains **7 cards and 8 printings**, selected from real
Scryfall responses to demonstrate different card layouts. You can search cards,
filter printings, inspect card faces, and check the dataset's origin. It is a
small catalog demo: tournament evidence, competitive rankings, and automatic
Forge collection import are not available yet. You do not need Forge installed,
an MTG account, or a Scryfall/TopDeck API key to run it.

### 1. Check the required tools

Open **PowerShell**. Use these versions to reproduce the repository's local setup:

| Tool | Version | Check in PowerShell |
| --- | --- | --- |
| Python | 3.12.10 | `python --version` |
| Node.js | 24.14.1 | `node --version` |
| npm | 11.11.0 | `npm.cmd --version` |
| Java Development Kit (JDK) | 21 | Set and check `JAVA_HOME` in step 2 |

If a tool is missing, install it from the official
[Python 3.12.10 release page](https://www.python.org/downloads/release/python-31210/),
[Node.js downloads](https://nodejs.org/en/download), or
[Temurin JDK Windows installation guide](https://adoptium.net/installation/windows/).
Select the versions above; download pages may default to a different version.
Enable Python's PATH option during installation, and reopen PowerShell afterward
so it can find newly installed tools. Node includes npm; if its version differs,
run `npm.cmd install --global npm@11.11.0` and check again.

Maven is included through the repository's wrapper. On Windows, the runner can
download and prepare portable PostgreSQL automatically. You do not need to
install Maven, PostgreSQL, or Docker separately for the default setup.

### 2. Open the project folder and select Java 21

Run these commands in the same PowerShell window. Replace the paths if your
project or JDK is installed elsewhere; the paths shown are an example local setup:

```powershell
Set-Location 'C:\Users\paulo\Documents\work\mtg-scorer'
$env:JAVA_HOME = 'C:\Users\paulo\.jdks\temurin-21.0.12.1'
& "$env:JAVA_HOME\bin\java.exe" -version
& "$env:JAVA_HOME\bin\javac.exe" -version
```

Both Java commands must report version **21**. `JAVA_HOME` must point to the JDK
folder itself, not its `bin` folder or `java.exe`. The runner uses this setting;
having Java 21 installed is not enough if `JAVA_HOME` still points to Java 17.
This assignment lasts for the current PowerShell session, so repeat it in each
new terminal you use to start the app.

All remaining commands below run from this project folder, the one containing
`README.md`, `scripts/`, `analytics/`, `api/`, and `web/`.

### 3. Start the app

```powershell
python scripts/demo.py up
```

Leave this terminal open. The first run needs internet and may take several
minutes while it:

1. Installs the locked Python and web dependencies, plus Chromium for browser tests.
2. Runs code checks/tests and builds the Java API and website.
3. Prepares PostgreSQL and the local `mtg_catalog_demo` database.
4. Loads the included Scryfall sample and starts the API and website.

You do not need to activate a Python virtual environment, start each application
separately, or download the full Scryfall catalog. The runner handles the Python
environment and uses source data already in the repository.

Wait until the terminal prints:

```text
Catalog ready: http://127.0.0.1:3300/cards | API: http://127.0.0.1:18080/swagger-ui.html
```

The command stays running while you use the app. If it exits with an error before
`Catalog ready`, use the troubleshooting table below.

### 4. Open the catalog and try a search

Open **[the card catalog](http://127.0.0.1:3300/cards)** in your browser.

1. Enter `Lightning Bolt` in the name field and click **Find cards**.
2. Open the result to see its metadata and printings.
3. Return to search and try `Insectile Aberration` to find a card by its back-face name.
4. Use **Inspect this dataset** to see the source information and coverage limits.

The small sample will not contain most Magic cards. Start with no set, rarity, or
color filters; an empty result may simply mean that no sample card matches.
For example, this seed includes Lightning Bolt as **M11 common** and **2X2 uncommon**.
Set, rarity, and game filters must match the same printing.

Developers can also open **[Swagger UI](http://127.0.0.1:18080/swagger-ui.html)**
to inspect and try API requests. The catalog link above is the user interface.

### 5. Stop and start again

Press **Ctrl+C** in the runner's terminal to stop the website and API. PostgreSQL,
the sample data, and logs remain on disk for reuse.

After a successful first run, you can start the existing build more quickly:

```powershell
python scripts/demo.py up --skip-install --skip-build
```

Set `JAVA_HOME` again first if you opened a new terminal. After changing code or
dependencies, use the full `python scripts/demo.py up` command to install and
rebuild. The fast command serves the previous build.

To stop the background PostgreSQL process as well, follow
[the database shutdown instructions](docs/local-catalog.md#postgresql-choices-and-credentials).

### If something goes wrong

| Symptom | What to do |
| --- | --- |
| `python` or `node` is not recognized | Install the tool from step 1, reopen PowerShell, and check its version. If Python opens the Microsoft Store, try `py -3.12 --version`; if that succeeds, use `py -3.12` instead of `python` in the commands. |
| `npm.ps1` cannot run because scripts are disabled | Use `npm.cmd` for manual commands, as shown above. The runner already uses `npm.cmd` on Windows. |
| `Set JAVA_HOME to a JDK 21 installation` or a Java version error | Repeat step 2 in the same terminal, using your actual JDK 21 folder. Check both `java.exe` and `javac.exe`. |
| Port `18080` or `3300` is already in use | Stop your earlier preview with Ctrl+C in its terminal, then retry. If you intended to use that running preview, open its catalog URL instead. |
| A dependency download fails | Check internet access and retry the full `up` command. A first-time setup cannot use `--skip-install`. |
| A code check, test, or build fails | Read the first failing check in the terminal. Startup stops at that failure; fix it before retrying the full command. |
| `Local server exited` or startup times out | Read `.local/mtg_catalog_demo/api.log` and `.local/mtg_catalog_demo/web.log`. Database startup logs are `.local/postgres-start.log` and `.local/postgres.log`. |
| Browser cannot connect | Wait for `Catalog ready`, keep the runner's terminal open, and use port `3300` for the website. |
| A search returns no cards | Clear filters and search for `Lightning Bolt`. Only seven cards are included; this is not the full Magic catalog. |

For database configuration, Linux/macOS setup, publication, retry, and rollback,
see the [advanced local runbook](docs/local-catalog.md).

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
transactions. PostgreSQL now serves immutable catalog snapshots through the Java API;
analytical score publication remains future work.

Product stack:

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

The three applications have independent build roots. Python owns source and
analytical transformations, Java owns catalog queries and HTTP validation, and
Next.js consumes the generated Java contract. Tournament/evidence serving remains
outside the delivered catalog milestone.

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
analytics/              independent Python 3.12 analytical application
  pyproject.toml        Python package, dependencies, and tool configuration
  src/mtg_scorer/       ingestion, facts, features, scoring, and CLI
  tests/                Python tests and source fixtures

api/                    independent Java 21 / Spring Boot application
  pom.xml               Maven build and dependencies
  mvnw, mvnw.cmd        Maven Wrapper (POSIX / Windows)
  src/main/             catalog/snapshot queries, Flyway, health and OpenAPI
  src/test/             real HTTP integration tests

web/                    Next.js guest discovery/detail/dataset and browser tests
contracts/              publication schemas, generated Spring OpenAPI and fixtures
scripts/                local demo, verification, contract and boundary checks

pom.xml                 repository Maven aggregator for Java module discovery

docs/
  adr/
    0001-polyglot-application-boundary.md
  measurement-contract.md
  implementation-plan.md
```

Keep source adapters outside the factual domain and scoring core.

## Development

Complete [the setup above](#run-the-app-on-windows) first. Keep the same toolchain
and `JAVA_HOME` setting when running developer commands from the repository root.

To check the complete application, run:

```powershell
python scripts/demo.py verify
```

This runs Python/Java checks, real PostgreSQL publication and API checks, and
Chromium browser tests. It uses a separate `mtg_verify_<id>` database and ports
**18081/3301**. Wait for `Verification passed`; this command exits after checking
the app, whereas `up` keeps the preview running. The test database and evidence
are retained for diagnosis. Verification is optional for simply browsing the demo.

See [local setup and recovery](docs/local-catalog.md),
[analytics development](analytics/README.md), and [API development](api/README.md).
Downloaded corpora, local databases, build outputs and runtime logs are ignored.
Retained source fixtures carry exact hashes and attribution; live probes stay outside CI.

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

The [active implementation plan](docs/implementation-plan.md) and
[progress report](docs/project-status-report.md) record milestone 2's delivery.
[ADR 0002](docs/adr/0002-catalog-publication-and-delivery-order.md) preserves the
Python/Java/Next.js boundary. The next milestone is traceable tournament evidence;
it requires permitted source access and evaluated coverage, not invented scores.
No tournament work, authentication or deployment was added here.

The unresolved statistical questions remain research work.
