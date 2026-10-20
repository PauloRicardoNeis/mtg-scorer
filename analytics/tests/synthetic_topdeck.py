"""Builders for SYNTHETIC saved TopDeck responses. Every event, deck and id is invented."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

# Oracle ids are UUIDs; these are derived from names so they are clearly invented.
BOLT = str(uuid5(NAMESPACE_URL, "synthetic-oracle-bolt"))
COUNTERSPELL = str(uuid5(NAMESPACE_URL, "synthetic-oracle-counterspell"))
ISLAND = str(uuid5(NAMESPACE_URL, "synthetic-oracle-island"))


def start(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp())


def deck(main: dict, side: dict | None = None) -> dict:
    """A structured deck; ``main``/``side`` map names to (oracle id, copies)."""

    zones = {"Mainboard": {name: {"id": i, "count": c} for name, (i, c) in main.items()}}
    if side is not None:
        zones["Sideboard"] = {name: {"id": i, "count": c} for name, (i, c) in side.items()}
    return {**zones, "metadata": {"game": "Magic: The Gathering", "format": "Modern"}}


def commander_deck(commanders: dict, main: dict, *, zone: str = "Commanders") -> dict:
    """A commander-format deck; both maps go from names to (oracle id, copies)."""

    return {
        zone: {name: {"id": i, "count": c} for name, (i, c) in commanders.items()},
        "Mainboard": {name: {"id": i, "count": c} for name, (i, c) in main.items()},
        "metadata": {"game": "Magic: The Gathering", "format": "EDH"},
    }


def row(wins: int, losses: int = 0, draws: int = 0, *, deck_obj=None, archetype=None, **extra):
    return {
        "decklist": None,
        "deckObj": deck_obj,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        **({"archetype": archetype} if archetype is not None else {}),
        **extra,
    }


def event(tid: str, rows: list, *, day="2026-03-10", top_cut=0, fmt="Modern") -> dict:
    return {
        "TID": tid,
        "tournamentName": f"Synthetic {tid}",
        "swissNum": 3,
        "startDate": start(day),
        "game": "Magic: The Gathering",
        "format": fmt,
        "topCut": top_cut,
        "standings": rows,
        "eventData": {},
    }


def save(directory: Path, files: dict[str, list], retrieved_at: dict | None = None) -> Path:
    """Write the responses plus a probe-style manifest with each file's SHA-256."""

    directory.mkdir(parents=True, exist_ok=True)
    requests = []
    for name, events in files.items():
        payload = json.dumps(events).encode()
        (directory / name).write_bytes(payload)
        request = {
            "method": "POST",
            "url": "https://topdeck.gg/api/v2/tournaments",
            "raw_file": name,
            "bytes": len(payload),
            "sha256": sha256(payload).hexdigest(),
        }
        if retrieved_at and name in retrieved_at:
            request["retrieved_at"] = retrieved_at[name]
        requests.append(request)
    manifest = {"probe_version": "synthetic", "requests": requests}
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def open_event() -> dict:
    """Four players, a top 2, three structured lists."""

    return event(
        "synthetic-open",
        [
            row(
                3, deck_obj=deck({"Bolt": (BOLT, 4), "Island": (ISLAND, 10)}, {}), archetype="Burn"
            ),
            row(
                2,
                1,
                deck_obj=deck({"Bolt": (BOLT, 2), "Counterspell": (COUNTERSPELL, 4)}, {}),
                archetype="Control",
            ),
            row(1, 2, deck_obj=deck({"Counterspell": (COUNTERSPELL, 4)}), archetype="Control"),
            row(0, 3),
        ],
        top_cut=2,
    )


def weekly_event() -> dict:
    """Two players, no top cut, both lists published."""

    return event(
        "synthetic-weekly",
        [
            row(1, deck_obj=deck({"Bolt": (BOLT, 4)}, {}), archetype="Burn"),
            row(
                0,
                1,
                deck_obj=deck({"Island": (ISLAND, 20), "Counterspell": (COUNTERSPELL, 4)}, {}),
                archetype="Control",
            ),
        ],
        day="2026-04-02",
    )
