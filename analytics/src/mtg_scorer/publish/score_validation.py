"""Executable score-run v2 and overall-run validation; shared by run-file writing and
publication."""

from __future__ import annotations

import json
import math
from bisect import bisect_left
from datetime import date
from itertools import pairwise
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .validation import contracts_dir

ROOT = contracts_dir()
SCHEMA = json.loads((ROOT / "score-run.schema.json").read_text())
OVERALL_SCHEMA = json.loads((ROOT / "overall-run.schema.json").read_text())


def validate_score_run(document: dict[str, Any]) -> None:
    """Check the closed schema, then the relationships a schema cannot express."""

    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(document)
    cards = {card["oracle_id"]: card for card in document["cards"]}
    if len(cards) != len(document["cards"]):
        raise ValueError("duplicate card oracle_id")
    for card in cards.values():
        if (card["top_cut_count"] is None) != (card["top_cut_known_decks"] == 0):
            raise ValueError(
                f"{card['oracle_id']}: top_cut_count must be unknown exactly when "
                "no result is known"
            )
        archetype = card["archetype"]
        if (archetype["label"] is None) != (archetype["labelled_deck_count"] == 0):
            raise ValueError(f"{card['oracle_id']}: archetype label and labelled decks disagree")
        top = card["archetypes"]["top"]
        leader = (top[0]["label"], top[0]["deck_count"]) if top else (None, 0)
        if leader != (archetype["label"], archetype["deck_count"]) or card["archetypes"][
            "distinct"
        ] < len(top):
            raise ValueError(f"{card['oracle_id']}: archetypes disagree with the leading label")
        record = card["record"]
        if record["decks"] > card["deck_count"] or card["mainboard_copies"] < card["deck_count"]:
            raise ValueError(f"{card['oracle_id']}: record or copies exceed the card's decks")
        games = record["wins"] + record["losses"] + record["draws"]
        if (card["performance"]["win_rate"] is None) != (games == 0):
            raise ValueError(f"{card['oracle_id']}: win rate must be unknown exactly without games")
    archetypes = document["cohort"]["archetypes"]
    if len({archetype["label"] for archetype in archetypes}) != len(archetypes):
        raise ValueError("duplicate archetype label")
    # Runs before feature pipeline card-usage-v5 describe archetypes by their cores alone.
    for archetype in (archetype for archetype in archetypes if "record" in archetype):
        label = archetype["label"]
        if (archetype["top_cut_count"] is None) != (archetype["top_cut_known_decks"] == 0):
            raise ValueError(
                f"{label}: top_cut_count must be unknown exactly when no result is known"
            )
        record = archetype["record"]
        counted = max(record["decks"], archetype["event_count"], archetype["top_cut_known_decks"])
        if counted > archetype["deck_count"]:
            raise ValueError(f"{label}: record, events or top cuts exceed the archetype's decks")
        games = record["wins"] + record["losses"] + record["draws"]
        if (archetype["performance"]["win_rate"] is None) != (games == 0):
            raise ValueError(f"{label}: win rate must be unknown exactly without games")
    _validate_decks(document)
    _validate_bounds(document)
    scored = {oracle_id for oracle_id, card in cards.items() if card["scored"]}
    if document["population"]["scored_cards"] != len(scored):
        raise ValueError("population scored_cards does not match the scored cards")
    identities = [
        [run["method_id"], run["method_version"], run["method_config_hash"]]
        for run in document["runs"]
    ]
    if identities != document["method_identities"]:
        raise ValueError("method_identities do not match the runs")
    if len({run["method_id"] for run in document["runs"]}) != len(document["runs"]):
        raise ValueError("duplicate method_id")
    for run in document["runs"]:
        card_ids = [score["card_id"] for score in run["scores"]]
        if len(card_ids) != len(set(card_ids)) or set(card_ids) != scored:
            raise ValueError(f"{run['method_id']} must score each scored card exactly once")
        outputs = set(run["outputs"])
        if any(set(score["values"]) != outputs for score in run["scores"]):
            raise ValueError(f"{run['method_id']} scores must hold exactly its declared outputs")


