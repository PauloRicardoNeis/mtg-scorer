"""Bounded, opt-in TopDeck tournament feasibility probe; never used by normal CI.

Selects the earliest completed, non-team events in a date window (start time, then
TID) that fit a deck budget, saves the raw responses privately, and prints only
aggregate coverage: decklists, zones, card-name resolution, records and matches.
The API key comes from TOPDECK_API_KEY or the repository's ignored .env file and is
never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://topdeck.gg/api"
GAME = "Magic: The Gathering"
USER_AGENT = "mtg-scorer/0.3 feasibility (+https://github.com/PauloRicardoNeis/mtg-scorer)"
COLUMNS = [
    "name",
    "id",
    "decklist",
    "wins",
    "winsSwiss",
    "winsBracket",
    "draws",
    "losses",
    "lossesSwiss",
    "lossesBracket",
    "byes",
]
URL_ONLY = re.compile(r"^\s*https?://\S+\s*$")
TEXT_LINE = re.compile(r"^\s*(\d+)\s*x?\s+(.+?)\s*$", re.IGNORECASE)
TEXT_SECTION = re.compile(
    r"^\s*(?:~~\s*(.+?)\s*~~|(sideboard|mainboard|commanders?)\s*:?)\s*$", re.I
)


def load_key() -> str:
    key = os.environ.get("TOPDECK_API_KEY", "").strip()
    env_file = ROOT / ".env"
    if not key and env_file.is_file():
        raw = env_file.read_bytes()
        # Notepad may save UTF-16; otherwise expect UTF-8 with or without a BOM.
        text = (
            raw.decode("utf-16")
            if raw[:2] in (b"\xff\xfe", b"\xfe\xff")
            else raw.decode("utf-8-sig")
        )
        for line in text.splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip().removeprefix("export ").strip() == "TOPDECK_API_KEY":
                key = value.strip().strip("'\"")
    if not key:
        raise SystemExit("TOPDECK_API_KEY is not set in the environment or the repository .env.")
    return key


class Client:
    """One request per second at most, well under the documented 100 per minute. Bulk
    searches have a lower, unpublished limit; a 429 is waited out up to three times."""

    def __init__(self, key: str, output: Path) -> None:
        self.key = key
        self.output = output
        self.records: list[dict] = []

    def redact(self, text: str) -> str:
        return text.replace(self.key, "[REDACTED]")

    def call(self, method: str, path: str, body: dict | None, filename: str, limit: int) -> object:
        saved = self.output / filename
        if saved.exists():
            # A resumed run reuses responses already saved for this request.
            payload = saved.read_bytes()
            self.records.append(
                {
                    "method": method,
                    "url": API + path,
                    "request_body": body,
                    "reused": True,
                    "raw_file": filename,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
            return json.loads(payload)
        data = None if body is None else json.dumps(body).encode()
        headers = {
            "Authorization": self.key,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(4):
            time.sleep(1)
            try:
                with urlopen(
                    Request(API + path, data=data, method=method, headers=headers), timeout=90
                ) as r:
                    payload = r.read(limit + 1)
                    status = r.status
                break
            except HTTPError as error:
                detail = error.read(2000).decode("utf-8", "replace")
                if error.code == 429 and attempt < 3:
                    wait = min(int(error.headers.get("Retry-After") or 30), 120)
                    print(f"Rate limited on {method} {path}; waiting {wait}s.", flush=True)
                    time.sleep(wait)
                    continue
                raise SystemExit(
                    self.redact(f"{method} {path} failed: HTTP {error.code} {detail}")
                ) from None
            except URLError as error:
                raise SystemExit(self.redact(f"{method} {path} failed: {error.reason}")) from None
        if len(payload) > limit:
            raise SystemExit(f"{method} {path} response exceeds the {limit:,}-byte probe limit")
        (self.output / filename).write_bytes(payload)
        self.records.append(
            {
                "method": method,
                "url": API + path,
                "request_body": body,
                "http_status": status,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "raw_file": filename,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        return json.loads(payload)


def day(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp())


def iso(seconds: object) -> str | None:
    return (
        datetime.fromtimestamp(seconds, UTC).isoformat()
        if isinstance(seconds, int | float)
        else None
    )


def deck_lines(row: dict) -> tuple[str, dict[str, Counter]]:
    """Return how the deck was supplied and its zones as name -> copies."""
    deck_obj = row.get("deckObj")
    if isinstance(deck_obj, dict) and deck_obj:
        zones: dict[str, Counter] = {}
        for zone, cards in deck_obj.items():
            if not isinstance(cards, dict):
                continue
            counted = Counter()
            for name, value in cards.items():
                copies = value.get("count") if isinstance(value, dict) else value
                if isinstance(copies, int) and copies > 0:
                    counted[name] += copies
            zones[zone] = counted
        return "structured", zones
    text = row.get("decklist")
    if not isinstance(text, str) or not text.strip():
        return "missing", {}
    if URL_ONLY.match(text):
        return "url_only", {}
    zones, zone = {}, "Mainboard"
    for line in text.splitlines():
        section = TEXT_SECTION.match(line)
        if section:
            zone = (section.group(1) or section.group(2)).strip().title()
            continue
        card = TEXT_LINE.match(line)
        if card:
            zones.setdefault(zone, Counter())[card.group(2)] += int(card.group(1))
    return ("text" if zones else "unparsed_text"), zones


# Art-series cards and tokens reuse real card names but are never deck cards.
NOT_PLAYABLE = ("art_series", "token", "double_faced_token", "emblem")


def resolve(names: set[str], dsn: str) -> dict[str, list[str]]:
    """Oracle IDs for each name in the active local catalog snapshot: an exact
    canonical name first, else an exact face name, ignoring unplayable layouts."""
    import psycopg
    from mtg_scorer.normalize.names import name_key

    keys = {name: name_key(name) for name in names}
    with psycopg.connect(dsn) as connection:
        rows = connection.execute(
            "SELECT a.alias_key, a.kind, a.oracle_id::text "
            "FROM catalog.catalog_alias a "
            "JOIN catalog.active_catalog s USING (catalog_snapshot_id) "
            "JOIN catalog.catalog_card c USING (catalog_snapshot_id, oracle_id) "
            "WHERE a.alias_key = ANY(%s) AND c.layout <> ALL(%s)",
            (sorted(set(keys.values())), list(NOT_PLAYABLE)),
        ).fetchall()
    found: dict[str, dict[str, set[str]]] = {}
    for key, kind, oracle in rows:
        found.setdefault(key, {}).setdefault(kind, set()).add(oracle)
    return {
        name: sorted(found.get(key, {}).get("canonical") or found.get(key, {}).get("face", []))
        for name, key in keys.items()
    }


def measure(events: list[dict], dsn: str | None) -> dict:
    supply, zone_presence, records, tables = Counter(), Counter(), Counter(), Counter()
    lines: list[tuple[str, int]] = []
    per_event = []
    for event in events:
        standings = event.get("standings") or []
        event_decks = Counter()
        for row in standings:
            how, zones = deck_lines(row)
            supply[how] += 1
            event_decks[how] += 1
            if how in ("structured", "text"):
                zone_presence["mainboard"] += bool(zones.get("Mainboard"))
                zone_presence["sideboard_listed"] += "Sideboard" in zones
                zone_presence["commanders_listed"] += bool(zones.get("Commanders"))
                lines.extend(zones.get("Mainboard", Counter()).items())
                lines.extend(zones.get("Sideboard", Counter()).items())
            known = [row.get(field) is not None for field in ("wins", "losses", "draws")]
            records["complete" if all(known) else "missing_component"] += 1
        event_tables = Counter()
        for round_ in event.get("rounds") or []:
            bracket = isinstance(round_.get("round"), str)
            for table in round_.get("tables") or []:
                status = table.get("status")
                if status == "Bye" or table.get("table") == "Byes":
                    event_tables["bye"] += 1
                    continue
                event_tables["bracket" if bracket else "swiss"] += 1
                event_tables[f"status:{status}"] += 1
                if status == "Completed":
                    winner = table.get("winner_id")
                    event_tables[
                        "draw" if winner == "Draw" else "decided" if winner else "no_result"
                    ] += 1
        tables.update(event_tables)
        per_event.append(
            {
                "tid": event.get("TID"),
                "name": event.get("tournamentName"),
                "start": iso(event.get("startDate")),
                "status": event.get("info", {}).get("status"),
                "swiss_rounds": event.get("swissNum"),
                "top_cut": event.get("topCut"),
                "participants": len(standings),
                "decks": dict(sorted(event_decks.items())),
                "rounds_returned": len(event.get("rounds") or []),
                "tables": dict(sorted(event_tables.items())),
            }
        )
    return {
        "events": per_event,
        "decks": {"standings_rows": sum(supply.values()), **supply},
        "zones_in_parsed_decks": dict(zone_presence),
        "standing_records": dict(records),
        "tables": dict(sorted(tables.items())),
        "card_resolution": resolution(lines, dsn),
    }


def resolution(lines: list[tuple[str, int]], dsn: str | None) -> dict | None:
    """Line- and copy-weighted resolution, with denominators kept."""
    if not dsn or not lines:
        return None
    matches = resolve({name for name, _ in lines}, dsn)
    outcome = {
        name: "resolved" if len(ids) == 1 else "ambiguous" if ids else "unresolved"
        for name, ids in matches.items()
    }
    by_line, by_copy = Counter(), Counter()
    for name, copies in lines:
        by_line[outcome[name]] += 1
        by_copy[outcome[name]] += copies
    return {
        "lines": {"total": len(lines), **by_line},
        "copies": {"total": sum(copies for _, copies in lines), **by_copy},
        "unresolved_names": sorted(n for n, o in outcome.items() if o == "unresolved")[:50],
        "ambiguous_names": sorted(n for n, o in outcome.items() if o == "ambiguous")[:50],
    }


def month_windows(first: str, last: str) -> list[tuple[str, int, int]]:
    """Calendar months from first to last ("2026-03"), as [start, end) in UTC seconds."""
    year, month = map(int, first.split("-"))
    windows = []
    while (year, month) <= tuple(map(int, last.split("-"))):
        following = (year + month // 12, month % 12 + 1)
        start = datetime(year, month, 1, tzinfo=UTC).timestamp()
        end = datetime(*following, 1, tzinfo=UTC).timestamp()
        windows.append((f"{year:04d}-{month:02d}", int(start), int(end)))
        year, month = following
    return windows


def day_windows(first: str, last: str, days: int) -> list[tuple[str, int, int]]:
    """Consecutive spans of `days` days covering the months first..last, as [start, end)."""
    _, start, _ = month_windows(first, first)[0]
    _, _, stop = month_windows(last, last)[0]
    windows = []
    while start < stop:
        end = min(start + days * 86_400, stop)
        windows.append((datetime.fromtimestamp(start, UTC).strftime("%Y-%m-%d"), start, end))
        start = end
    return windows


def survey(
    client: Client,
    fmt: str,
    first: str,
    last: str,
    dsn: str | None,
    window_days: int | None = None,
) -> dict:
    """One search per month (or per window of days) with decklists: how many decks each
    window publishes. Busy formats such as EDH need day windows to stay under the cap."""
    months, events, lines = [], [], []
    windows = day_windows(first, last, window_days) if window_days else month_windows(first, last)
    for label, start, end in windows:
        found = client.call(
            "POST",
            "/v2/tournaments",
            {
                "game": GAME,
                "format": fmt,
                "start": start,
                "end": end - 1,
                # Bracket results let the scorer read top cuts directly.
                "columns": [
                    "decklist",
                    "wins",
                    "losses",
                    "draws",
                    "winsBracket",
                    "lossesBracket",
                    "byes",
                ],
            },
            f"search-{label}.json",
            50_000_000,
        )
        month = Counter()
        for event in found:
            if event.get("isTeamEvent") or not start <= event.get("startDate", -1) < end:
                continue
            supply = Counter()
            for row in event.get("standings") or []:
                how, zones = deck_lines(row)
                supply[how] += 1
                for zone in ("Mainboard", "Sideboard"):
                    lines.extend(zones.get(zone, Counter()).items())
            players, listed = sum(supply.values()), supply["structured"] + supply["text"]
            month.update(events=1, players=players, decks_with_lists=listed)
            month.update({f"supply:{how}": n for how, n in supply.items()})
            if listed:
                month.update(events_with_lists=1, players_in_those_events=players)
                events.append(
                    {
                        "month": label,
                        "tid": event.get("TID"),
                        "name": event.get("tournamentName"),
                        "start": iso(event.get("startDate")),
                        "players": players,
                        "decks_with_lists": listed,
                        "top_cut": event.get("topCut"),
                    }
                )
        months.append({"month": label, **dict(sorted(month.items()))})
    return {
        "months": months,
        "events_with_lists": events,
        "card_resolution": resolution(lines, dsn),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-key", action="store_true", help="Only confirm the key loads")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", default="Modern")
    parser.add_argument("--start", default="2026-08-01", help="UTC date, inclusive")
    parser.add_argument("--end", default="2026-09-01", help="UTC date, exclusive")
    parser.add_argument("--max-events", type=int, default=3)
    parser.add_argument("--max-decks", type=int, default=100)
    parser.add_argument("--catalog-dsn", help="Local catalog database for card-name resolution")
    parser.add_argument(
        "--skip-info",
        action="store_true",
        help="Skip per-event info requests; search results are already completed events",
    )
    parser.add_argument(
        "--survey",
        nargs=2,
        metavar=("FIRST", "LAST"),
        help="Instead of the capped probe, count decklists per month, e.g. 2026-03 2026-08",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        help="With --survey, search windows of this many days instead of calendar months",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="An interrupted run's directory; responses already saved there are reused",
    )
    args = parser.parse_args()
    key = load_key()
    if args.check_key:
        print("TOPDECK_API_KEY is set; its value is not shown.")
        return
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    output = args.resume or args.output or ROOT / f"analytics/data/local/topdeck-probe-{stamp}"
    if args.resume:
        if not output.is_dir() or (output / "summary.json").exists():
            raise SystemExit("--resume needs an interrupted run's directory without a summary.")
    else:
        # Exclusive directory creation prevents overwriting an earlier observation.
        output.mkdir(parents=True, exist_ok=False)
    client = Client(key, output)
    if args.survey:
        summary = {
            "probe_version": "tournament-volume-v1",
            "format": args.format,
            **survey(client, args.format, *args.survey, args.catalog_dsn, args.window_days),
        }
        manifest = {"probe_version": summary["probe_version"], "requests": client.records}
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", "utf-8")
        print(f"Raw responses and summary: {output}")
        print(json.dumps(summary, indent=2))
        return
    start, end = day(args.start), day(args.end)
    found = client.call(
        "POST",
        "/v2/tournaments",
        {
            "game": GAME,
            "format": args.format,
            "start": start,
            "end": end - 1,
            "columns": ["wins", "losses", "draws"],
        },
        "search.json",
        50_000_000,
    )
    eligible = sorted(
        (e for e in found if not e.get("isTeamEvent") and start <= e.get("startDate", -1) < end),
        key=lambda e: (e["startDate"], str(e["TID"])),
    )
    selected, skipped, budget = [], [], args.max_decks
    for event in eligible:
        if len(selected) == args.max_events:
            break
        size = len(event.get("standings") or [])
        if size == 0 or size > budget:
            skipped.append(
                {
                    "tid": event["TID"],
                    "participants": size,
                    "reason": "no standings" if size == 0 else "exceeds remaining deck budget",
                }
            )
            continue
        selected.append(event["TID"])
        budget -= size
    events = []
    if selected:
        events = client.call(
            "POST",
            "/v2/tournaments",
            {"TID": selected, "columns": COLUMNS, "rounds": True},
            "tournaments.json",
            20_000_000,
        )
        for event in [] if args.skip_info else events:
            event["info"] = client.call(
                "GET",
                f"/v2/tournaments/{event['TID']}/info",
                None,
                f"info-{event['TID']}.json",
                1_000_000,
            )
    summary = {
        "probe_version": "tournament-feasibility-v1",
        "window": {"format": args.format, "start": args.start, "end_exclusive": args.end},
        "caps": {"max_events": args.max_events, "max_decks": args.max_decks},
        "search": {
            "returned": len(found),
            "eligible_non_team": len(eligible),
            "participants_in_eligible": sum(len(e.get("standings") or []) for e in eligible),
        },
        "skipped_before_cap": skipped,
        **measure(events, args.catalog_dsn),
    }
    manifest = {"probe_version": summary["probe_version"], "requests": client.records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Raw responses and summary: {output}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
