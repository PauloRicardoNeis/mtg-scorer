"""Offline adapter for saved Wizards event-coverage pages.

From about 2004 to 2010 Wizards published every player's decklist and every round's
results for constructed Pro Tours; the pages survive only in the Internet Archive.
``scripts/probe_wizards_coverage.py`` saves one event's decklist, round-results and
final-standings pages next to a ``manifest.json`` that lists each file with its
SHA-256 and names the event: its coverage code, format, first day and the rounds
played in that format. Each file is verified against the manifest before it is
parsed. Nothing here calls the network: card names are resolved by a function the
caller passes, usually :func:`catalog_resolver` over the local catalog database.

Decklists name players "First Last" and the standings "Last, First [CTRY]", so each
deck is joined to its standing by name (:func:`join_names`). A deck's record counts
only the rounds played in the event's constructed format, and only when every one of
those rounds was archived.
"""

from __future__ import annotations

import difflib
import html
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from sys import intern
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
from ..normalize.names import name_key
from .topdeck import STANDING_ORDER, UNKNOWN_TOP_CUT, RawFile, _coverage, _retrieval

SOURCE = "wizards-coverage"
PARSER_VERSION = "wizards-coverage-v1"
ATTRIBUTION = (
    "Pro Tour coverage published by Wizards of the Coast (wizards.com), "
    "read from the Internet Archive's Wayback Machine (https://web.archive.org)"
)
# Every Pro Tour of the era cut to a top 8 after the Swiss rounds.
TOP_CUT = 8
RESULT_PAGE = re.compile(r"res(\d+)[a-z]?")
STANDINGS_PAGE = "standfin"
OUTCOME = re.compile(r"^(Won|Lost|Drew)\s+(\d+-\d+(?:-\d+)?)$", re.I)
COUNTRY = re.compile(r"\s*\[[A-Z]{2,3}\]\s*$")
BYE = re.compile(r"\bbye\b", re.I)
# Some pages name the deck in the player's header: "First Last - Deck Name".
# Names hold hyphens ("Al-Bacha") but no en or em dashes.
DECK_IN_HEADER = re.compile(r"\s*[–—]\s*|\s+-\s+")
# Top-8 decklist pages; "top8bdd" lists booster draft decks and stays out.
TOP8_DECKS = re.compile(r"(?:t8|top8)(?:decks|decklists|bcd)")
# The decks with the best constructed records ("Top Extended Deck Lists").
TOP_RECORD_DECKS = re.compile(r"tedecks|(?:f-)?top(?:std|ext|block)\w*")
EVENT_CAPTION = re.compile(r"pro\s*tour", re.I)
# "<p class="decktitle">Sideboard</p>", with "<i>" around the word on 2010 pages.
SIDEBOARD_TITLE = re.compile(r'class="decktitle">(?:\s|<[^>]+>)*Sideboard', re.I)
# Suffixes are written inconsistently ("Zampere Junior, Celso" in the standings,
# "Celso Zampere, Jr." on the decklist), so names are compared without them.
NAME_SUFFIX = re.compile(r",?\s+(?:jr|sr|junior|ii|iii|iv)\.?(?=\s*(?:,|$))", re.I)
# Layouts no constructed deck lists; a product's front card ("Savage Lands", 2026)
# shares its name with the land.
NOT_PLAYABLE = (
    "art_series",
    "double_faced_token",
    "emblem",
    "front_card",
    "planar",
    "scheme",
    "token",
    "vanguard",
)
# Misspellings in the original coverage, mapped to the printed card name. Each target
# was checked against its deck and printed before the event: "Goblin Incinerator" sits
# in a sideboard beside three main deck Gempalm Incinerators, "Recap" in a Burning Wish
# sideboard, and "Frostlang" in a red deck while fourteen other decks list Frostling.
# Spellings that differ only in punctuation or spacing need no entry (see match_names).
CARD_ALIASES = {
    "Adaker Wastes": "Adarkar Wastes",
    "Bird of Paradise": "Birds of Paradise",
    "Caves of Kolios": "Caves of Koilos",
    "Circle or Protection: Red": "Circle of Protection: Red",
    "Drift of Phantoms": "Drift of Phantasms",
    "Elf of Deep Shadow": "Elves of Deep Shadow",
    "Frostlang": "Frostling",
    "Gave-Shell Scarab": "Grave-Shell Scarab",
    "Genju of the Realms": "Genju of the Realm",
    "Ghost Council of Orzhov": "Ghost Council of Orzhova",
    "Ghostly Demise": "Ghastly Demise",
    "Goblin Incinerator": "Gempalm Incinerator",
    "Guerilla Tactics": "Guerrilla Tactics",
    "Hokari, Dust Drinker": "Hokori, Dust Drinker",
    "Ink-Eyes Servant of the Oni": "Ink-Eyes, Servant of Oni",
    "Keldon Necroplis": "Keldon Necropolis",
    "Last Grasp": "Last Gasp",
    "Meloku, The Cloud Mirror": "Meloku the Clouded Mirror",
    "Mikokoro, Centre of the Sea": "Mikokoro, Center of the Sea",
    "Mokokoro, Center of the Sea": "Mikokoro, Center of the Sea",
    "Mortified": "Mortify",
    "Ninja of Deep Hours": "Ninja of the Deep Hours",
    "Orzhov, the Church of Deals": "Orzhova, the Church of Deals",
    "Ravaged Highland": "Ravaged Highlands",
    "Recap": "Recoup",
    "Ribbons of the Night": "Ribbons of Night",
    "Ringleader Goblin": "Goblin Ringleader",
    "Savannah Lion": "Savannah Lions",
    "Scorching Rusalka": "Scorched Rusalka",
    "Stich Together": "Stitch Together",
    "Stomping Grounds": "Stomping Ground",
    "Sulfurous Spring": "Sulfurous Springs",
}
# The join's last pass pairs a deck and a player whose surnames are at least this
# similar and whose first names agree, or whose surname is the same when neither has
# any other candidate.
SURNAME_SIMILARITY = 0.8
FIRST_NAME_SIMILARITY = 0.6
# Short forms of given names that are not a prefix of the full name ("Dan", "Chris"
# and "Steve" are).
NICKNAMES = {
    "andy": "andrew",
    "bill": "william",
    "billy": "william",
    "bob": "robert",
    "bobby": "robert",
    "chuck": "charles",
    "dick": "richard",
    "gabe": "gabriel",
    "jim": "james",
    "jimmy": "james",
    "joe": "joseph",
    "mike": "michael",
    "rick": "richard",
    "ted": "edward",
    "tom": "thomas",
    "tommy": "thomas",
    "tony": "anthony",
}


