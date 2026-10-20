"""Publish card prices from a retained Scryfall bulk file beside the catalog.

Scryfall's bulk prices are daily market estimates (TCGplayer for USD). Its guidance is
to use them only for trends or a general estimate of a card's value, so they are shown
with their date and never as a price to buy at. Each card gets the cheapest USD price
among the paper printings a sanctioned deck can play, in any finish.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

import psycopg

from mtg_scorer.publish.bulk import bulk_source

LOGGER = logging.getLogger(__name__)
LOCK_ID = 724604
RULE = "cheapest-playable-paper-usd-v1"
FINISHES = ("usd", "usd_foil", "usd_etched")


def playable_in_paper(card: dict[str, Any]) -> bool:
    """False for printings no sanctioned deck can play, whatever they cost.

    Gold-bordered World Championship decks, Collectors' Edition and other memorabilia
    share an Oracle identity with the real card but sell far below or above it.
    """

    return (
        "paper" in card.get("games", [])
        and not card.get("digital")
        and not card.get("oversized")
        and card.get("set_type") != "memorabilia"
        and card.get("border_color") != "gold"
    )


def cheapest_prices(cards: Iterable[dict[str, Any]]) -> dict[str, tuple[Decimal, str]]:
    """Each Oracle card's cheapest USD price and its printing; ties go to the lower id."""

    cheapest: dict[str, tuple[Decimal, str]] = {}
    for card in cards:
        oracle_id = card.get("oracle_id")
        prices = card.get("prices") or {}
        if not oracle_id or not playable_in_paper(card):
            continue
        for finish in FINISHES:
            if prices.get(finish) is None:
                continue
            offer = (Decimal(prices[finish]), card["id"])
            if offer[0] > 0 and (oracle_id not in cheapest or offer < cheapest[oracle_id]):
                cheapest[oracle_id] = offer
    return cheapest


def price_snapshot_id(content_sha256: str) -> str:
    """The same source bytes under the same rule always make the same snapshot."""

    return "prices-" + sha256(f"{content_sha256}:{RULE}".encode()).hexdigest()


def publish_prices(source_dir: Path, dsn: str) -> dict[str, Any]:
    """Load a verified bulk file's prices and make them the ones the API reads."""

    source_bytes, records = bulk_source(source_dir)
    manifest = json.loads(source_bytes)
    snapshot = price_snapshot_id(manifest["content_sha256"])
    prices = cheapest_prices(card for card, _ in records)
    with psycopg.connect(dsn, autocommit=True) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
        created = connection.execute(
            "INSERT INTO prices.price_snapshot (price_snapshot_id,source,source_snapshot_id,"
            "source_sha256,source_updated_at,rule,card_count) VALUES (%s,'scryfall',%s,%s,%s,%s,%s)"
            " ON CONFLICT (price_snapshot_id) DO NOTHING RETURNING price_snapshot_id",
            (
                snapshot,
                manifest["snapshot_id"],
                manifest["content_sha256"],
                manifest["source_updated_at"],
                RULE,
                len(prices),
            ),
        ).fetchone()
        if created:
            with connection.cursor().copy(
                "COPY prices.card_price (price_snapshot_id,oracle_id,usd,usd_scryfall_id)"
                " FROM STDIN"
            ) as copy:
                for oracle_id, (usd, scryfall_id) in sorted(prices.items()):
                    copy.write_row((snapshot, oracle_id, usd, scryfall_id))
            connection.execute("ANALYZE prices.card_price")
        connection.execute(
            "INSERT INTO prices.active_price_snapshot (price_snapshot_id) VALUES (%s)"
            " ON CONFLICT (singleton) DO UPDATE SET price_snapshot_id=EXCLUDED.price_snapshot_id",
            (snapshot,),
        )
    LOGGER.info("price snapshot %s active with %d cards", snapshot, len(prices))
    return {
        "price_snapshot_id": snapshot,
        "cards": len(prices),
        "state": "published" if created else "already_published",
    }
