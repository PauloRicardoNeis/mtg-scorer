"""Test-only refresh/fault controls; never imported by an application request."""

import argparse
import json
import os
from pathlib import Path

import psycopg
from mtg_scorer.publish.artifact import export_catalog
from mtg_scorer.publish.postgres import publish_catalog, rollback_catalog

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["refresh", "rollback", "unavailable", "available"])
    parser.add_argument("--target")
    parser.add_argument("--expected")
    args = parser.parse_args()
    publisher = os.environ["CATALOG_TEST_PUBLISH_DSN"]
    if args.action == "refresh":
        seed = ROOT / "analytics/seeds/scryfall-layouts-v1"
        directory = export_catalog(
            seed,
            ROOT / ".local/browser-refresh-v2",
            created_at="2026-09-08T00:46:15Z",
            selection={
                "kind": "bounded_sample",
                "description": (
                    "Real layout sample replay for browser snapshot continuity verification"
                ),
            },
        )
        result = publish_catalog(directory, seed, publisher)
        # A retained, already published test refresh may need explicit reactivation on rerun.
        with psycopg.connect(publisher) as connection:
            previous = connection.execute(
                "SELECT catalog_snapshot_id FROM catalog.active_catalog"
            ).fetchone()[0]
        if previous != directory.name:
            rollback_catalog(publisher, directory.name, previous)
        print(json.dumps(result))
    elif args.action == "rollback":
        rollback_catalog(publisher, args.target, args.expected)
    else:
        # Deliberately remove read permission on the disposable integration database.
        with psycopg.connect(os.environ["CATALOG_TEST_ADMIN_DSN"]) as connection:
            connection.execute(
                "REVOKE SELECT ON catalog.published_snapshot FROM catalog_reader"
                if args.action == "unavailable"
                else "GRANT SELECT ON catalog.published_snapshot TO catalog_reader"
            )


if __name__ == "__main__":
    main()
