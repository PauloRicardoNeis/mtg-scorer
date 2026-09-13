"""Face-aware Scryfall projection with deterministic Oracle representatives."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date
from typing import Any

from mtg_scorer.normalize.names import name_key

PARSER_VERSION = "scryfall-catalog-v1"
SCHEMA_VERSION = "catalog-publication-v1"
MULTIFACE_LAYOUTS = {
    "transform",
    "modal_dfc",
    "split",
    "adventure",
    "flip",
    "double_faced_token",
    "reversible_card",
}


def project_catalog(
    records: Iterable[tuple[dict[str, Any], dict[str, str]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    """Project verified source records; reject conflicts instead of choosing by arrival order."""
    candidates: dict[str, list[dict[str, Any]]] = {}
    printings: dict[str, dict[str, Any]] = {}
    originals: dict[str, dict[str, Any]] = {}
    excluded: Counter[str] = Counter()
    for source, provenance in records:
        oracle_id = source.get("oracle_id")
        if not oracle_id:
            excluded["missing_oracle_id"] += 1
            continue
        if source["layout"] in MULTIFACE_LAYOUTS and len(source.get("card_faces", [])) < 2:
            excluded["missing_required_faces"] += 1
            continue
        printing_id = source["id"]
        images = []
        for index, face in [(None, source), *enumerate(source.get("card_faces", []))]:
            uri = face.get("image_uris", {}).get("normal")
            if uri:
                images.append(
                    {"face_index": index, "source_uri": uri, "artist": face.get("artist")}
                )
        printing = {
            "scryfall_id": printing_id,
            "oracle_id": oracle_id,
            "set_code": source["set"],
            "set_name": source["set_name"],
            "collector_number": source["collector_number"],
            "rarity": source["rarity"],
            "released_on": source.get("released_at"),
            "language": source["lang"],
            "games": sorted(source["games"]),
            "source_uri": source["scryfall_uri"],
            **provenance,
            "images": images,
        }
        if printing_id in printings:
            if printings[printing_id] != printing or originals[printing_id] != source:
                raise ValueError("conflicting duplicate printing")
            continue
        printings[printing_id] = printing
        originals[printing_id] = source
        candidates.setdefault(oracle_id, []).append(source)

    cards, faces, aliases = [], [], []
    for oracle_id, versions in sorted(candidates.items()):

        def preference(card: dict[str, Any]) -> tuple[bool, int, str]:
            released = card.get("released_at")
            return (
                card["lang"] != "en",
                -date.fromisoformat(released).toordinal() if released else 0,
                card["id"],
            )

        source = min(versions, key=preference)
        source_faces = source.get("card_faces", [])
        colors = source.get("colors")
        if (
            colors is None
            and source_faces
            and all(face.get("colors") is not None for face in source_faces)
        ):
            colors = [
                color for color in "WUBRG" if any(color in face["colors"] for face in source_faces)
            ]
        cards.append(
            {
                "oracle_id": oracle_id,
                "source_scryfall_id": source["id"],
                "name": source["name"],
                "name_key": name_key(source["name"]),
                "layout": source["layout"],
                "mana_value": float(source["cmc"]) if source.get("cmc") is not None else None,
                "colors": colors,
                "color_identity": source.get("color_identity"),
                **{key: source.get(key) for key in ("mana_cost", "oracle_text", "type_line")},
            }
        )
        card_aliases = {(name_key(source["name"]), "canonical")}
        for index, face in enumerate(source_faces):
            faces.append(
                {
                    "oracle_id": oracle_id,
                    "face_index": index,
                    "name": face["name"],
                    **{
                        key: face.get(key)
                        for key in ("mana_cost", "oracle_text", "type_line", "colors")
                    },
                }
            )
            card_aliases.add((name_key(face["name"]), "face"))
        aliases.extend(
            {"oracle_id": oracle_id, "alias_key": key, "kind": kind}
            for key, kind in sorted(card_aliases)
        )
    return {
        "cards": cards,
        "faces": faces,
        "printings": [printings[key] for key in sorted(printings)],
        "aliases": aliases,
    }, dict(sorted(excluded.items()))
