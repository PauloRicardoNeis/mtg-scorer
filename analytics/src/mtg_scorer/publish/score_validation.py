"""Executable score-run v2 validation; shared by run-file writing and publication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[4] / "contracts"
SCHEMA = json.loads((ROOT / "score-run.schema.json").read_text())


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