@dataclass(frozen=True, slots=True)
class NameResolution:
    """Card names resolved against one catalog snapshot: each name's
    ``(oracle_id, catalog name)`` matches; one match resolves it, none or several do not."""

    catalog_snapshot_id: str
    matches: Mapping[str, tuple[tuple[str, str], ...]]


Resolver = Callable[[Collection[str]], NameResolution]


@dataclass(frozen=True, slots=True)
class WizardsSnapshot:
    """Facts parsed from one verified directory of saved coverage pages, in the shape
    ``publish.score_run`` reads from a TopDeck snapshot."""

    dataset_snapshot_id: str
    raw_files: tuple[RawFile, ...]
    tournaments: tuple[Tournament, ...]
    decks: tuple[DeckEntry, ...]
    standings: tuple[Standing, ...]
    top_cut_basis: Mapping[str, str]
    quarantined_card_lines: int
    # Decks with an unresolved main deck card; their card usage is not complete.
    incomplete_mainboards: frozenset[str]
    team_events_skipped: int = 0
    # How the decks were joined to the standings, and the card names left unresolved.
    join_methods: Mapping[str, int] = field(default_factory=dict)
    unresolved_names: tuple[str, ...] = ()


# --- Pages ---------------------------------------------------------------------------


def decode_page(payload: bytes) -> str:
    """The pages declare no reliable charset: most are UTF-8, some Windows-1252."""

    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload.decode("cp1252", "replace")


def page_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def card_name(value: str) -> str:
    """The printed name: typos corrected, split cards written "Fire // Ice" (older lists
    wrote "Fire/Ice") and the "Æ" ligature spelled out as the catalog spells it."""

    value = value.replace("Æ", "Ae").replace("æ", "ae")
    if "/" in value and "//" not in value:
        value = re.sub(r"\s*/\s*", " // ", value)
    return CARD_ALIASES.get(value, value)


