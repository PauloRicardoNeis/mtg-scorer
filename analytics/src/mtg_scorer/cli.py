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
    score_parser = subparsers.add_parser(
        "score-topdeck", help="score one cohort of saved TopDeck responses into a run file"
    )
    score_parser.add_argument(
        "--source-dir", type=Path, required=True, help="probe output with manifest.json"
    )
    score_parser.add_argument("--cohort", type=Path, required=True, help="cohort rules JSON")
    score_parser.add_argument("--output-root", type=Path, required=True)
    wizards_parser = subparsers.add_parser(
        "score-wizards",
        help="score one cohort of saved Wizards Pro Tour coverage pages into a run file; "
        "card names resolve against the catalog in CATALOG_READ_DSN",
    )
    wizards_parser.add_argument(
        "--source-dir",
        type=Path,
        action="append",
        required=True,
        help="one event's probe output with manifest.json; repeat for a season",
    )
    wizards_parser.add_argument("--cohort", type=Path, required=True, help="cohort rules JSON")
    wizards_parser.add_argument("--output-root", type=Path, required=True)
    publish_scores_parser = subparsers.add_parser(
        "publish-scores", help="atomically publish a score-run file and make it active"
    )
    publish_scores_parser.add_argument("--run-file", type=Path, required=True)
    rollback_scores_parser = subparsers.add_parser(
        "rollback-scores", help="guarded rollback to a published score run"
    )
    rollback_scores_parser.add_argument("--target", required=True)
    rollback_scores_parser.add_argument("--expected", required=True)
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
    elif arguments.command == "score-topdeck":
        from .publish.score_run import score_topdeck

        print(score_topdeck(arguments.source_dir, arguments.cohort, arguments.output_root))
    elif arguments.command == "score-wizards":
        from .ingest.wizards import catalog_resolver
        from .publish.score_run import score_wizards

        print(
            score_wizards(
                arguments.source_dir,
                arguments.cohort,
                arguments.output_root,
                catalog_resolver(os.environ["CATALOG_READ_DSN"]),
            )
        )
    elif arguments.command == "publish-scores":
        from .publish.score_postgres import publish_score_run

        print(json.dumps(publish_score_run(arguments.run_file, os.environ["SCORE_PUBLISH_DSN"])))
    elif arguments.command == "rollback-scores":
        from .publish.score_postgres import rollback_score_run

        rollback_score_run(os.environ["SCORE_PUBLISH_DSN"], arguments.target, arguments.expected)
        print("Active score run rolled back; published runs retained.")


if __name__ == "__main__":
    main()
