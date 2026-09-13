"""Command-line entry point for reproducible local data operations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .ingest import ingest_scryfall


def main() -> None:
    parser = argparse.ArgumentParser(prog="mtg-scorer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scryfall_parser = subparsers.add_parser(
        "ingest-scryfall",
        help="download and normalize the current Scryfall default-cards bulk file",
    )
    scryfall_parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/local"),
        help="root for immutable raw snapshots and generated Parquet (default: data/local)",
    )
    export_parser = subparsers.add_parser(
        "export-catalog", help="export a verified bounded source sample"
    )
    export_parser.add_argument("--source-dir", type=Path, required=True)
    export_parser.add_argument("--output-root", type=Path, required=True)
    export_parser.add_argument("--created-at", default=None)
    publish_parser = subparsers.add_parser(
        "publish-catalog", help="atomically publish a catalog artifact"
    )
    publish_parser.add_argument("--source-dir", type=Path, required=True)
    publish_parser.add_argument("--artifact", type=Path, required=True)
    rollback_parser = subparsers.add_parser(
        "rollback-catalog", help="guarded rollback to a retained snapshot"
    )
    rollback_parser.add_argument("--target", required=True)
    rollback_parser.add_argument("--expected", required=True)
    arguments = parser.parse_args()

    if arguments.command == "ingest-scryfall":
        result = ingest_scryfall(arguments.data_dir)
        print(f"snapshot: {result.snapshot.snapshot_id}")
        print(f"oracle cards: {result.oracle_card_count}")
        print(f"printings: {result.printing_count}")
        print(f"oracle parquet: {result.oracle_cards_file}")
        print(f"printing parquet: {result.printings_file}")
    elif arguments.command == "export-catalog":
        from .publish.artifact import export_catalog

        print(
            export_catalog(
                arguments.source_dir, arguments.output_root, created_at=arguments.created_at
            )
        )
    elif arguments.command == "publish-catalog":
        from .publish.postgres import publish_catalog

        print(
            json.dumps(
                publish_catalog(
                    arguments.artifact, arguments.source_dir, os.environ["CATALOG_PUBLISH_DSN"]
                )
            )
        )
    elif arguments.command == "rollback-catalog":
        from .publish.postgres import rollback_catalog

        rollback_catalog(os.environ["CATALOG_PUBLISH_DSN"], arguments.target, arguments.expected)
        print("Active catalog rolled back; immutable rows retained.")


if __name__ == "__main__":
    main()
