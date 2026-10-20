"""Which printing's price stands for a card; every card below is SYNTHETIC."""

from decimal import Decimal

from mtg_scorer.publish.prices import RULE, cheapest_prices, price_snapshot_id


def printing(scryfall_id, oracle_id="oracle-bolt", **fields):
    prices = {"usd": None, "usd_foil": None, "usd_etched": None, "eur": "9.99", "tix": "0.10"}
    prices.update(fields.pop("prices", {}))
    return {
        "id": scryfall_id,
        "oracle_id": oracle_id,
        "games": ["paper", "mtgo"],
        "set_type": "expansion",
        "border_color": "black",
        "prices": prices,
        **fields,
    }


def test_the_cheapest_usd_price_of_any_printing_and_finish_wins():
    prices = cheapest_prices(
        [
            printing("p-3", prices={"usd": "2.10", "usd_foil": "9.00"}),
            printing("p-1", prices={"usd_foil": "0.80"}),
            printing("p-2", prices={"usd_etched": "1.50"}),
            printing("p-4", "oracle-other", prices={"usd": "12.00"}),
        ]
    )

    assert prices == {
        "oracle-bolt": (Decimal("0.80"), "p-1"),
        "oracle-other": (Decimal("12.00"), "p-4"),
    }


def test_equal_prices_go_to_the_lower_printing_id_whatever_the_order():
    cards = [printing("p-b", prices={"usd": "1.00"}), printing("p-a", prices={"usd": "1.00"})]

    assert cheapest_prices(cards) == cheapest_prices(reversed(cards))
    assert cheapest_prices(cards)["oracle-bolt"] == (Decimal("1.00"), "p-a")


def test_printings_no_sanctioned_deck_can_play_never_set_the_price():
    unplayable = [
        printing("gold", border_color="gold", prices={"usd": "0.25"}),
        printing("ced", set_type="memorabilia", prices={"usd": "0.30"}),
        printing("big", oversized=True, prices={"usd": "0.35"}),
        printing("arena", games=["arena"], digital=True, prices={"usd": "0.40"}),
        printing("mtgo", games=["mtgo"], prices={"usd": "0.45"}),
    ]

    assert cheapest_prices([*unplayable, printing("real", prices={"usd": "3.00"})]) == {
        "oracle-bolt": (Decimal("3.00"), "real")
    }
    assert cheapest_prices(unplayable) == {}


def test_cards_without_an_identity_or_a_usd_price_are_left_unpriced():
    assert (
        cheapest_prices(
            [
                printing("no-oracle", oracle_id=None, prices={"usd": "1.00"}),
                printing("eur-only"),
                printing("zero", prices={"usd": "0"}),
                {"id": "no-prices", "oracle_id": "oracle-bolt", "games": ["paper"]},
            ]
        )
        == {}
    )


def test_a_snapshot_is_named_by_its_source_bytes_and_rule():
    first = price_snapshot_id("a" * 64)

    assert first == price_snapshot_id("a" * 64)
    assert first != price_snapshot_id("b" * 64)
    assert first.startswith("prices-") and len(first) == len("prices-") + 64
    assert RULE == "cheapest-playable-paper-usd-v1"
