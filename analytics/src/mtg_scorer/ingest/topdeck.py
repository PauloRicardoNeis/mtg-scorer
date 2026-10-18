"""Offline adapter for saved TopDeck bulk tournament responses.

Reads a directory written by ``scripts/probe_tournaments.py``: a ``manifest.json``
listing every saved response with its SHA-256, next to the raw JSON files. Each file
is verified against the manifest before it is parsed. Nothing here calls the network.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..domain import (
    CoverageDimension,
    CoverageProfile,
    CoverageScope,
    DeckCard,
    DeckEntry,
    Provenance,
    Standing,
    Tournament,
)

SOURCE = "topdeck"
PARSER_VERSION = "topdeck-bulk-v1"

# How each event's top-cut membership was established.
BRACKET_RECORD = "bracket_record"
STANDING_ORDER = "standing_order"
INCONSISTENT_ORDER = "inconsistent_order"
NO_TOP_CUT = "no_top_cut"


@dataclass(frozen=True, slots=True)
class RawFile:
    """One saved response and how its retrieval time is known."""

    name: str
    sha256: str
    bytes: int
    retrieved_at: datetime
    retrieved_at_basis: str


@dataclass(frozen=True, slots=True)
class TopDeckSnapshot:
    """Facts parsed from one verified directory of saved responses."""

    dataset_snapshot_id: str
    raw_files: tuple[RawFile, ...]
    tournaments: tuple[Tournament, ...]
    decks: tuple[DeckEntry, ...]
    standings: tuple[Standing, ...]
    top_cut_basis: Mapping[str, str]
    quarantined_card_lines: int
    # Decks with an unreadable mainboard line; their card usage is not complete.
    incomplete_mainboards: frozenset[str]


def read_saved_responses(directory: Path) -> TopDeckSnapshot:
    """Verify and parse every bulk-search response listed in ``manifest.json``."""

    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    raw_files: list[RawFile] = []
    events: dict[str, tuple[dict[str, Any], RawFile]] = {}
    for request in manifest["requests"]:
        path = directory / request["raw_file"]
        payload = path.read_bytes()
        digest = sha256(payload).hexdigest()
        if digest != request["sha256"]:
            raise ValueError(f"{request['raw_file']} does not match its manifest SHA-256")
        raw = RawFile(request["raw_file"], digest, len(payload), *_retrieval(request, path))
        raw_files.append(raw)
        for event in json.loads(payload):
            tid = event["TID"]
            if tid in events and events[tid][0] != event:
                raise ValueError(f"event {tid} appears twice with different content")
            events.setdefault(tid, (event, raw))

    tournaments: list[Tournament] = []
    decks: list[DeckEntry] = []
    standings: list[Standing] = []
    basis: dict[str, str] = {}
    quarantined = 0
    incomplete: set[str] = set()
    for tid, (event, raw) in sorted(events.items()):
        rows = event.get("standings") or []
        made_cut, basis[tid] = _top_cut(rows, event.get("topCut") or 0)
        tournaments.append(_tournament(event, rows, _provenance(tid, raw, directory)))
        for position, row in enumerate(rows, start=1):
            deck_id = f"{tid}#{position}"
            provenance = _provenance(deck_id, raw, directory)
            standings.append(
                Standing(
                    provenance=provenance,
                    source_event_id=tid,
                    source_deck_id=deck_id,
                    wins=row.get("wins"),
                    losses=row.get("losses"),
                    draws=row.get("draws"),
                    byes=row.get("byes"),
                    made_top_cut=made_cut[position - 1],
                )
            )
            deck, skipped_main, skipped_side = _deck(row, tid, provenance)
            quarantined += skipped_main + skipped_side
            if deck is not None:
                decks.append(deck)
                if skipped_main:
                    incomplete.add(deck_id)

    identity = sha256(
        json.dumps(
            {
                "source": SOURCE,
                "parser_version": PARSER_VERSION,
                "files": sorted([raw.name, raw.sha256] for raw in raw_files),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return TopDeckSnapshot(
        dataset_snapshot_id=f"topdeck-{identity}",
        raw_files=tuple(raw_files),
        tournaments=tuple(tournaments),
        decks=tuple(decks),
        standings=tuple(standings),
        top_cut_basis=basis,
        quarantined_card_lines=quarantined,
        incomplete_mainboards=frozenset(incomplete),
    )


def _retrieval(request: Mapping[str, Any], path: Path) -> tuple[datetime, str]:
    # Responses reused by a resumed probe carry no timestamp; the file's own write
    # time is then the closest record of when it was fetched.
    if request.get("retrieved_at"):
        return datetime.fromisoformat(request["retrieved_at"]), "manifest"
    return datetime.fromtimestamp(path.stat().st_mtime, UTC), "file_mtime"


def _provenance(record_id: str, raw: RawFile, directory: Path) -> Provenance:
    return Provenance(
        source=SOURCE,
        source_record_id=record_id,
        retrieved_at=raw.retrieved_at,
        parser_version=PARSER_VERSION,
        raw_snapshot_ref=f"{directory.name}/{raw.name}",
    )


def _tournament(
    event: Mapping[str, Any], rows: list[dict[str, Any]], provenance: Provenance
) -> Tournament:
    players = len(rows)
    listed = sum(1 for row in rows if _mainboard(row))
    recorded = sum(
        1 for row in rows if all(row.get(key) is not None for key in ("wins", "losses", "draws"))
    )
    return Tournament(
        provenance=provenance,
        occurred_on=datetime.fromtimestamp(event["startDate"], UTC).date(),
        format_name=event["format"],
        source_format_name=event["format"],
        player_count=players or None,
        top_cut_size=event.get("topCut") or 0,
        coverage=CoverageProfile(
            decklists=_coverage(listed, players),
            standings=_coverage(recorded, players),
            # Round data was not requested, which is not the same as having none.
            matches=CoverageDimension.unknown(),
        ),
    )


def _coverage(observed: int, expected: int) -> CoverageDimension:
    if expected == 0:
        return CoverageDimension.unknown()
    if observed == 0:
        return CoverageDimension(CoverageScope.NONE, 0, expected)
    scope = CoverageScope.FULL_FIELD if observed == expected else CoverageScope.PARTIAL
    return CoverageDimension(scope, observed, expected)


def _top_cut(rows: list[dict[str, Any]], size: int) -> tuple[list[bool | None], str]:
    if size == 0:
        return [None] * len(rows), NO_TOP_CUT
    if rows and all(
        row.get("winsBracket") is not None and row.get("lossesBracket") is not None for row in rows
    ):
        return [row["winsBracket"] + row["lossesBracket"] > 0 for row in rows], BRACKET_RECORD
    # Without bracket columns, the response order is read as the final standings. That
    # is undocumented, so it is used only if no player below the cut has more wins
    # than a player inside it.
    wins = [row.get("wins") for row in rows]
    if None in wins or (
        len(rows) > size and min(wins[:size], default=0) < max(wins[size:], default=0)
    ):
        return [None] * len(rows), INCONSISTENT_ORDER
    return [position < size for position in range(len(rows))], STANDING_ORDER


def _mainboard(row: Mapping[str, Any]) -> Mapping[str, Any]:
    deck = row.get("deckObj") or {}
    return deck.get("Mainboard") or {}


def _deck(
    row: Mapping[str, Any], tid: str, provenance: Provenance
) -> tuple[DeckEntry | None, int, int]:
    """Return the deck plus how many mainboard and sideboard lines were unreadable."""

    if not _mainboard(row):
        return None, 0, 0
    deck = row["deckObj"]
    # One entry per oracle id: [first name seen, mainboard copies, sideboard copies].
    copies: dict[str, list[Any]] = {}
    skipped = [0, 0]
    for slot, zone in enumerate(("Mainboard", "Sideboard")):
        for name, line in (deck.get(zone) or {}).items():
            oracle_id = (line or {}).get("id")
            count = (line or {}).get("count")
            if not oracle_id or not isinstance(count, int) or count <= 0:
                skipped[slot] += 1
                continue
            copies.setdefault(oracle_id, [name, 0, 0])[1 + slot] += count
    label = (row.get("archetype") or "").strip() or None
    cards = tuple(
        DeckCard(oracle_id, name, mainboard_count=main, sideboard_count=side)
        for oracle_id, (name, main, side) in copies.items()
    )
    entry = DeckEntry(
        provenance=provenance,
        source_event_id=tid,
        cards=cards,
        # An unreadable sideboard line means the sideboard was not fully observed.
        sideboard_observed="Sideboard" in deck and not skipped[1],
        archetype_label=label,
    )
    return entry, skipped[0], skipped[1]
