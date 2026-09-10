# Catalog v1: implementation contract

Status: implemented and verified locally for milestone 2 (2026-09-08). See
[verification evidence](project-status-report.md) and [operation commands](local-catalog.md).
ADR 0002 records the implemented ownership and publication design.

## Scope and executable artifacts

Guest chooses a pool, searches real cards, opens face-aware detail and eligible
printings, and sees exact dataset identity/source information. No tournament counts,
scores, historical legality, Forge compatibility claims or user accounts in v1.

- [Publication JSON Schema](../contracts/catalog-publication.schema.json): logical
  export fields, nullability, formats, supported version and closed row shapes.
- [Generated Spring OpenAPI 3.1](../contracts/catalog-api.openapi.json): implemented routes, parameters, payloads and errors. HTTP DTOs belong to Java;
  `scripts/api_contract.py` detects live-schema and generated-TypeScript drift.
  The old proposal is retained under `docs/evidence/milestone1/`.
- [Synthetic catalog](../contracts/fixtures/catalog-valid.json) and
  [response](../contracts/fixtures/card-page.json): clearly labeled conformance
  inputs; never evidence of data access or tournament performance.
- [Offline checks](../scripts/verify_contracts.py): schema/spec validity, identity
  references, faces, aliases, invalid versions, missingness and filter counterexample.

```powershell
python -m uv sync --project analytics --locked --extra dev
analytics/.venv/Scripts/python.exe scripts/verify_contracts.py
```

These checks do not establish SQL constraints, query behavior, raw-file integrity,
atomic publication or cross-language integration. They are reusable expected
inputs/outputs for those tests in milestone 2. The entire Python environment is resolved in `analytics/uv.lock`.

The verifier does check export byte hashes and declared row counts; verification
against retained upstream raw files and enforcement by PostgreSQL remain importer
and database integration responsibilities.

## Normalization and factual identity

Use Oracle IDs for cards and Scryfall IDs for printings. Each export envelope has
one catalog snapshot ID inherited by every nested row. For canonical attributes,
prefer English printings, then newest `released_on` (null last), then smallest UUID.
Keep `source_scryfall_id`; never mix canonical attributes from different printings.
Retain every supported source printing, language and game. A representative need
not be eligible for the user's selected pool; eligible printing information is
returned separately.

Retain top-level cost/text as supplied, including null versus empty string.
Retain `card_faces` in source order. Missing top-level colors may be the union of
face colors only if every face has known colors; otherwise null. Never default
missing mana value to zero. Color identity is source-provided and independent
from colors; missing is null and `[]` means known colorless. Preserve face-specific
images per printing and whole-card images with `face_index=null`; no image binaries
in publication JSON or this milestone's HTTP contract.

Known multi-face layouts must include their faces. Do not invent face rows for
meld pieces with no `card_faces`; keep the piece as its Oracle identity. Meld-part
navigation is deferred. Preserve unfamiliar layout strings with present face data
and render a generic detail; quarantine missing top-level Oracle IDs (including
face-ID-only reversible records) rather than collapsing identities. Excluded counts
and reasons belong to the manifest. No claim of complete catalog coverage while
unhandled records exist.

Name-key v1 is Unicode NFKC, ASCII A–Z to a–z, trim/collapse ASCII whitespace;
preserve accents, punctuation and other letters. Store canonical and face aliases.
Duplicate aliases across Oracle IDs are allowed. Search may return all matches;
future deck resolution needs an exact unique alias or explicit identifier and must
quarantine ambiguity. No fuzzy automatic deck resolution. Java must use the same
named normalization contract for query text; shared conformance examples cover it.
Layout/name/source normalization stays Python-owned.

## Publication artifact and PostgreSQL mapping

First exporter writes `catalog.json` conforming to the logical schema and a
`manifest.json`, finalized atomically in a new directory. Use Parquet as the
analytical store; JSON is a deliberately simple serving export for the bounded
first slice. Parse large arrays with streaming I/O on import. Benchmark before
changing the serving transport to JSONL/Parquet; preserve logical row contracts.
The fixture verifier loads small files in memory and is not the production importer.

