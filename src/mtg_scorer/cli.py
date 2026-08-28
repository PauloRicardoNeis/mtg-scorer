"""Command-line entry point for reproducible local data operations."""

from __future__ import annotations

import argparse
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
    arguments = parser.parse_args()

    if arguments.command == "ingest-scryfall":
        result = ingest_scryfall(arguments.data_dir)
        print(f"snapshot: {result.snapshot.snapshot_id}")
        print(f"oracle cards: {result.oracle_card_count}")
        print(f"printings: {result.printing_count}")
        print(f"oracle parquet: {result.oracle_cards_file}")
        print(f"printing parquet: {result.printings_file}")


if __name__ == "__main__":
    main()
