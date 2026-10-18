# MTG Scorer Analytics

Python 3.12 application for MTG data ingestion, source-independent facts,
missing-aware feature research, batch scoring, and publication artifacts.

The Python package owns analytical semantics. It does not serve HTTP requests;
the sibling Java application under `../api/` owns the product API.

From the repository root, install the locked analytical environment:

```powershell
python -m pip install uv==0.8.22
python -m uv sync --project analytics --locked --extra dev
python -m uv run --project analytics python -m pytest analytics/tests -q
python -m uv run --project analytics python -m pytest analytics/tests -q --cov --cov-config=analytics/pyproject.toml
python -m uv run --project analytics ruff check analytics scripts
```

The `--cov` run fails below `fail_under` in `pyproject.toml`; from the repository
root it needs `--cov-config`, because coverage only searches the working directory.
Plain `pytest` measures nothing, so single-file database runs are never gated.

`python scripts/demo.py verify` additionally runs real PostgreSQL publication,
Java HTTP and browser checks. Their required environment variables are supplied
by that runner; the offline Python phase reports them as skipped intentionally.

The catalog producer is in `normalize/` and `publish/`. It preserves top-level
missing values and ordered faces, chooses one deterministic representative, retains
printing images/provenance and ambiguous aliases, writes immutable JSON/Parquet,
and publishes through guarded PostgreSQL functions. The full serving exporter in
`publish/bulk.py` uses SQLite staging and streams the same logical contract;
validation uses disk indexes and PostgreSQL loading uses transactional COPY.
See [measured full import evidence](../docs/full-catalog-import-verification.md).

The real eight-response seed and its source hashes are under
`seeds/scryfall-layouts-v1`. See [the local runbook](../docs/local-catalog.md) for
`export-catalog`, `publish-catalog` and `rollback-catalog` commands. These batch
commands are separate from HTTP handling.

The legacy analytical bulk command remains available for an explicit online refresh:

```powershell
python -m uv run --project analytics mtg-scorer ingest-scryfall --data-dir analytics/data/local
```

It preserves raw bytes and legacy analytical Parquet. To populate the serving
catalog, operate `python -m mtg_scorer.import_worker` with `CATALOG_PUBLISH_DSN`
and enqueue through the protected administrative API. The worker connects raw
bulk data to face-aware normalization, immutable serving exports and atomic
publication. `--once` handles one queued job; `--source-dir` selects retained
source data for an offline rebuild. The [runbook](../docs/local-catalog.md)
documents credentials, refresh, retries and rollback. Live probes are not CI.

See the repository [README](../README.md),
[measurement contract](../docs/measurement-contract.md), and
[application boundary](../docs/adr/0001-polyglot-application-boundary.md) before
changing feature or scoring semantics.