def _validate_decks(document: dict[str, Any]) -> None:
    """From feature pipeline card-usage-v7 on, a run lists its decks and every card its own;
    a card's decks must then recount its decks, copies, events, top cuts and record."""

    listing = [card for card in document["cards"] if "decks" in card]
    if "decks" not in document:
        if listing:
            raise ValueError("cards list decks the run does not publish")
        return
    if len(listing) != len(document["cards"]):
        raise ValueError("every card must list its decks")
    decks, cohort_events = document["decks"], document["cohort"]["events"]
    if len(decks) != document["cohort"]["totals"]["decks"]:
        raise ValueError("decks do not match the cohort's deck total")
    if len({deck["source_deck_id"] for deck in decks}) != len(decks):
        raise ValueError("duplicate source_deck_id")
    occurred = {event["source_event_id"]: event["occurred_on"] for event in cohort_events}
    if any(deck["source_event_id"] not in occurred for deck in decks):
        raise ValueError("a deck's event is not in the cohort")
    events = [deck["source_event_id"] for deck in decks]
    dates = [occurred[event] for event in events]
    if any(later > earlier for earlier, later in pairwise(dates)):
        raise ValueError("decks must list the newest event first")
    cuts = [deck["made_top_cut"] for deck in decks]
    records = [deck["record"] for deck in decks]
    played = bytearray(len(decks))
    for card in document["cards"]:
        oracle_id, positions = card["oracle_id"], card["decks"]
        if len(positions) != card["deck_count"] or len(card["deck_copies"]) != len(positions):
            raise ValueError(f"{oracle_id}: decks and copies must list each of the card's decks")
        if any(b <= a for a, b in pairwise(positions)) or (
            positions and positions[-1] >= len(decks)
        ):
            raise ValueError(f"{oracle_id}: decks must ascend within the run's decks")
        if sum(card["deck_copies"]) != card["mainboard_copies"]:
            raise ValueError(f"{oracle_id}: deck copies do not add up to its mainboard copies")
        if len({events[position] for position in positions}) != card["event_count"]:
            raise ValueError(f"{oracle_id}: its decks' events do not match its event count")
        known = [cuts[position] for position in positions if cuts[position] is not None]
        if (
            len(known) != card["top_cut_known_decks"]
            or (sum(known) if known else None) != card["top_cut_count"]
        ):
            raise ValueError(f"{oracle_id}: its decks' top cuts do not match its counts")
        recorded = [records[position] for position in positions if records[position]]
        if card["record"] != {
            "decks": len(recorded),
            **{key: sum(record[key] for record in recorded) for key in ("wins", "losses", "draws")},
        }:
            raise ValueError(f"{oracle_id}: its decks' records do not add up to its record")
        for position in positions:
            played[position] = 1
    # A published deck read its main deck completely, so some card lists every deck.
    if not all(played):
        raise ValueError("a deck has no main deck card")
    _validate_deck_lists(document)


def _validate_deck_lists(document: dict[str, Any]) -> None:
    """From feature pipeline card-usage-v8 on, every deck states its commanders and its
    sideboard; a commander is in the deck's own main deck, and a sideboard names each card
    once."""

    decks = document["decks"]
    stated = [deck for deck in decks if "sideboard" in deck]
    if not stated:
        return
    if len(stated) != len(decks):
        raise ValueError("every deck must state its commanders and sideboard")
    played = {card["oracle_id"]: card["decks"] for card in document["cards"]}
    for position, deck in enumerate(decks):
        for commander in deck["commanders"]:
            positions = played.get(commander, [])
            index = bisect_left(positions, position)
            if index == len(positions) or positions[index] != position:
                raise ValueError(f"{deck['source_deck_id']}: a commander is not in its main deck")
        sideboard = deck["sideboard"] or []
        if len({card["oracle_id"] for card in sideboard}) != len(sideboard):
            raise ValueError(f"{deck['source_deck_id']}: a sideboard card is listed twice")