[Manifest v1](../contracts/catalog-manifest.schema.json) has exactly these required fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | `catalog-manifest-v1` |
| `catalog_snapshot_id`, `publication_schema_version` | Match export envelope; schema is `catalog-publication-v1` |
| `export_file`, `export_sha256`, `export_bytes` | `catalog.json`, lowercase full SHA-256 of exact bytes, nonnegative integer size |
| `row_counts` | Exact nonnegative integers for cards/faces/printings/aliases; cards and printings positive |
| `source_manifest_sha256` | Full hash of retained immutable source manifest |
| `excluded_record_counts` | Map of reason code to nonnegative count; empty means none excluded |

Publication identity is `catalog-` plus full SHA-256 of canonical UTF-8 JSON
containing `source_manifest_sha256`, `parser_version`, `publication_schema_version`
and `selection` (sorted object keys, compact separators, no ASCII escaping).
The source manifest records the actual retrieval timestamps; `created_at` is fixed
when the export is first produced and reused on retries. Do not regenerate it for
an idempotent retry. The ID is independent of the import attempt and export hash;
changing content under an existing ID fails even if counts match. The synthetic
fixture uses a human-readable test ID and fake raw digests; production rejects
that exception. Validate export and source checksums before marking ready.

API-owned Flyway migrations create these PostgreSQL tables. Every `snapshot`
column below is `catalog_snapshot_id text` and part of each child primary key;
all child FKs include snapshot. Column names/types follow the publication schema
unless specified here: UUID identities, text strings, timestamptz timestamps,
date release dates, double precision finite nonnegative mana value, text[] colors/
identity/games, integer face indices. Nullability follows JSON Schema.

| Table | Columns / keys / constraints |
| --- | --- |
| `catalog_snapshot` | snapshot PK; source, parser_version, schema_version, created_at, selection jsonb; manifest jsonb; export_sha256; state (`staging`,`ready`,`published`); published_at nullable until published |
| `catalog_card` | snapshot + oracle_id PK; remaining `card` fields; FK (snapshot, source_scryfall_id) to printing, deferred until load completes |
| `catalog_face` | snapshot + oracle_id + face_index PK; remaining face fields; FK to card; contiguous indices checked before ready |
| `catalog_printing` | snapshot + scryfall_id PK; remaining printing fields except images; FK to card; unique (snapshot, scryfall_id, oracle_id) supports same-card representative validation |
| `catalog_printing_image` | snapshot + scryfall_id + image_slot PK; source_uri, artist; image_slot `-1` for whole card or nonnegative face index; validate face references before ready |
| `catalog_alias` | snapshot + oracle_id + alias_key + kind PK; FK to card; aliases intentionally not globally unique |
| `catalog_publication_attempt` | attempt_id UUID PK, snapshot FK, expected_previous_snapshot_id nullable FK, started_at, finished_at nullable, state (`running`,`succeeded`,`failed`), error_code nullable; no secrets/raw exception text |
| `active_catalog` | singleton boolean PK constrained true, snapshot FK; row absent before first promotion; promotion function requires published state |

Use the three-column printing FK for a card's representative (snapshot,
source_scryfall_id, oracle_id), not just existence of a printing. Deferred
constraints allow card/printing loading in one staging transaction. Keep source
record ID as printing ID; printing retrieval/raw references and global parser
version provide fact provenance. Faces/aliases inherit the card representative's
provenance. Source URI is attribution, not an instruction to fetch at request time.

Initial indexes: card `(snapshot, name_key COLLATE "C", oracle_id)`, printing
`(snapshot, oracle_id, scryfall_id)` and `(snapshot, set_code, rarity, oracle_id)`;
alias PK plus `(snapshot, alias_key, oracle_id)`. B-tree does not accelerate arbitrary
substring search: retain the simple parameterized substring query initially and
inspect EXPLAIN ANALYZE before adding `pg_trgm`/GIN. No index is claimed efficient
without representative evidence. Limit snapshot set vocabulary to 4096 codes and
report an import validation error if exceeded; this bounds filter metadata.

