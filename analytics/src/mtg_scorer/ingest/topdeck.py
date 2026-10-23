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
from sys import intern
from typing import Any
from urllib.parse import quote
from uuid import UUID

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
# v4 kept each event's name and page; v5 links the public results page, since the
# event page asks visitors to sign in.
PARSER_VERSION = "topdeck-bulk-v5"
EVENT_URL = "https://topdeck.gg/bracket/{}"
# Cards in the Mainboard and in a commander zone are played: commander formats keep
# the commander apart from the Mainboard. The Sideboard is kept separately.
MAINBOARD = "Mainboard"
# Commander zone names, compared case-insensitively: most lists say "Commanders", a
# few "Commander" or "COMMANDER".
COMMANDER_ZONES = frozenset({"commanders", "commander"})
# The rules allow two commanders at most (partners, a background, an oathbreaker and
# its signature spell). A longer commander zone holds a misplaced decklist, so its
# cards are played but none of them is taken for a commander.
MAX_COMMANDERS = 2

# How each event's top-cut membership was established.
BRACKET_RECORD = "bracket_record"
STANDING_ORDER = "standing_order"
INCONSISTENT_ORDER = "inconsistent_order"
NO_TOP_CUT = "no_top_cut"
UNKNOWN_TOP_CUT = "unknown_top_cut"


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
    # Team events report one standing per team, not per deck, so none of them is read.
    team_events_skipped: int = 0


def read_saved_responses(directory: Path) -> TopDeckSnapshot:
    """Verify and parse every bulk-search response listed in ``manifest.json``.

    Each file's events become facts as soon as it is read, keeping only a content hash
    per event, so memory holds the facts rather than every raw response at once.
    """

    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    raw_files: list[RawFile] = []
    parsed: dict[str, tuple[str, _EventFacts | None]] = {}
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
            content = sha256(
                json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if tid in parsed:
                if parsed[tid][0] != content:
                    raise ValueError(f"event {tid} appears twice with different content")
                continue
            facts = None if event.get("isTeamEvent") else _event_facts(event, raw, directory)
            parsed[tid] = (content, facts)

    tournaments: list[Tournament] = []
    decks: list[DeckEntry] = []
    standings: list[Standing] = []
    basis: dict[str, str] = {}
    quarantined = 0
    incomplete: set[str] = set()
    teams = 0
    for tid in sorted(parsed):
        facts = parsed[tid][1]
        if facts is None:
            teams += 1
            continue
        tournaments.append(facts.tournament)
        standings.extend(facts.standings)
        decks.extend(facts.decks)
        basis[tid] = facts.top_cut_basis
        quarantined += facts.quarantined
        incomplete.update(facts.incomplete)

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
        team_events_skipped=teams,
    )


@dataclass(frozen=True, slots=True)
class _EventFacts:
    tournament: Tournament
    standings: tuple[Standing, ...]
    decks: tuple[DeckEntry, ...]
    top_cut_basis: str
    quarantined: int
    incomplete: tuple[str, ...]


def _event_facts(event: Mapping[str, Any], raw: RawFile, directory: Path) -> _EventFacts:
    tid = event["TID"]
    rows = event.get("standings") or []
    made_cut, top_cut_basis = _top_cut(rows, _top_cut_size(event.get("topCut")))
    tournament = _tournament(event, rows, _provenance(tid, raw, directory))
    standings: list[Standing] = []
    decks: list[DeckEntry] = []
    quarantined = 0
    incomplete: list[str] = []
    for position, row in enumerate(rows, start=1):
        deck_id = f"{tid}#{position}"
        provenance = _provenance(deck_id, raw, directory)
        standings.append(
            Standing(
                provenance=provenance,
                source_event_id=tid,
                source_deck_id=deck_id,
                wins=_count(row.get("wins")),
                losses=_count(row.get("losses")),
                draws=_count(row.get("draws")),
                byes=_count(row.get("byes")),
                made_top_cut=made_cut[position - 1],
            )
        )
        deck, skipped_main, skipped_side = _deck(row, tid, provenance)
        quarantined += skipped_main + skipped_side
        if deck is not None:
            decks.append(deck)
            if skipped_main:
                incomplete.append(deck_id)
    return _EventFacts(
        tournament, tuple(standings), tuple(decks), top_cut_basis, quarantined, tuple(incomplete)
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
        raw_snapshot_ref=intern(f"{directory.name}/{raw.name}"),
    )


