"""Real PostgreSQL proof for card prices; TEST_DATABASE_DSN must name a disposable database.

Every bulk file below is SYNTHETIC. Each test writes source bytes of its own, so its
snapshot identity is unique and the suite can share one database with other tests.
"""

import gzip
import hashlib
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest

from mtg_scorer.publish.prices import price_snapshot_id, publish_prices

DSN = os.environ.get("TEST_DATABASE_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="real PostgreSQL TEST_DATABASE_DSN required")
BOLT = "4457ed35-7c10-48c8-9776-456485fdf070"
COUNTERSPELL = "8c2996d9-3287-4480-8c04-7a378e37e3cf"


def role_dsn(role):
    return psycopg.conninfo.make_conninfo(DSN, options=f"-c role={role}")


def retained(tmp_path, cards):
    """A retained bulk directory as the import worker leaves one."""

    directory = tmp_path / uuid4().hex
    directory.mkdir()
    raw = gzip.compress("".join(json.dumps(card) + "\n" for card in cards).encode())
    (directory / "default-cards.bulk").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "raw_file": "default-cards.bulk",
                "content_sha256": digest,
                "snapshot_id": f"scryfall-default-cards-synthetic-{digest[:12]}",
                "retrieved_at": "2026-09-28T03:42:50+00:00",
                "source_updated_at": "2026-09-27T21:05:46.301+00:00",
            }
        )
    )
    return directory, price_snapshot_id(digest)


def card(scryfall_id, oracle_id, usd, **fields):
    return {
        "id": scryfall_id,
        "oracle_id": oracle_id,
        "name": "Synthetic",
        "games": ["paper"],
        "set_type": "expansion",
        "border_color": "black",
        "prices": {"usd": usd, "usd_foil": None, "usd_etched": None},
        # A unique field keeps every test's bytes, and so its snapshot, distinct.
        "nonce": uuid4().hex,
        **fields,
    }


def active(connection):
    found = connection.execute("SELECT price_snapshot_id FROM prices.active_price_snapshot")
    row = found.fetchone()
    return row[0] if row else None


def test_prices_publish_once_become_active_and_are_read_only_for_the_api(tmp_path):
    first = str(uuid4())
    directory, snapshot = retained(
        tmp_path,
        [
            card(first, BOLT, "0.95"),
            card(str(uuid4()), BOLT, "4.20"),
            card(str(uuid4()), BOLT, "0.10", border_color="gold"),
            card(str(uuid4()), COUNTERSPELL, None),
        ],
    )

    result = publish_prices(directory, role_dsn("price_publisher"))

    assert result == {"price_snapshot_id": snapshot, "cards": 1, "state": "published"}
    assert publish_prices(directory, role_dsn("price_publisher"))["state"] == "already_published"
    with psycopg.connect(role_dsn("price_reader"), autocommit=True) as reader:
        assert active(reader) == snapshot
        rows = reader.execute(
            "SELECT oracle_id::text, usd::text, usd_scryfall_id::text FROM prices.card_price"
            " WHERE price_snapshot_id=%s",
            (snapshot,),
        ).fetchall()
        assert rows == [(BOLT, "0.95", first)]
        header = reader.execute(
            "SELECT source_updated_at, rule, card_count FROM prices.price_snapshot"
            " WHERE price_snapshot_id=%s",
            (snapshot,),
        ).fetchone()
        assert header[0] == datetime(2026, 9, 27, 21, 5, 46, 301000, tzinfo=UTC)
        assert header[1:] == ("cheapest-playable-paper-usd-v1", 1)
        for statement in (
            "DELETE FROM prices.card_price",
            "UPDATE prices.active_price_snapshot SET price_snapshot_id=price_snapshot_id",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                reader.execute(statement)


def test_the_publisher_moves_the_pointer_but_never_rewrites_prices(tmp_path):
    older, older_id = retained(tmp_path, [card(str(uuid4()), BOLT, "1.00")])
    newer, newer_id = retained(tmp_path, [card(str(uuid4()), BOLT, "2.00")])
    publish_prices(older, role_dsn("price_publisher"))
    publish_prices(newer, role_dsn("price_publisher"))

    with psycopg.connect(role_dsn("price_publisher"), autocommit=True) as writer:
        assert active(writer) == newer_id
        for statement in (
            "UPDATE prices.card_price SET usd=usd",
            "DELETE FROM prices.card_price",
            "DELETE FROM prices.price_snapshot",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                writer.execute(statement)

    # Republishing retained older bytes points back at their untouched snapshot.
    assert publish_prices(older, role_dsn("price_publisher"))["state"] == "already_published"
    with psycopg.connect(role_dsn("price_reader"), autocommit=True) as reader:
        assert active(reader) == older_id


def test_a_bulk_file_that_no_longer_matches_its_manifest_is_refused(tmp_path):
    directory, snapshot = retained(tmp_path, [card(str(uuid4()), BOLT, "1.00")])
    (directory / "default-cards.bulk").write_bytes(gzip.compress(b"{}\n"))

    with pytest.raises(ValueError, match="checksum"):
        publish_prices(directory, role_dsn("price_publisher"))
    with psycopg.connect(role_dsn("price_reader"), autocommit=True) as reader:
        found = reader.execute(
            "SELECT count(*) FROM prices.price_snapshot WHERE price_snapshot_id=%s", (snapshot,)
        ).fetchone()[0]
        assert found == 0