The implementation follows the lock, state transition, immutability, guarded promotion and recovery
protocol in [ADR 0002](adr/0002-catalog-publication-and-delivery-order.md). Staging
read privileges must not leak through detail-by-ID. Catalog readiness means a valid
published active snapshot and usable DB connection; missing tournament evidence
does not make a catalog API unready. Liveness stays process-only. Startup without
publication returns a 503 catalog problem, not a successful empty result.

## HTTP semantics beyond the schema

`GET /api/v1/cards` accepts literal name/face search, repeated set and rarity
filters, optional game and color identity, `name_asc`, limit 1–100 (default 24),
optional snapshot and cursor. Whitelist parameters; reject unknown parameters,
sorts and duplicate scalar parameters with 400. Repeated set/rarity values are
deduplicated then sorted for filter identity; enforce max 32 sets / 6 rarities.
Unknown well-formed set code returns an empty page, not an invalid-query error.

Within each set/rarity list use OR; between dimensions use AND on one printing:

```sql
-- Conceptual predicate: bind arrays; never interpolate user query text.
EXISTS (
  SELECT 1 FROM catalog_printing p
  WHERE p.catalog_snapshot_id = c.catalog_snapshot_id
    AND p.oracle_id = c.oracle_id
    AND (:sets_absent OR p.set_code = ANY(:sets))
    AND (:rarities_absent OR p.rarity = ANY(:rarities))
    AND (:game_absent OR :game = ANY(p.games))
)
```

Color-identity filter means known identity is a subset of selected W/U/B/R/G;
colorless is included in any selected color pool. `C` selects known colorless
only. Omitted means no restriction, including unknown. UI must label this
"Color identity". Pool eligibility is not historical tournament eligibility or
proof of Forge implementation. Query text `%` and `_` are literal characters,
not SQL LIKE wildcards. SQL must bind values and escape LIKE metacharacters or
use a literal substring function.

Return Oracle cards once and count only jointly eligible printings.
Detail returns canonical fields and all faces. Printings are separately paginated
with the same set/rarity/game predicates, ordered by Scryfall UUID ascending;
valid card with no eligible printings returns an empty page. Unknown card or
unknown/unpublished snapshot is 404. An explicit snapshot never falls back to active.
Snapshot list always contains active first, then up to 19 other published snapshots
ordered by published_at descending and ID ascending. An explicit older retained
snapshot remains addressable even if absent from that list. Snapshot detail supplies
sorted set codes/names for controls and source/selection metadata; it exposes no
filesystem paths, secrets, or raw personal data.

Cursor v1: base64url UTF-8 JSON containing version=1, resource (`cards` or
`printings:<oracle_id>`), catalog_snapshot_id, normalized-filter SHA-256,
sort, limit and last key. Cards key is `[name_key, oracle_id]`; printings key is
`[scryfall_id]`. Hash canonical JSON of normalized q, sorted sets/rarities, game
and canonical WUBRG color selection (absent values null; sort/limit checked
separately). Validate decoded size/types, supported version, route binding,
snapshot, sort/filter identity and key. A cursor is untrusted input, not an
authorization token; signing is unnecessary for this public read path. Never
embed SQL or use raw cursor values without binding. Reject mismatch with 400
`invalid_cursor`. Continue a valid cursor against its snapshot after promotion.
No total-count query in v1; fetch limit+1 to determine `next_cursor`. Capture one
snapshot ID at request start and bind every subsequent query to it.

All errors use Problem Details and stable `code`; never parse `detail` in the
browser. Invalid query/cursor=400; unknown snapshot/card=404; absent active catalog
or DB unavailability=503 `catalog_unavailable`; unexpected failure=500
`internal_error`. Sanitize unexpected details, preserve server-side cause and
request correlation ID. No scores/endpoints/sorts are advertised until implemented.
TypeScript is generated from Spring OpenAPI, and verification compares the live
server with the checked-in contract. The milestone-1 proposal is historical evidence.

