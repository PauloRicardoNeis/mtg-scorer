"""Named-machine measurements for the bounded seed, never a full-catalog claim."""

import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import statistics
import time
from pathlib import Path
from urllib.request import urlopen

import psycopg
from mtg_scorer.publish.artifact import export_catalog, verify_artifact
from mtg_scorer.publish.postgres import publish_catalog, rollback_catalog

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "analytics/seeds/scryfall-layouts-v1"


def peak_rss_bytes() -> int:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class ProcessMemory(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("faults", wintypes.DWORD),
                *[
                    (name, ctypes.c_size_t)
                    for name in (
                        "peak",
                        "working",
                        "quota_peak_paged",
                        "quota_paged",
                        "quota_peak_nonpaged",
                        "quota_nonpaged",
                        "pagefile",
                        "peak_pagefile",
                    )
                ],
            ]

        memory = ProcessMemory()
        memory.cb = ctypes.sizeof(memory)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemory),
            wintypes.DWORD,
        ]
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(memory), memory.cb
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return memory.peak
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if platform.system() == "Darwin" else value * 1024


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload, manifest = verify_artifact(args.artifact, SEED)
    dsn = os.environ["CATALOG_TEST_PUBLISH_DSN"]
    with psycopg.connect(dsn) as connection:
        previous = connection.execute(
            "SELECT catalog_snapshot_id FROM catalog.active_catalog"
        ).fetchone()[0]
    start = time.perf_counter()
    measured = export_catalog(
        SEED,
        args.output.parent / "measured-export",
        created_at="2026-09-08T00:46:15Z",
        selection={
            "kind": "bounded_sample",
            "description": "Real layout seed for bounded import measurement",
        },
    )
    export_seconds = time.perf_counter() - start
    start = time.perf_counter()
    publish_catalog(measured, SEED, dsn)
    publish_seconds = time.perf_counter() - start
    peak = peak_rss_bytes()
    try:
        route = os.environ["CATALOG_TEST_API_URL"] + "/api/v1/cards?limit=24"

        def request(_: int) -> tuple[float, bool]:
            started = time.perf_counter()
            try:
                with urlopen(route, timeout=10) as response:
                    body = json.load(response)
                    success = response.status == 200 and len(body["items"]) == 7
            except (OSError, ValueError):
                success = False
            return (time.perf_counter() - started) * 1000, success

        for index in range(10):
            request(index)
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            samples = list(pool.map(request, range(100)))
        duration = time.perf_counter() - start
        timings = sorted(elapsed for elapsed, _ in samples)
        with psycopg.connect(os.environ["CATALOG_TEST_ADMIN_DSN"]) as connection:
            postgres = connection.execute("SELECT version()").fetchone()[0]
            disk = connection.execute("SELECT pg_database_size(current_database())").fetchone()[0]
            plan = connection.execute(
                """EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON)
              SELECT c.oracle_id FROM catalog.published_catalog_card c
              WHERE c.catalog_snapshot_id=%s AND EXISTS(
              SELECT FROM catalog.published_catalog_printing p
              WHERE p.catalog_snapshot_id=c.catalog_snapshot_id AND p.oracle_id=c.oracle_id
              AND p.set_code='m11' AND p.rarity='common') ORDER BY c.name_key,c.oracle_id LIMIT 25
              """,
                (measured.name,),
            ).fetchone()[0]
        evidence = {
            "scope": (
                "8-printing bounded seed; warm integration measurements only. "
                "Full-scale latency, throughput and memory remain unverified."
            ),
            "machine": {
                "os": platform.platform(),
                "cpu": platform.processor(),
                "logical_cpus": os.cpu_count(),
                "python": platform.python_version(),
                "postgresql": postgres,
            },
            "catalog_snapshot_id": payload["catalog_snapshot_id"],
            "export_sha256": manifest["export_sha256"],
            "source_manifest_sha256": hashlib.sha256(
                (SEED / "manifest.json").read_bytes()
            ).hexdigest(),
            "source_bytes": sum(
                (SEED / record["raw_file"]).stat().st_size
                for record in json.loads((SEED / "manifest.json").read_bytes())["records"]
            ),
            "row_counts": manifest["row_counts"],
            "export_bytes": manifest["export_bytes"],
            "export_seconds": export_seconds,
            "publication_seconds": publish_seconds,
            "process_peak_rss_through_import_bytes": peak,
            "artifact_disk_bytes": sum(file.stat().st_size for file in measured.iterdir()),
            "disposable_database_bytes_including_test_snapshots": disk,
            "http": {
                "warmup_requests": 10,
                "requests": 100,
                "concurrent_readers": 20,
                "errors": sum(not ok for _, ok in samples),
                "duration_seconds": duration,
                "p50_ms": statistics.median(timings),
                "p95_ms": timings[94],
                "max_ms": timings[-1],
                "conditions": (
                    "Warm JVM/database; Python urllib on loopback; browser assets excluded."
                ),
            },
            "joint_printing_explain_analyze": plan,
        }
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(f"Measured bounded import and 100 API requests: {args.output}")
        if evidence["http"]["errors"]:
            raise RuntimeError("API measurement encountered failures")
    finally:
        rollback_catalog(dsn, previous, measured.name)


if __name__ == "__main__":
    main()
