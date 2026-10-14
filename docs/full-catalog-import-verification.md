# Full catalog import verification — 2026-09-28

## Real source and outcome

The full retained Scryfall **default-cards** snapshot dated
`2026-09-27T21:05:46.301+00:00` was imported into the existing local
`mtg_catalog_demo` database. The HTTP enqueue returned **202 in 72 ms**. A separate
Python worker completed normalization, validation and atomic publication in
**158.86 seconds**. This excludes the initial bulk download (performed separately)
and Java startup. The source was a 78,602,859-byte gzip JSONL file.

| Measured output | Count |
| --- | ---: |
| Source records | 118,406 |
| Oracle cards | 38,690 |
| Printings | 118,324 |
| Faces | 6,433 |
| Aliases | 42,875 |
| Image references | 122,155 |
| Sets | 1,052 |
| Excluded: missing top-level Oracle ID | 82 |

The source is default-cards, not all languages or every Scryfall object. It includes
115,679 English printings and 2,645 printings in other languages. Excluded objects
remain in the retained raw source. Images are URLs, not downloaded image binaries.
Legacy game availability (`astral`: 12; `sega`: 10) is preserved alongside paper,
MTGO and Arena. The first attempt rejected these previously unsupported game
values during validation, recorded a failed job, and left the old catalog active.
After adding an additive database/schema constraint update, retry reused the raw
download and succeeded.

Published identity:

```text
catalog-4a95abfdbd39514d07ed6c874b5afc1e600dfd869976bc58a479ef74f9f56285
parser: scryfall-catalog-v1-bulk-v1
schema: catalog-publication-v1
raw SHA-256: a5d81cd5b2212e2ac234c762820866d80595c581fb97afa9093789d7d201a0fb
export SHA-256: 6dcd1aba78dbc3057851cef6de3312ead445ad5e75400a211aac53b45bb1cadb
```

A second real endpoint request completed in **0.535 seconds** with
`result=already_published`, retaining the same identity. The raw file was verified
and reused. Search found Lightning Bolt, Insectile Aberration by face name, and
Black Lotus. Three 100-row pages returned 300 distinct Oracle IDs on the published
snapshot. Existing snapshot-pinned URLs still address the retained sample.

## Resource and query measurements

Machine: Windows 11, Ryzen 7 7800X3D (16 logical CPUs), 33,397,133,312 bytes physical
RAM; Python 3.12.10, PostgreSQL 17.11, Java 21.0.12.1, Node 24.14.1. Python process
peak RSS through import: **198,897,664 bytes (189.7 MiB)**. This includes the local
measurement coordinator/worker and excludes PostgreSQL, Java and the browser.
CPU utilization and aggregate process memory were not sampled.

- Serving JSON: 111,480,040 bytes.
- Completed artifact directory including Parquet/manifests: 123,992,417 bytes.
- Total retained source/artifacts: 202,595,927 bytes.
- Database at measurement: 265,901,747 bytes, including previously retained sample
  data and catalog/import metadata. Transient staging and WAL peaks were not sampled.

A warm loopback check used 8 warmups followed by 100 requests with 20 concurrent
readers. Queries rotated between unfiltered discovery, Lightning Bolt, Insectile
Aberration, and the joint M11/common/paper filter. There were **0 errors**;
median **132.64 ms**, p95 **180.74 ms**, maximum **222.82 ms**. The existing API
process uses the same catalog read SQL. Browser/CDN assets are excluded. This is
one small warm workload, not a cold-cache, sustained-load or remote service claim.
An EXPLAIN ANALYZE with buffer counts for the joint printing filter is retained in
the [machine-readable evidence](evidence/full-catalog/2026-09-28.json), along with
job timestamps, complete hashes, language/game counts and measurements.

## Deterministic checks

`python scripts/demo.py verify --skip-install` runs the locked installed toolchain:

- Python: 38 offline tests passed; database/HTTP tests are intentionally skipped
  in that phase and run explicitly against a new PostgreSQL database afterward.
- The import integration test uses retained fixture bytes and real HTTP/roles:
  unauthorized requests, unknown jobs, eight concurrent enqueue requests sharing
  one ID, worker exclusion, successful import, unchanged-source no-op, sanitized
  failure, disconnected-session recovery and successful retry.
- Five real PostgreSQL publication tests cover old-reader visibility, atomic
  promotion, competing publishers, rollback, integrity conflict, failed loads,
  abandoned attempts, role restrictions and invalid references.
- Empty-catalog HTTP behavior and five catalog HTTP tests cover search, filters,
  images, errors, and pagination across refreshes.
- Java: 16 tests; Maven/Spotless checks and package build.
- Seven Chromium journeys; Next.js production build, TypeScript, Prettier, Python
  Ruff, publication/OpenAPI validation and dependency-boundary checks.
- Live Spring OpenAPI and generated TypeScript agree.

CI uses these fixtures and never needs Scryfall access. These checks are separate
from the real-source measurements above. Existing comments in `scripts/demo.py`,
the diagnostic change in `scripts/probe_catalog.py`, and untracked `analytics/data/`
were preserved. No commits, pushes or deployment were performed.

## Operational limits

The worker must be run separately; queued jobs remain queued until it is running.
Recovery detects loss of the database session, rather than guessing an import
timeout. A hung process retaining its session requires operator termination.
Raw snapshots and published artifacts are retained without automatic deletion.
Temporary directories left by forced process termination can be removed after
workers stop. Public hosting, remote credentials, restore drills and scheduled
refreshes are outside this change. See the [runbook](local-catalog.md) for startup,
credential setup, import, status, refresh, retained-source rebuild and rollback.
