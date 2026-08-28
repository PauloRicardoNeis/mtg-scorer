"""Source adapters and snapshot ingestion entry points."""

from .scryfall import ScryfallIngestResult, ingest_scryfall

__all__ = ["ScryfallIngestResult", "ingest_scryfall"]
