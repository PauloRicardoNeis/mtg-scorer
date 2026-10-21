"""Bounded, opt-in MTGTop8 probe for one format and date window; never used by CI.

MTGTop8 keeps the top of each event (usually the top 8) with placings, but no match
records. The probe reads every search page of the window to count events, decks and
placing patterns, then saves the event pages and MTGO-format lists of the earliest
events that fit the caps. It prints only aggregate coverage and a preview of a
separate Top 8 score: how often a card reaches top 8s, and the playoff record its decks
earned, inferred from single-elimination placings. No player names are kept in the
summary.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mtg_scorer.ingest.wizards import card_name
from probe_tournaments import resolution

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://www.mtgtop8.com"
USER_AGENT = "mtg-scorer/0.3 feasibility (+https://github.com/PauloRicardoNeis/mtg-scorer)"
SEARCH_ROW = re.compile(r"<tr class=hover_tr>(.*?)</tr>", re.S | re.I)
EVENT_ENTRY = re.compile(
    r"class=(?:chosen_tr|hover_tr)[^>]*>.*?class=S14>([^<]+)</div>.*?"
    r"\?e=(\d+)&d=(\d+)&f=\w+>([^<]*)</a>",
    re.S,
)
PLAYERS = re.compile(r"(\d+) players\s*-\s*(\d\d)/(\d\d)/(\d\d)")
# Matches won and lost in a single-elimination playoff, by finishing place.
PLAYOFF = {
    8: {"1": (3, 0), "2": (2, 1), "3-4": (1, 1), "5-8": (0, 1)},
    4: {"1": (2, 0), "2": (1, 1), "3-4": (0, 1)},
}
BRACKET = {
    8: ["1", "2", "3-4", "3-4", "5-8", "5-8", "5-8", "5-8"],
    4: ["1", "2", "3-4", "3-4"],
}
# Playoff matches of field-average (50%) evidence added to every card's record.
PRIOR_MATCHES = 10


class Site:
    """Two seconds between requests; 429 and 5xx responses are retried with a backoff."""

    def __init__(self, output: Path) -> None:
        self.output = output
        self.records: list[dict] = []

    def get(self, path: str, filename: str, form: dict | None = None) -> str:
        saved = self.output / filename
        if saved.exists():
            payload = saved.read_bytes()
            self.records.append(
                {
                    "path": path,
                    "form": form,
                    "reused": True,
                    "raw_file": filename,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
            return payload.decode("latin-1" if filename.endswith(".txt") else "utf-8", "replace")
        data = None if form is None else urlencode(form).encode()
        payload, status = b"", 0
        for attempt in range(4):
            time.sleep(2)
            try:
                request = Request(SITE + path, data=data, headers={"User-Agent": USER_AGENT})
                with urlopen(request, timeout=60) as r:
                    payload = r.read(5_000_001)
                    status = r.status
                break
            except HTTPError as error:
                if (error.code == 429 or error.code >= 500) and attempt < 3:
                    time.sleep(15 * (attempt + 1))
                    continue
                raise SystemExit(f"{path} failed: HTTP {error.code}") from None
            except (URLError, TimeoutError) as error:
                if attempt < 3:
                    time.sleep(15 * (attempt + 1))
                    continue
                raise SystemExit(f"{path} failed: {getattr(error, 'reason', error)}") from None
        if len(payload) > 5_000_000:
            raise SystemExit(f"{path} exceeds the 5,000,000-byte probe limit")
        saved.write_bytes(payload)
        self.records.append(
            {
                "path": path,
                "form": form,
                "http_status": status,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "raw_file": filename,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        # Deck exports are served as ISO-8859-1 text; pages are UTF-8.
        return payload.decode("latin-1" if filename.endswith(".txt") else "utf-8", "replace")


def text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def search(site: Site, fmt: str, start: date, end: date) -> list[dict]:
    """Every deck the search lists for the window, newest first, page by page."""
    rows, page = [], 1
    while True:
        found = site.get(
            "/search",
            f"search-{page:03d}.html",
            {
                "format": fmt,
                "date_start": start.strftime("%d/%m/%y"),
                "date_end": end.strftime("%d/%m/%y"),
                "current_page": page,
            },
        )
        total = re.search(r"(\d[\d ]*) decks? matching", re.sub(r"<[^>]+>", " ", found))
        before = len(rows)
        for row in SEARCH_ROW.findall(found):
            link = re.search(r"event\?e=(\d+)&(?:amp;)?d=(\d+)", row)
            cells = [c for c in (text(x) for x in re.split(r"<td[^>]*>", row)) if c]
            if link and len(cells) >= 3:
                rows.append(
                    {
                        "event": int(link.group(1)),
                        "deck": int(link.group(2)),
                        "rank": cells[-2],
                        "date": cells[-1],
                    }
                )
        expected = int(total.group(1).replace(" ", "")) if total else 0
        # An empty page ends the listing even if the total says more decks match.
        if len(rows) == before or len(rows) >= expected or page >= 200:
            return rows
        page += 1


def placing(ranks: list[str]) -> str:
    ordered = sorted(ranks, key=lambda r: (int(r.split("-")[0]) if r[:1].isdigit() else 99, r))
    for size, shape in BRACKET.items():
        if ordered == shape:
            return f"bracket_top{size}"
    if ordered == [str(n) for n in range(1, len(ordered) + 1)]:
        return "numbered"
    return "other"


def parse_event(page: str) -> dict:
    players = PLAYERS.search(text(page))
    entries = [
        {"rank": text(rank), "deck": int(deck), "label": text(label) or None}
        for rank, _, deck, label in EVENT_ENTRY.findall(page)
    ]
    unique = list({e["deck"]: e for e in entries}.values())
    return {
        "players": int(players.group(1)) if players else None,
        "date": f"20{players.group(4)}-{players.group(3)}-{players.group(2)}" if players else None,
        "entries": unique,
    }


def parse_list(export: str) -> dict[str, Counter]:
    zones, zone = {"main": Counter(), "side": Counter()}, "main"
    for line in export.splitlines():
        if line.strip().lower() == "sideboard":
            zone = "side"
            continue
        found = re.match(r"^\s*(\d+)\s+(.+?)\s*$", line)
        if found:
            zones[zone][card_name(found.group(2))] += int(found.group(1))
    return zones


def top8_preview(decks: list[dict]) -> dict:
    """Top-8 presence and the shrunk playoff win rate of each card's decks."""
    presence, wins, losses = Counter(), Counter(), Counter()
    for deck in decks:
        record = deck.get("playoff")
        for card in deck["main"]:
            presence[card] += 1
            if record:
                wins[card] += record[0]
                losses[card] += record[1]
    # Each playoff match gives one deck a win and another a loss.
    played = sum(sum(d["playoff"]) for d in decks if d.get("playoff")) // 2

    def shrunk(card: str) -> float:
        return (wins[card] + PRIOR_MATCHES / 2) / (wins[card] + losses[card] + PRIOR_MATCHES)

    with_record = [c for c in presence if wins[c] + losses[c]]
    return {
        "decks": len(decks),
        "decks_with_playoff_record": sum(bool(d.get("playoff")) for d in decks),
        "playoff_matches": played,
        "prior_matches": PRIOR_MATCHES,
        "most_present": [
            {"card": c, "decks": n, "share": round(n / len(decks), 4)}
            for c, n in sorted(presence.items(), key=lambda i: (-i[1], i[0]))[:10]
        ],
        "best_playoff_record": [
            {
                "card": c,
                "decks": presence[c],
                "won": wins[c],
                "lost": losses[c],
                "shrunk_win_rate": round(shrunk(c), 4),
            }
            for c in sorted(with_record, key=lambda c: (-shrunk(c), c))[:10]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", default="LE", help="MTGTop8 format code, e.g. LE, ST, EX")
    parser.add_argument("--start", default="2008-01-01", help="first day, inclusive")
    parser.add_argument("--end", default="2008-12-31", help="last day, inclusive")
    parser.add_argument("--max-events", type=int, default=3)
    parser.add_argument("--max-decks", type=int, default=100)
    parser.add_argument("--catalog-dsn", help="Local catalog database for card-name resolution")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", type=Path, help="An interrupted run's directory")
    args = parser.parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    output = args.resume or args.output or ROOT / f"analytics/data/local/mtgtop8-probe-{stamp}"
    if args.resume:
        if not output.is_dir() or (output / "summary.json").exists():
            raise SystemExit("--resume needs an interrupted run's directory without a summary.")
    else:
        output.mkdir(parents=True, exist_ok=False)
    site = Site(output)
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    rows = search(site, args.format, start, end)
    by_event: dict[int, list[dict]] = {}
    for row in rows:
        by_event.setdefault(row["event"], []).append(row)
    shapes = Counter(placing([r["rank"] for r in event]) for event in by_event.values())

    def first_seen(event: int) -> tuple[str, int]:
        day, month, year = by_event[event][0]["date"].split("/")
        return f"{year}{month}{day}", event

    # The earliest events, by date then id, not the ones with the best-looking results.
    selected, budget = [], args.max_decks
    for event in sorted(by_event, key=first_seen):
        if len(selected) == args.max_events:
            break
        if len(by_event[event]) <= budget:
            selected.append(event)
            budget -= len(by_event[event])
    events, decks, lines = [], [], []
    for event in selected:
        facts = parse_event(site.get(f"/event?e={event}&f={args.format}", f"event-{event}.html"))
        shape = placing([e["rank"] for e in facts["entries"]])
        size = int(shape.removeprefix("bracket_top")) if shape.startswith("bracket") else None
        for entry in facts["entries"]:
            zones = parse_list(site.get(f"/mtgo?d={entry['deck']}", f"deck-{entry['deck']}.txt"))
            lines.extend(zones["main"].items())
            lines.extend(zones["side"].items())
            decks.append(
                {
                    **zones,
                    "event": event,
                    "rank": entry["rank"],
                    "playoff": PLAYOFF[size].get(entry["rank"]) if size else None,
                }
            )
        events.append(
            {
                "event": event,
                "date": facts["date"],
                "players": facts["players"],
                "decks": len(facts["entries"]),
                "decklist_coverage": round(len(facts["entries"]) / facts["players"], 4)
                if facts["players"]
                else None,
                "placing": shape,
            }
        )
    summary = {
        "probe_version": "mtgtop8-v1",
        "window": {"format": args.format, "start": args.start, "end_inclusive": args.end},
        "caps": {"max_events": args.max_events, "max_decks": args.max_decks},
        "survey": {
            "decks": len(rows),
            "events": len(by_event),
            "decks_per_event": dict(sorted(Counter(len(e) for e in by_event.values()).items())),
            "placing_patterns": dict(shapes.most_common()),
        },
        "selected_events": events,
        "mainboard_sizes": dict(sorted(Counter(sum(d["main"].values()) for d in decks).items())),
        "card_resolution": resolution(lines, args.catalog_dsn),
        "top8_preview": top8_preview(decks) if decks else None,
    }
    manifest = {"probe_version": summary["probe_version"], "requests": site.records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Raw pages and summary: {output}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