def _validate_bounds(document: dict[str, Any]) -> None:
    """Mirror the database CHECKs the schema cannot express (migrations V4 to V10), so a
    file that passes here cannot fail on COPY. tests/test_score_validation_parity.py lists
    every CHECK against the check that covers it."""

    rules = document["cohort"]["rules"]
    if date.fromisoformat(rules["ends_before"]) <= date.fromisoformat(rules["starts_on"]):
        raise ValueError("the cohort window must end after it starts")
    for card in document["cards"]:
        oracle_id, decks = card["oracle_id"], card["deck_count"]
        if card["event_count"] > decks or card["top_cut_known_decks"] > decks:
            raise ValueError(f"{oracle_id}: events or known top cuts exceed the card's decks")
        cut = card["top_cut_count"]
        if cut is not None and cut > card["top_cut_known_decks"]:
            raise ValueError(f"{oracle_id}: top cuts exceed the decks with a known result")
        archetype = card["archetype"]
        if not archetype["deck_count"] <= archetype["labelled_deck_count"] <= decks:
            raise ValueError(
                f"{oracle_id}: labelled decks must lie between the archetype's decks and the card's"
            )
    for deck in document.get("decks", ()):
        if any(not card["name"].strip() for card in deck.get("sideboard") or ()):
            raise ValueError(f"{deck['source_deck_id']}: a sideboard card needs a name")
    _validate_finite_scores(document)


def _validate_finite_scores(document: dict[str, Any]) -> None:
    """JSON carries NaN and infinities that PostgreSQL's score columns reject."""

    for run in document["runs"]:
        for score in run["scores"]:
            for group in ("values", "inputs"):
                for name, value in score[group].items():
                    if value is not None and not math.isfinite(value):
                        raise ValueError(
                            f"{run['method_id']} {score['card_id']} {name}: "
                            "scores and inputs must be finite"
                        )


def validate_overall_run(document: dict[str, Any]) -> None:
    """Check the overall-run schema, then that cards, components and scores agree."""

    Draft202012Validator(OVERALL_SCHEMA, format_checker=FormatChecker()).validate(document)
    formats = [component["format_name"] for component in document["components"]]
    if len(set(formats)) != len(formats) or document["format_name"] in formats:
        raise ValueError("components must name distinct formats other than the run's own")
    if document["totals"]["formats"] != len(formats):
        raise ValueError("totals count a different number of formats than the components")
    cards = {card["oracle_id"]: card for card in document["cards"]}
    if len(cards) != len(document["cards"]):
        raise ValueError("duplicate card oracle_id")
    for card in cards.values():
        if (card["top_cut_count"] is None) != (card["top_cut_known_decks"] == 0):
            raise ValueError(
                f"{card['oracle_id']}: top_cut_count must be unknown exactly when "
                "no result is known"
            )
        if (
            card["event_count"] > card["deck_count"]
            or card["top_cut_known_decks"] > card["deck_count"]
            or card["record"]["decks"] > card["deck_count"]
            or card["mainboard_copies"] < card["deck_count"]
        ):
            raise ValueError(f"{card['oracle_id']}: counts exceed the card's decks")
        if not set(card["formats"]) <= set(formats):
            raise ValueError(f"{card['oracle_id']}: graded in a format that is not a component")
    if document["population"]["scored_cards"] != len(cards):
        raise ValueError("population scored_cards does not match the cards")
    identities = [
        [run["method_id"], run["method_version"], run["method_config_hash"]]
        for run in document["runs"]
    ]
    if identities != document["method_identities"]:
        raise ValueError("method_identities do not match the runs")
    if len({run["method_id"] for run in document["runs"]}) != len(document["runs"]):
        raise ValueError("duplicate method_id")
    for run in document["runs"]:
        card_ids = [score["card_id"] for score in run["scores"]]
        if len(card_ids) != len(set(card_ids)) or set(card_ids) != set(cards):
            raise ValueError(f"{run['method_id']} must score each card exactly once")
        outputs = set(run["outputs"])
        if any(set(score["values"]) != outputs for score in run["scores"]):
            raise ValueError(f"{run['method_id']} scores must hold exactly its declared outputs")
    _validate_finite_scores(document)
