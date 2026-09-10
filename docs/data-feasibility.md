# Milestone 1: data feasibility

Observed 2026-09-07 local / 2026-09-08 UTC. Verdict: proceed with a bounded real
catalog; empirical tournament feasibility is unresolved. This milestone produces
an implementable catalog contract, not a verified tournament corpus or release.

## Checkout and baseline

Inspected tracked diff, untracked files, Python and Java source/tests, all four
requested plans, CI and build files. Existing changes include deleted root Python
files, untracked `analytics/`, `api/`, `.gitattributes`, root `pom.xml` and portfolio
plan, plus modified README/CI/ADR/roadmap. These were preserved; no staging,
commit, remote Git operation, deployment or purchase was performed. No applicable
AGENTS.md was found in the checkout or its ancestor directories.

| Check | Observed result / limits |
| --- | --- |
| Default `python` | Python 3.12.10; pytest/Ruff/DuckDB/ijson unavailable in that interpreter |
| Project environment | Installed editable `analytics[dev]` and contract tooling in ignored `analytics/.venv`; 20 existing tests pass; Ruff check and format pass |
| Java | PATH defaults to JDK 17; explicit local Temurin 21.0.12.1 with root Maven Wrapper `--offline verify` succeeds; 10 HTTP tests pass |
| Runtime dependencies | Docker and psql not found on PATH; no PostgreSQL integration run. Node exists; no web application/build exists yet |
| Evidence limits | No full bulk download, browser product flow, load test, empirical model evaluation or deployed system verified |

Baseline commands (PowerShell, repository root):

```powershell
analytics/.venv/Scripts/python.exe -m pytest -q analytics/tests
analytics/.venv/Scripts/python.exe -m ruff check analytics
analytics/.venv/Scripts/python.exe -m ruff format --check analytics
$env:JAVA_HOME = 'C:\Users\paulo\.jdks\temurin-21.0.12.1'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
.\api\mvnw.cmd -f pom.xml --offline --batch-mode --no-transfer-progress verify
```

## Real catalog sample

Purposeful layout coverage, not random sampling: eight successful named-card
requests with a one-second delay and 2 MB response bound. Retrieved
00:46:04–00:46:14 UTC on September 8. The saved payloads total 49,570 bytes,
contain eight printing IDs, seven Oracle IDs and seven layouts. All eight have
image references; image bytes were not downloaded or tested.

| Requested card | Layout | Finding |
| --- | --- | --- |
| Lightning Bolt, M11 / 2X2 | normal | Same Oracle ID; common / uncommon respectively |
| Delver of Secrets | transform | Two faces; top-level cost, text and colors absent |
| Fire // Ice | split | Two faces; top-level text absent |
| Bonecrusher Giant | adventure | Two faces; top-level text absent |
| Valakut Awakening | modal_dfc | Two faces; top-level cost, text and colors absent |
| Erayo, Soratami Ascendant | flip | Two faces; top-level text absent |
| Bruna, the Fading Light | meld | No `card_faces`; related pieces need separate handling |

The current `normalize_snapshot` actually produced 7 Oracle rows / 8 printing
rows / 0 skipped rows from these bytes. Five canonical rows have null text;
Delver and Valakut have empty colors despite colored faces. Layout, faces, image
references and aliases are not emitted by the current projection. Fix normalization
before serving detail. This is source-to-Parquet evidence, not just a synthetic
test. No deck-name resolution rate can be inferred from successful catalog ID
lookups. Missing Oracle IDs, reversible cards and conflicting printings still
need adversarial fixtures and a bulk audit.

An earlier attempt requested Lightning Bolt in `2xm` and received HTTP 404. It
was corrected to `2x2`; the successful sample is a separate directory. A manual
Delver connectivity check also preceded the saved sample. Neither is counted in
the eight successful sample records.

Reproduce with `python scripts/probe_catalog.py --output <new-local-directory>`.
The script refuses an existing output directory and stops on an HTTP error; it
is an opt-in probe, not a production retrying downloader. Do not rerun it in CI.
The original raw files and normalization output remain ignored under
`analytics/data/local/feasibility-20260908T0050Z/`. The directory is a run label;
the manifest's actual retrieval timestamps are authoritative. Portable evidence
(request URLs, IDs, timestamps, hashes and measured projection summary) is in
[evidence/catalog-sample.json](evidence/catalog-sample.json). Payload hashes cannot
be independently rechecked without those retained raw files; a fresh lookup may
return changed content.

The live [bulk descriptor](evidence/scryfall-bulk-metadata.json) returned HTTP 200
at 00:59:41 UTC. It reports `compressed_size=78058821` and a `.jsonl.gz` URI for
the 2026-09-07 21:05:28 UTC update; legacy `download_uri`, `size`, content type and
encoding fields are absent. The existing downloader's JSONL preference is
compatible with this descriptor. This is advertised metadata size, not measured
download/import volume; no bulk bytes were downloaded.

## Tournament feasibility and scope decision

No TopDeck-named environment variable or project-root, analytics or API dotenv
file was found. Values were never printed; other secret stores were not searched.
Authenticated tournament endpoints were not called, so there is no claimed 401,
event count, success rate or corpus coverage result.