def deck_blocks(page: str) -> list[tuple[str, str | None, str]]:
    """Each deck as (player, deck name, markup). Pages captured from 2009 use div.deck;
    earlier captures keep the original table layout with a large-font player header."""

    if '<div class="deck">' in page:
        blocks = []
        for chunk in page.split('<div class="deck">')[1:]:
            player = re.search(r"<heading>(.*?)</heading>", chunk, re.S)
            label = re.search(r'<div class="sub">(.*?)</div>', chunk, re.S)
            if player:
                blocks.append((player.group(1), label.group(1) if label else None, chunk))
        return blocks
    heads = list(
        re.finditer(r'<font size="\+1">(.*?)</font>\s*</b>\s*<br\s*/?>(.*?)</p>', page, re.S)
    )
    if not heads:
        return []
    ends = [head.start() for head in heads[1:]] + [len(page)]
    return [
        (head.group(1), head.group(2), page[head.end() : end])
        for head, end in zip(heads, ends, strict=True)
    ]


def parse_decks(page: str) -> list[dict[str, Any]]:
    """Every deck on a decklist page: player, deck name, main deck and sideboard."""

    decks = []
    for player, label, chunk in deck_blocks(page):
        zones: dict[str, Counter[str]] = {"main": Counter(), "side": Counter()}
        body = re.sub(
            r'<span class="decktotals">.*?</span>|<p class="cardcount">.*?</p>',
            "",
            chunk,
            flags=re.S,
        )
        side_at = SIDEBOARD_TITLE.search(body)
        for cell in re.finditer(r'(<td[^>]*valign="top"[^>]*>)(.*?)</td>', body, re.S):
            # The table layout shades its sideboard column with its own background; 2009
            # pages give the sideboard its own column, 2010 pages start it mid-column.
            after_title = side_at and cell.start() > side_at.start()
            zone = "side" if after_title or "statback" in cell.group(1) else "main"
            content = cell.group(2)
            inner = SIDEBOARD_TITLE.search(content)
            before, after = (
                (content[: inner.start()], content[inner.end() :]) if inner else (content, "")
            )
            for part_zone, part in ((zone, before), ("side", after)):
                for line in re.split(r"<br\s*/?>", part):
                    found = re.match(r"^(\d+)\s+(.+)$", page_text(line))
                    if found and int(found.group(1)) > 0:
                        zones[part_zone][card_name(found.group(2))] += int(found.group(1))
        if not zones["main"]:
            # A heading without cards, such as a page title in the deck layout.
            continue
        name, *named = DECK_IN_HEADER.split(page_text(player), maxsplit=1)
        caption = (page_text(label) if label else "") or "".join(named)
        decks.append(
            {
                "player": name,
                # 2009 pages caption every deck with the event ("Pro Tour-Austin 2009,
                # Extended"), which names no archetype.
                "label": None if not caption or EVENT_CAPTION.search(caption) else caption,
                **zones,
            }
        )
    return decks