def _tournament(
    event: Mapping[str, Any], rows: list[dict[str, Any]], provenance: Provenance
) -> Tournament:
    players = len(rows)
    listed = sum(1 for row in rows if _mainboard(row))
    recorded = sum(
        1
        for row in rows
        if all(_count(row.get(key)) is not None for key in ("wins", "losses", "draws"))
    )
    return Tournament(
        provenance=provenance,
        occurred_on=datetime.fromtimestamp(event["startDate"], UTC).date(),
        format_name=event["format"],
        source_format_name=event["format"],
        player_count=players or None,
        top_cut_size=_top_cut_size(event.get("topCut")),
        name=(event.get("tournamentName") or "").strip() or None,
        source_url=EVENT_URL.format(quote(event["TID"], safe="")),
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


def _count(value: object) -> int | None:
    """A record count, or unknown: the source occasionally reports values such as -1."""

    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _top_cut_size(value: object) -> int | None:
    """Players in the cut; no value means no cut, unreadable text such as "8-0" is unknown."""

    if value is None:
        return 0
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return _count(value)


def _top_cut(rows: list[dict[str, Any]], size: int | None) -> tuple[list[bool | None], str]:
    if size is None:
        return [None] * len(rows), UNKNOWN_TOP_CUT
    if size == 0:
        return [None] * len(rows), NO_TOP_CUT
    bracket = [(_count(row.get("winsBracket")), _count(row.get("lossesBracket"))) for row in rows]
    records = [(won, lost) for won, lost in bracket if won is not None and lost is not None]
    if rows and len(records) == len(bracket):
        return [won + lost > 0 for won, lost in records], BRACKET_RECORD
    # Without bracket columns, the response order is read as the final standings. That
    # is undocumented, so it is used only if no player below the cut has more wins
    # than a player inside it.
    wins = [won for row in rows if (won := _count(row.get("wins"))) is not None]
    if len(wins) != len(rows) or (
        len(rows) > size and min(wins[:size], default=0) < max(wins[size:], default=0)
    ):
        return [None] * len(rows), INCONSISTENT_ORDER
    return [position < size for position in range(len(rows))], STANDING_ORDER


def _oracle_id(value: object) -> str | None:
    # TopDeck card ids are Scryfall oracle ids; anything else cannot be joined to a card.
    try:
        return str(UUID(value)) if isinstance(value, str) else None
    except ValueError:
        return None


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
    commander_zones = [zone for zone in deck if zone.lower() in COMMANDER_ZONES]
    # One entry per oracle id: [first name seen, mainboard copies, sideboard copies].
    copies: dict[str, list[Any]] = {}
    commanders: set[str] = set()
    skipped = [0, 0]
    zones = [(0, MAINBOARD)] + [(0, zone) for zone in commander_zones] + [(1, "Sideboard")]
    for slot, zone in zones:
        for name, line in (deck.get(zone) or {}).items():
            oracle_id = _oracle_id((line or {}).get("id"))
            count = (line or {}).get("count")
            if oracle_id is None or not isinstance(count, int) or count <= 0:
                skipped[slot] += 1
                continue
            oracle_id = intern(oracle_id)
            entry = copies.setdefault(oracle_id, [intern(name), 0, 0])
            entry[1 + slot] += count
            if zone in commander_zones:
                commanders.add(oracle_id)
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
        commanders=tuple(sorted(commanders)) if len(commanders) <= MAX_COMMANDERS else (),
    )
    return entry, skipped[0], skipped[1]