## Evidence eligibility proposal (future, Python-owned)

Catalog metadata states `not_available` / `no_tournament_dataset`. A catalog lookup
cannot claim "not observed" or zero usage without an eligible observed corpus.
Keep all numeric research outputs out of these responses.

For milestone 3, version policy as `public-evidence-v1` only after corpus evaluation.
Proposed result variants: `available` with finite estimate; `insufficient_evidence`
with estimate null and nonempty reason codes; `not_applicable` with null and a
domain reason. Persist policy version alongside measurement's four computational
identities. Raw counts, denominators, strata, feature availability and independent
decklist/standing/match coverage accompany available observations.

An observed zero requires a positive eligible denominator and complete resolution
of the relevant zone. Unknown denominator/coverage/legality stays unavailable.
No eligible decks -> insufficient evidence. Top-cut usage labels its population
explicitly. Match evidence requires known match coverage and complete outcome
semantics; missing results do not become losses. Singleton commitment is
not_applicable until a revised model exists. Build-around recommendations require
evaluated strategy-specificity and package-coherence evidence, not volume or
commitment alone; reasons include `strategy_features_unavailable` and
`policy_not_evaluated`. No universal coverage percentage or sample threshold is
invented here. Evidence Score remains a heuristic, never a confidence percentage.

## Three-view wireframe and interaction

```text
DISCOVERY /cards?catalog_snapshot_id=...&set=...&rarity=...
[MTG Scorer]                             [Dataset & method]
Find cards for your pool    [Catalog sample badge / source date]
[Search card or face name____________________________]
[Sets v] [Rarity v] [Color identity v] [Game v] [Clear]
Card name / colors / eligible printing count    [Open]
Card name / colors / eligible printing count    [Open]
[Load more]                         [Copy this search URL]
Tournament evidence is not available for this dataset.

CARD /cards/{oracle_id}?catalog_snapshot_id=...
[Back to search]   Card name / layout
Front face name, cost, type, full text
Back/other face name, cost, type, full text
Eligible printings: set / rarity / collector number
[Load more printings]   [Source link]
Tournament evidence unavailable: no tournament dataset

DATASET /datasets/{catalog_snapshot_id}
Source + retrieved range + publication time + sample/bulk scope
Exact catalog ID / parser / schema / card and printing counts
Sets included / exclusions / attribution links
Method: pool availability differs from historical opportunity.
Research scores are not tournament evidence.
```

Desktop controls can share a row; narrow screens stack them above results. Use
native labeled inputs/selects, semantic headings, links and buttons, visible focus,
keyboard-operable filter panels, text color labels, and live result/loading status.
Filter changes reset the cursor, retain snapshot and update a shareable URL;
Back restores prior filters. Distinguish loading, no matching cards (clear filters),
network/API failure (retry), and no active catalog (dataset unavailable). A refresh
banner may offer a newer snapshot explicitly; never silently change the current
search during pagination. No results or scores invented for wireframe display.

## Workload assumptions and validation targets

First seed: the bounded reviewed layout sample or an equivalently documented small
derived real sample. Scale planning envelope, not observed data: up to 100,000
Oracle cards, 1,000,000 printings, one publisher and 20 concurrent readers,
at most one refresh/day, two full snapshots for initial storage estimation.
No hard freshness SLA: show retrieval/publication time and retain last good data
during source failure. A bounded seed must clearly identify itself as incomplete.

Before full-catalog release, record actual source size, all table counts, import
duration and peak RSS, disk usage, query plans, CPU/RAM/runtime versions and dataset
hash. Proposed API target: p95 below 300 ms at 20 concurrent readers, excluding
browser assets, over a documented warm/cold workload and named machine/tier.
Measure errors and request count too. This is a target to validate/revise, not a
milestone-1 result or a promise inferred from tiny fixtures.