def parse_results(page: str) -> tuple[list[tuple[str, str, str]], list[str], int]:
    """Matches as (player, outcome, opponent), players with a bye, and unread rows."""

    matches, byes, unread = [], [], 0
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = [page_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        result = OUTCOME.match(cells[2])
        # A bye can be written as a won match against "BYE"; a player is never one.
        if any(BYE.search(cell) for cell in cells[2:]):
            byes.append(cells[1])
        elif result and len(cells) >= 5 and cells[4]:
            matches.append((cells[1], result.group(1).lower(), cells[4]))
        else:
            unread += 1
    return matches, byes, unread


def parse_standings(page: str) -> list[tuple[int, str]]:
    """Final standings as (rank, "Last, First [CTRY]")."""

    ranks = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = [page_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) >= 2 and cells[0].isdigit() and COUNTRY.search(cells[1]):
            ranks.append((int(cells[0]), cells[1]))
    return ranks


def deck_pages(slugs: Iterable[str]) -> list[str]:
    """The pages listing the whole field's decks: alphabetical pages, then the best
    records, then the top 8. A deck listed twice is read once, from its first page.

    Most events split the field alphabetically ("afdecks", "alldecksad", "decksae");
    other deck pages ("extendeddecks", "legacydecks") belong to side events. Without
    such pages, every decklist page is read except deck techs and sample hands. The
    2009–10 Pro Tours left the players with the best constructed records out of the
    alphabetical pages and listed them apart (Austin's "tedecks", San Diego's
    "topstddecks", Honolulu's "f-topblock"), and Austin and San Diego did the same
    with the top 8.
    """

    slugs = sorted(set(slugs))
    ranges = []
    for slug in slugs:
        found = re.fullmatch(r"(?:all)?decks([a-z])([a-z])|([a-z])([a-z])decks", slug)
        if found and (found.group(1) or found.group(3)) <= (found.group(2) or found.group(4)):
            ranges.append(slug)
    field = ranges or [
        slug
        for slug in slugs
        if "deck" in slug and not re.search(r"tech|sample", slug) and not re.match(r"t8|top8", slug)
    ]
    return (
        field
        + [slug for slug in slugs if TOP_RECORD_DECKS.fullmatch(slug) and slug not in field]
        + [slug for slug in slugs if TOP8_DECKS.fullmatch(slug)]
    )


def result_round(slug: str) -> int | None:
    """The round a results page reports ("res3" and "res3a" are round 3), if any."""

    found = RESULT_PAGE.fullmatch(slug)
    return int(found.group(1)) if found else None


# --- Players -------------------------------------------------------------------------


def _fold(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()


def name_parts(value: str) -> tuple[list[str], list[str]]:
    """(first names, surnames) as lowercase ASCII tokens, from "First Last" or
    "Last, First [CTRY]", without a "Jr." suffix."""

    value = NAME_SUFFIX.sub("", COUNTRY.sub("", value).strip())
    if "," in value:
        last, _, first = value.partition(",")
    else:
        first, _, last = value.partition(" ")

    def tokens(part: str) -> list[str]:
        return re.sub(r"[^a-z0-9]+", " ", _fold(part).lower()).split()

    return tokens(first), tokens(last)


def name_tokens(value: str) -> list[str]:
    first, last = name_parts(value)
    return first + last


def _romanized(token: str) -> str:
    # Japanese long vowels are written "Oodan", "Ohdan" or "Odan" and German umlauts
    # "ue" or "u"; those spellings compare equal.
    for long, short in (("ou", "o"), ("oo", "o"), ("oh", "o"), ("uu", "u"), ("ue", "u")):
        token = token.replace(long, short)
    return token


def _similarity(a: str, b: str) -> float:
    a, b = _romanized(a), _romanized(b)
    return 1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()


def join_names(decks: list[str], players: list[str]) -> tuple[dict[str, str], Counter[str]]:
    """Each deck's player in the standings, joined in passes over the names still left:
    the same tokens, then truncated tokens (standings cut long names), then surname and
    first initial, then spellings that differ (:func:`_similar_names`). A pass keeps
    only matches that are unique among the names left."""

    keys = {player: name_tokens(player) for player in players}
    joined: dict[str, str] = {}
    how: Counter[str] = Counter()

    def same(deck: list[str], player: list[str]) -> bool:
        return sorted(deck) == sorted(player)

    def truncated(deck: list[str], player: list[str]) -> bool:
        return len(player) <= len(deck) and all(
            any(d.startswith(p) or p.startswith(d) for d in deck) for p in player
        )

    def surname_initial(deck: list[str], player: list[str]) -> bool:
        return len(deck) >= 2 and player[-1] == deck[-1] and player[0][:1] == deck[0][:1]

    for method, rule in (
        ("exact", same),
        ("truncated", truncated),
        ("surname_initial", surname_initial),
    ):
        left = [p for p in players if p not in joined.values() and keys[p]]
        for deck in [d for d in decks if d not in joined]:
            tokens = name_tokens(deck)
            found = [p for p in left if rule(tokens, keys[p])]
            if len(found) == 1 and found[0] not in joined.values():
                joined[deck] = found[0]
                how[method] += 1
    similar = _similar_names(
        [d for d in decks if d not in joined], [p for p in players if p not in joined.values()]
    )
    joined.update(similar)
    how["similar"] += len(similar)
    how["unmatched"] += len(decks) - len(joined)
    return joined, +how


def _similar_names(decks: list[str], players: list[str]) -> dict[str, str]:
    """Decks and players that are each other's single best candidate, scored by surname
    and first-name similarity."""

    score: dict[tuple[str, str], tuple[float, float]] = {}
    for deck in decks:
        for player in players:
            pair = _name_similarity(deck, player)
            if pair[0] >= SURNAME_SIMILARITY:
                score[deck, player] = pair

    def best(candidates: list[tuple[str, str]]) -> tuple[str, str] | None:
        ranked = sorted(candidates, key=lambda pair: sum(score[pair]), reverse=True)
        if len(ranked) > 1 and sum(score[ranked[0]]) == sum(score[ranked[1]]):
            return None
        return ranked[0] if ranked else None

    joined = {}
    for deck in decks:
        pair = best([pair for pair in score if pair[0] == deck])
        if pair is None or best([other for other in score if other[1] == pair[1]]) != pair:
            continue
        surname, given = score[pair]
        alone = all(
            other == pair or (pair[0] not in other and pair[1] not in other) for other in score
        )
        if given >= FIRST_NAME_SIMILARITY or (surname == 1.0 and alone):
            joined[deck] = pair[1]
    return joined


def _name_similarity(deck: str, player: str) -> tuple[float, float]:
    """(surname, first name) similarity of a decklist name and a standings name.

    The deck's first name may be any of the player's given names ("Bryant Malig" is
    "Malig, J. Bryant"), a surname may be written in one word or two ("DeRosa"), and
    some decklists put the surname first ("Shimada Masataki").
    """

    first, last = name_parts(player)
    tokens = [token for part in name_parts(deck) for token in part]

    def oriented(given: list[str], surname: list[str]) -> tuple[float, float]:
        if not given or not surname or not last:
            return 0.0, 0.0
        return (
            max(_similarity(a, b) for a in _joined(surname) for b in _joined(last)),
            max((_given_similarity(given[0], b) for b in first), default=0.0),
        )

    return max(oriented(tokens[:1], tokens[1:]), oriented(tokens[-1:], tokens[:-1]), key=sum)


def _joined(tokens: list[str]) -> list[str]:
    return [*tokens, "".join(tokens)] if len(tokens) > 1 else tokens


def _given_similarity(a: str, b: str) -> float:
    a, b = NICKNAMES.get(a, a), NICKNAMES.get(b, b)
    return 1.0 if a.startswith(b) or b.startswith(a) else _similarity(a, b)


def records(rounds: Mapping[int, list[tuple[str, str, str]]]) -> dict[str, Counter[str]]:
    """Each player's won, lost and drew matches; a match listed twice counts once."""

    flip = {"won": "lost", "lost": "won", "drew": "drew"}
    record: dict[str, Counter[str]] = {}
    for matches in rounds.values():
        seen: set[frozenset[str]] = set()
        for player, outcome, opponent in matches:
            if frozenset((player, opponent)) in seen:
                continue
            seen.add(frozenset((player, opponent)))
            record.setdefault(player, Counter())[outcome] += 1
            record.setdefault(opponent, Counter())[flip[outcome]] += 1
    return record


def _standings_spellings(
    rounds: Mapping[int, tuple[list[tuple[str, str, str]], list[str], int]], players: list[str]
) -> Callable[[str], str]:
    """Each results name as the standings spell it.

    Early results pages sometimes list a player under another spelling, often the
    default country ("Dean, J. Evan W [USA]" before "[CAN]"), which would split the
    player's record in two. A results name missing from the standings is read as the
    player it joins (:func:`join_names`), unless both names played in the same round.
    """

    played: dict[str, set[int]] = {}
    for number, (matches, byes, _) in rounds.items():
        for name in [n for a, _, b in matches for n in (a, b)] + byes:
            played.setdefault(name, set()).add(number)
    same: dict[str, str] = {}
    for name in sorted(set(played) - set(players)):
        player = join_names([name], players)[0].get(name)
        if player is not None and not played[name] & played.setdefault(player, set()):
            same[name] = player
            played[player] |= played[name]
    return lambda name: same.get(name, name)


# --- Card names ----------------------------------------------------------------------


def catalog_resolver(dsn: str) -> Resolver:
    """Resolve names against the active snapshot of a local catalog database."""

    def resolve(names: Collection[str]) -> NameResolution:
        import psycopg

        with psycopg.connect(dsn) as connection:
            active = connection.execute(
                "SELECT catalog_snapshot_id FROM catalog.active_catalog"
            ).fetchone()
            if active is None:
                raise ValueError("the catalog has no active snapshot to resolve names against")
            (snapshot,) = active
            rows = connection.execute(
                "SELECT a.alias_key, a.kind, a.oracle_id::text, c.name "
                "FROM catalog.catalog_alias a "
                "JOIN catalog.catalog_card c USING (catalog_snapshot_id, oracle_id) "
                "WHERE a.catalog_snapshot_id = %s AND c.layout <> ALL(%s)",
                (snapshot, list(NOT_PLAYABLE)),
            ).fetchall()
        return NameResolution(snapshot, match_names(names, rows))

    return resolve


def match_names(
    names: Collection[str], aliases: Iterable[tuple[str, str, str, str]]
) -> dict[str, tuple[tuple[str, str], ...]]:
    """Each name's matches among ``(alias_key, kind, oracle_id, catalog name)`` rows: an
    exact canonical name first, else an exact face name; then the same without accents
    ("Lim-Dul's Vault" is "Lim-Dûl's Vault"); then without punctuation, spaces or case
    ("Watch Wolf" is "Watchwolf", "Yukora The Prisoner" is "Yukora, the Prisoner")."""

    keys = (name_key, lambda key: _fold(name_key(key)), _loose)
    index: list[dict[str, dict[str, set[tuple[str, str]]]]] = [{} for _ in keys]
    for key, kind, oracle_id, name in aliases:
        for found, normalize in zip(index, keys, strict=True):
            found.setdefault(normalize(key), {}).setdefault(kind, set()).add((oracle_id, name))

    def pick(name: str) -> tuple[tuple[str, str], ...]:
        for found, normalize in zip(index, keys, strict=True):
            kinds = found.get(normalize(name), {})
            if kinds:
                return tuple(sorted(kinds.get("canonical") or kinds["face"]))
        return ()

    return {name: pick(name) for name in names}


def _loose(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _fold(name_key(value)))


# --- Snapshot ------------------------------------------------------------------------


def read_saved_pages(directory: Path, resolver: Resolver) -> WizardsSnapshot:
    """Verify and parse every page listed in ``manifest.json`` into one event's facts."""

    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    event = manifest.get("event")
    if event is None:
        # Probes written before the manifest named the event kept it in the summary.
        event = json.loads((directory / "summary.json").read_text(encoding="utf-8"))["event"]
    raw_files: list[RawFile] = []
    pages: dict[str, tuple[str, RawFile]] = {}
    for request in manifest["requests"]:
        path = directory / request["raw_file"]
        payload = path.read_bytes()
        digest = sha256(payload).hexdigest()
        if digest != request["sha256"]:
            raise ValueError(f"{request['raw_file']} does not match its manifest SHA-256")
        raw = RawFile(request["raw_file"], digest, len(payload), *_retrieval(request, path))
        raw_files.append(raw)
        page = re.fullmatch(r"page-(.+)\.html", raw.name)
        if page:
            pages[page.group(1)] = (decode_page(payload), raw)
    if not pages:
        raise ValueError(f"{directory} holds no saved coverage pages")
    facts = _event_facts(event, pages, resolver, directory)
    identity = sha256(
        json.dumps(
            {
                "source": SOURCE,
                "parser_version": PARSER_VERSION,
                "event": event,
                # Corrected card names change the facts as much as the pages do.
                "card_aliases": sorted(CARD_ALIASES.items()),
                "not_playable_layouts": NOT_PLAYABLE,
                "catalog_snapshot_id": facts.catalog_snapshot_id,
                "files": sorted([raw.name, raw.sha256] for raw in raw_files),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return WizardsSnapshot(
        dataset_snapshot_id=f"wizards-{identity}",
        raw_files=tuple(raw_files),
        tournaments=(facts.tournament,),
        decks=facts.decks,
        standings=facts.standings,
        top_cut_basis={facts.tournament.source_event_id: facts.top_cut_basis},
        quarantined_card_lines=facts.quarantined,
        incomplete_mainboards=facts.incomplete,
        join_methods=facts.join_methods,
        unresolved_names=facts.unresolved,
    )


def read_saved_events(directories: Iterable[Path], resolver: Resolver) -> WizardsSnapshot:
    """Several saved events as one snapshot, so a cohort can span a format season.

    One directory reads as :func:`read_saved_pages`. With more, each raw file is named
    after its directory, and the dataset id hashes the events' own dataset ids.
    """

    directories = list(directories)
    snapshots = [read_saved_pages(directory, resolver) for directory in directories]
    events = Counter(t.source_event_id for s in snapshots for t in s.tournaments)
    if twice := sorted(event for event, count in events.items() if count > 1):
        raise ValueError(f"events saved more than once: {', '.join(twice)}")
    if len(snapshots) == 1:
        return snapshots[0]
    identity = sha256(
        json.dumps(sorted(s.dataset_snapshot_id for s in snapshots)).encode()
    ).hexdigest()
    return WizardsSnapshot(
        dataset_snapshot_id=f"wizards-{identity}",
        raw_files=tuple(
            replace(raw, name=f"{directory.name}/{raw.name}")
            for directory, snapshot in zip(directories, snapshots, strict=True)
            for raw in snapshot.raw_files
        ),
        tournaments=tuple(t for s in snapshots for t in s.tournaments),
        decks=tuple(d for s in snapshots for d in s.decks),
        standings=tuple(t for s in snapshots for t in s.standings),
        top_cut_basis={k: v for s in snapshots for k, v in s.top_cut_basis.items()},
        quarantined_card_lines=sum(s.quarantined_card_lines for s in snapshots),
        incomplete_mainboards=frozenset().union(*(s.incomplete_mainboards for s in snapshots)),
        join_methods=dict(sum((Counter(s.join_methods) for s in snapshots), Counter())),
        unresolved_names=tuple(sorted({n for s in snapshots for n in s.unresolved_names})),
    )


@dataclass(frozen=True, slots=True)
class _EventFacts:
    tournament: Tournament
    decks: tuple[DeckEntry, ...]
    standings: tuple[Standing, ...]
    top_cut_basis: str
    quarantined: int
    incomplete: frozenset[str]
    catalog_snapshot_id: str
    join_methods: dict[str, int]
    unresolved: tuple[str, ...]


def _event_facts(
    event: Mapping[str, Any],
    pages: Mapping[str, tuple[str, RawFile]],
    resolver: Resolver,
    directory: Path,
) -> _EventFacts:
    event_id = event["code"].rsplit("/", 1)[-1]
    parsed: dict[str, tuple[dict[str, Any], RawFile]] = {}
    for slug in deck_pages(pages):
        text, raw = pages[slug]
        for deck in parse_decks(text):
            # A player listed on two pages registered one deck.
            parsed.setdefault(" ".join(name_tokens(deck["player"])), (deck, raw))

    # Only the rounds played in the event's constructed format count.
    wanted = event.get("constructed_rounds")
    by_round = {number: slug for slug in pages if (number := result_round(slug)) is not None}
    expected = (
        sorted(wanted) if wanted is not None else list(range(1, max(by_round, default=0) + 1))
    )
    rounds = {
        number: parse_results(pages[by_round[number]][0])
        for number in expected
        if number in by_round
    }
    complete = bool(rounds) and len(rounds) == len(expected)
    rank_of = {
        name: rank
        for rank, name in (
            parse_standings(pages[STANDINGS_PAGE][0]) if STANDINGS_PAGE in pages else []
        )
    }
    spelling = _standings_spellings(rounds, list(rank_of))
    record = records(
        {
            number: [(spelling(a), outcome, spelling(b)) for a, outcome, b in matches]
            for number, (matches, _, _) in rounds.items()
        }
    )
    byes = Counter(
        spelling(player) for _, round_byes, _ in rounds.values() for player in round_byes
    )
    # Players in the results but not the final standings played too; without final
    # standings, the players are the names in the results.
    roster = list(rank_of) + sorted((set(record) | set(byes)) - set(rank_of))
    joined, join_methods = join_names([deck["player"] for deck, _ in parsed.values()], roster)
    top_cut_basis = (
        STANDING_ORDER
        if sum(rank <= TOP_CUT for rank in rank_of.values()) == TOP_CUT
        else UNKNOWN_TOP_CUT
    )

    names = {
        card for deck, _ in parsed.values() for zone in ("main", "side") for card in deck[zone]
    }
    resolution = resolver(names)
    resolved = {name: found[0] for name, found in resolution.matches.items() if len(found) == 1}
    decks: list[DeckEntry] = []
    standings: list[Standing] = []
    quarantined = 0
    incomplete: set[str] = set()
    for index, (deck, raw) in enumerate(parsed.values(), start=1):
        deck_id = f"{event_id}#{index}"
        provenance = _provenance(deck_id, raw, directory)
        entry, skipped_main, skipped_side = _deck(deck, event_id, provenance, resolved)
        decks.append(entry)
        quarantined += skipped_main + skipped_side
        if skipped_main:
            incomplete.add(deck_id)
        if deck["player"] not in joined:
            continue
        player = joined[deck["player"]]
        rank = rank_of.get(player)
        result = record.get(player, Counter())
        standings.append(
            Standing(
                provenance=provenance,
                source_event_id=event_id,
                source_deck_id=deck_id,
                final_rank=rank,
                wins=result["won"] if complete else None,
                losses=result["lost"] if complete else None,
                draws=result["drew"] if complete else None,
                byes=byes[player] if complete else None,
                made_top_cut=(
                    rank <= TOP_CUT
                    if rank is not None and top_cut_basis == STANDING_ORDER
                    else None
                ),
            )
        )

    players = len(roster)
    event_page = STANDINGS_PAGE if STANDINGS_PAGE in pages else min(pages)
    tournament = Tournament(
        provenance=_provenance(event_id, pages[event_page][1], directory),
        occurred_on=date.fromisoformat(event["date"]),
        format_name=event["format"],
        source_format_name=event["format"],
        player_count=players or None,
        top_cut_size=TOP_CUT if top_cut_basis == STANDING_ORDER else None,
        coverage=CoverageProfile(
            # A deck page can list a player the standings lost; coverage cannot exceed 1.
            decklists=_coverage(min(len(decks), players), players),
            standings=_coverage(len(rank_of), players),
            matches=_coverage(len(rounds), len(expected))
            if expected
            else CoverageDimension(CoverageScope.NONE, 0),
        ),
    )
    return _EventFacts(
        tournament=tournament,
        decks=tuple(decks),
        standings=tuple(standings),
        top_cut_basis=top_cut_basis,
        quarantined=quarantined,
        incomplete=frozenset(incomplete),
        catalog_snapshot_id=resolution.catalog_snapshot_id,
        join_methods=dict(join_methods),
        unresolved=tuple(sorted(name for name in names if name not in resolved)),
    )


def _provenance(record_id: str, raw: RawFile, directory: Path) -> Provenance:
    return Provenance(
        source=SOURCE,
        source_record_id=record_id,
        retrieved_at=raw.retrieved_at,
        parser_version=PARSER_VERSION,
        raw_snapshot_ref=intern(f"{directory.name}/{raw.name}"),
    )


def _deck(
    deck: Mapping[str, Any],
    event_id: str,
    provenance: Provenance,
    resolved: Mapping[str, tuple[str, str]],
) -> tuple[DeckEntry, int, int]:
    """The deck by oracle id, plus how many main deck and sideboard lines stayed
    unresolved. Two spellings of one card are one entry under the catalog's name."""

    copies: dict[str, list[Any]] = {}
    skipped = [0, 0]
    for slot, zone in enumerate(("main", "side")):
        for name, count in deck[zone].items():
            if name not in resolved:
                skipped[slot] += 1
                continue
            oracle_id, catalog_name = resolved[name]
            entry = copies.setdefault(intern(oracle_id), [intern(catalog_name), 0, 0])
            entry[1 + slot] += count
    entry = DeckEntry(
        provenance=provenance,
        source_event_id=event_id,
        cards=tuple(
            DeckCard(oracle_id, name, mainboard_count=main, sideboard_count=side)
            for oracle_id, (name, main, side) in copies.items()
        ),
        # An empty or partly unresolved sideboard was not fully observed.
        sideboard_observed=bool(deck["side"]) and not skipped[1],
        archetype_label=deck["label"],
    )
    return entry, skipped[0], skipped[1]