The current [TopDeck API documentation](https://topdeck.gg/docs/tournaments-v2)
requires an Authorization key and visible attribution. Bulk queries accept format
and bounded dates; decklists may be text or URLs and structured decks are
conditional. Match responses distinguish pods, byes and 1v1 game scores. General
and heavy endpoints have different rate limits. These documented capabilities
do not establish accessible data quality or permission to redistribute a corpus.

| Required observation | Current result |
| --- | --- |
| Event dates, format, number of events | Unknown; no tournament sample |
| Usable / observed / expected decks | Unknown; never encoded as 0/0 coverage |
| Resolved card lines / total lines and copy-weighted resolution | Unknown |
| Mainboard / sideboard / commander zone completeness | Unknown |
| Standings and match observed/expected counts and scopes | Independently unknown |
| Permitted redistribution of normalized decks/examples | Unresolved |
| Selected analytical cohort | None; catalog sample has no tournament cohort |

First candidate probe after credentials become available: completed non-team
Modern events in `[2026-08-01T00:00:00Z, 2026-09-01T00:00:00Z)`, at most three
events and 100 decks, no external deck-host crawling. This is a probe candidate,
not a commitment that Modern data exists or that the month is legality-homogeneous.
Partition at any verified legality change and attach a versioned explicit card
pool before computing opportunity denominators. Prefer the earliest eligible
events by start time then source ID, not the events with the best-looking results.
Record incomplete response sampling as such; do not call the capped sample full-field.
If the candidate is unsuitable, report why before choosing another cohort.

On access, save raw responses privately, measure each coverage dimension, resolve
IDs/unique aliases and quarantine ambiguity, count missing zones and distinguish
URL-only decks from parseable lists. Compute both line- and copy-weighted resolution
with denominators retained. Mainboard usage requires complete resolved mainboards;
unknown sideboards must not become empty sideboards. Restrict incidence to eligible
observed decks in an explicit opportunity pool; top-cut-only observations are
usage among published successes. Measured partial coverage does not establish an
unbiased field estimate. Do not use `Standing.recorded_matches` as a complete
denominator while any win/loss/draw component is missing.

If access remains unavailable, milestone 2 proceeds with the catalog. Milestone 3
requires either a verified source or a curated real corpus with recorded reuse
permission and honest coverage labels. No synthetic tournament proof, automatic
switch to multiplayer, source scraping project, or permission request to a third
party is authorized by this plan.

## Demo data policy and dependencies

[Scryfall API guidance](https://scryfall.com/docs/api) supports added-value MTG
software/research while restricting pure republication/proxying, paywalls and
misleading endorsement; full-card images must retain artist/copyright treatment.
The [rate-limit page](https://scryfall.com/docs/api/rate-limits) currently limits
named lookups to two per second and directs bulk lookup workloads to bulk files.
These primary pages were fetched successfully through Python HTTP after the web
reader returned internal errors. Copies remain in ignored local storage.

For milestone 2, use a small derived real catalog seed in the application with
source links, provenance and attribution, useful joint-printing pool filtering,
and face-aware detail. Do not ship the full raw database as a download/proxy.
Keep raw payloads local. Test fixtures must say synthetic when invented; contract
fixtures contain no tournament evidence. Prefer text-first local rendering until
image hosting is defined. Serving cached images through owned assets would preserve
ADR 0001's no-browser-to-source rule; direct Scryfall image requests would require
an explicit ADR exception. No images are needed to execute the next milestone.

| Dependency | Blocks | Resolution condition |
| --- | --- | --- |
| TopDeck key or permitted real alternative | Tournament probe and milestone 3 | Provide through local/deployment secret configuration, not chat or source control |
| Corpus reuse terms | Public deck/examples release | Record source-specific permission and remove unnecessary personal fields |
| Real PostgreSQL runtime | Milestone 2 DB integration | Provision disposable local PostgreSQL or an approved test service; do not substitute H2/SQLite transaction evidence |
| Full-size catalog/layout profiling | Full-catalog scale claim | Measure raw bytes, row/layout counts, time, peak memory and quarantine counts on a bulk snapshot |
| Code license; hosting provider/budget | Public release/deployment | Owner decisions later; neither blocks local catalog implementation |

See [catalog-contract.md](catalog-contract.md), [ADR 0002](adr/0002-catalog-publication-and-delivery-order.md)
and [implementation-plan.md](implementation-plan.md). Milestone 1's desired chosen
tournament cohort/resolution report remains an explicitly unresolved external
dependency, rather than a fabricated completed acceptance gate.

## Milestone 1 contract verification

Six offline contract tests pass, including invalid-input subcases, publication
references/faces, exact export checksum/count checks and OpenAPI validation.
Ruff lint/format checks pass for the two new scripts using the analytics config.
`git diff --check` passes; existing CRLF conversion warnings remain informational.
CI now includes the same offline contract checks. CI configuration was inspected,
not executed on GitHub. No production application source or measurement formulas
were modified. PostgreSQL transaction, Java contract-conformance and browser tests
remain milestone-2 acceptance work.
