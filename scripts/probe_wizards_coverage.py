"""Bounded, opt-in probe of one archived Wizards event-coverage site; never used by CI.

From about 2004 to 2010 Wizards published every player's decklist and every round's
results for constructed Pro Tours. Those pages survive only in the Internet Archive.
The probe lists one event's archived pages, saves the original bytes of its decklist,
round-results and final-standings pages privately, and prints only aggregate coverage:
decklists against players, how decklist names join the standings, match records and
card-name resolution. No player names are printed or written to the summary.

Events up to 2008 have codes such as ``mtgevent/ptla05``; from 2009 the coverage moved
to ``mtg/daily/eventcoverage/ptaus09``, served through Magazine/Article.aspx. The parsers
live in ``mtg_scorer.ingest.wizards``, which reads the saved directory into score inputs
(``mtg-scorer score-wizards``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from mtg_scorer.ingest.wizards import (
    STANDINGS_PAGE,
    catalog_resolver,
    deck_pages,
    decode_page,
    join_names,
    name_tokens,
    page_text,
    parse_decks,
    parse_results,
    parse_standings,
    records,
    result_round,
)

ROOT = Path(__file__).resolve().parents[1]
WAYBACK = "https://web.archive.org"
USER_AGENT = "mtg-scorer/0.3 feasibility (+https://github.com/PauloRicardoNeis/mtg-scorer)"
FORMAT_STANDINGS = "formatstandings"
# The same coverage page was served under several addresses as the site was rebuilt.
URL_FORMS = (
    "www.wizards.com/default.asp?x=",
    "www.wizards.com/Magic/Magazine/Events.aspx?x=",
    "www.wizards.com/Magic/Magazine/Article.aspx?x=",
    "www.wizards.com/Magic/TCG/Events.aspx?x=",
)


class ArchiveError(Exception):
    """A request that still failed after its retries."""


class Archive:
    """Two seconds between requests; 429 and 5xx responses are retried with a backoff."""

    def __init__(self, output: Path) -> None:
        self.output = output
        self.records: list[dict] = []

    def get(self, url: str, filename: str, limit: int = 5_000_000, attempts: int = 4) -> bytes:
        saved = self.output / filename
        if saved.exists():
            # A resumed run reuses responses already saved for this request.
            payload = saved.read_bytes()
            self.records.append(
                {
                    "url": url,
                    "reused": True,
                    "raw_file": filename,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
            return payload
        payload, status = b"", 0
        for attempt in range(attempts):
            time.sleep(2)
            try:
                with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=90) as r:
                    payload = r.read(limit + 1)
                    status = r.status
                break
            except HTTPError as error:
                if (error.code == 429 or error.code >= 500) and attempt < attempts - 1:
                    wait = 15 * 2**attempt
                    print(f"HTTP {error.code} for {url}; waiting {wait}s.", flush=True)
                    time.sleep(wait)
                    continue
                raise ArchiveError(f"{url} failed: HTTP {error.code}") from None
            except (URLError, TimeoutError) as error:
                if attempt < attempts - 1:
                    time.sleep(15 * 2**attempt)
                    continue
                raise ArchiveError(f"{url} failed: {getattr(error, 'reason', error)}") from None
        if len(payload) > limit:
            raise ArchiveError(f"{url} exceeds the {limit:,}-byte probe limit")
        saved.write_bytes(payload)
        self.records.append(
            {
                "url": url,
                "http_status": status,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "raw_file": filename,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        return payload


def archived_pages(archive: Archive, event: str) -> dict[str, tuple[str, str]]:
    """Each archived page of the event as slug -> (capture timestamp, original URL),
    the earliest capture of any address form, so the page is closest to the event.

    The CDX API is often slow, so listings get more patient retries. A listing that
    still fails ends the run: a page missing from it would go unnoticed. ``--resume``
    reuses the listings already saved."""
    pages: dict[str, tuple[str, str]] = {}
    for index, form in enumerate(URL_FORMS):
        prefix = quote(f"{form}{event}/", safe="")
        listing = archive.get(
            f"{WAYBACK}/cdx/search/cdx?url={prefix}&matchType=prefix&output=json"
            "&fl=timestamp,original&filter=statuscode:200&collapse=urlkey&limit=5000",
            f"cdx-{index}.json",
            attempts=6,
        )
        rows = json.loads(listing or b"[]")
        for timestamp, original in rows[1:]:
            # "afdecks,0" was an older address of the same page as "afdecks".
            slug = re.sub(r",\d+$", "", original.rsplit("/", 1)[-1].split("&")[0].lower())
            if slug not in pages or timestamp < pages[slug][0]:
                pages[slug] = (timestamp, original)
    return pages


def parse_format_points(page: str) -> dict[str, int]:
    """Each player's points in the constructed format, from the "standings by format"
    page of mixed-format events (columns: name, constructed, Booster Draft, total)."""
    points = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = [page_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) >= 3 and cells[1].isdigit():
            points[cells[0]] = int(cells[1])
    return points


def resolution(lines: list[tuple[str, int]], dsn: str | None) -> dict | None:
    """Line- and copy-weighted resolution, with denominators kept."""
    if not dsn or not lines:
        return None
    matches = catalog_resolver(dsn)({name for name, _ in lines}).matches
    outcome = {
        name: "resolved" if len(found) == 1 else "ambiguous" if found else "unresolved"
        for name, found in matches.items()
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--event",
        default="mtgevent/ptla05",
        help="coverage code, e.g. mtgevent/ptla05 or mtg/daily/eventcoverage/ptaus09",
    )
    parser.add_argument("--format", default="Extended")
    parser.add_argument("--date", default="2005-10-28", help="first day of the event")
    parser.add_argument(
        "--constructed-rounds",
        help="rounds played in the format, e.g. 1-8,12-16; default every results page",
    )
    parser.add_argument("--catalog-dsn", help="Local catalog database for card-name resolution")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", type=Path, help="An interrupted run's directory")
    args = parser.parse_args()
    slug = args.event.rsplit("/", 1)[-1]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    output = args.resume or args.output or ROOT / f"analytics/data/local/wizards-{slug}-{stamp}"
    if args.resume:
        if not output.is_dir() or (output / "summary.json").exists():
            raise SystemExit("--resume needs an interrupted run's directory without a summary.")
    else:
        # Exclusive directory creation prevents overwriting an earlier observation.
        output.mkdir(parents=True, exist_ok=False)
    archive = Archive(output)
    pages = archived_pages(archive, args.event)

    def fetch(name: str) -> str:
        timestamp, original = pages[name]
        # id_ returns the bytes as captured, without the archive's toolbar or rewriting.
        return decode_page(
            archive.get(f"{WAYBACK}/web/{timestamp}id_/{original}", f"page-{name}.html")
        )

    decks, per_page = {}, {}
    for name in deck_pages(pages):
        found = parse_decks(fetch(name))
        per_page[name] = len(found)
        for deck in found:
            decks.setdefault(" ".join(name_tokens(deck["player"])), deck)
    wanted = None
    if args.constructed_rounds:
        wanted = set()
        for part in args.constructed_rounds.split(","):
            first, _, last = part.partition("-")
            wanted.update(range(int(first), int(last or first) + 1))
    result_pages = sorted((number, p) for p in pages if (number := result_round(p)) is not None)
    rounds, byes, unread = {}, Counter(), 0
    for number, name in result_pages:
        # Every round is saved, so the choice of constructed rounds can be checked later.
        matches, round_byes, round_unread = parse_results(fetch(name))
        if wanted is not None and number not in wanted:
            continue
        rounds[number] = matches
        byes.update(round_byes)
        unread += round_unread
    format_points = (
        parse_format_points(fetch(FORMAT_STANDINGS)) if FORMAT_STANDINGS in pages else {}
    )
    standings = parse_standings(fetch(STANDINGS_PAGE)) if STANDINGS_PAGE in pages else []
    players = [name for _, name in standings]
    joined, join_how = join_names([d["player"] for d in decks.values()], players)
    record = records(rounds)
    lines = [
        (card, copies)
        for deck in decks.values()
        for zone in ("main", "side")
        for card, copies in deck[zone].items()
    ]
    main_sizes = Counter(sum(d["main"].values()) for d in decks.values())
    side_sizes = Counter(sum(d["side"].values()) for d in decks.values())
    expected_rounds = (
        sorted(wanted) if wanted is not None else list(range(1, max(rounds, default=0) + 1))
    )
    summary = {
        "probe_version": "wizards-coverage-v1",
        "event": {
            "code": args.event,
            "format": args.format,
            "date": args.date,
            "constructed_rounds": sorted(wanted) if wanted is not None else None,
        },
        "archive": {
            "pages_archived": len(pages),
            "decklist_pages": per_page,
            "results_rounds_archived": sorted(rounds),
            "results_rounds_missing": [r for r in expected_rounds if r not in rounds],
            "final_standings": bool(standings),
        },
        "players": len(players),
        "decklists": {
            "parsed": sum(per_page.values()),
            "unique_players": len(decks),
            "joined_to_standings": len(joined),
            "join_methods": dict(join_how),
            "coverage": round(len(joined) / len(players), 4) if players else None,
            "mainboard_sizes": dict(sorted(main_sizes.items())),
            "sideboard_sizes": dict(sorted(side_sizes.items())),
            "labelled": sum(bool(d["label"]) for d in decks.values()),
        },
        "results": {
            "rounds": len(rounds),
            "matches_by_round": {r: len(m) for r, m in sorted(rounds.items())},
            "draws": sum(o == "drew" for m in rounds.values() for _, o, _ in m),
            "byes": sum(byes.values()),
            "unread_rows": unread,
            "players_with_results": len(record),
            "result_names_in_standings": len(set(record) & set(players)),
            "decks_with_record": sum(
                joined[d["player"]] in record for d in decks.values() if d["player"] in joined
            ),
        },
        # The coverage's own points in the constructed format, against 3 a win and 1 a
        # draw over the chosen rounds: agreement confirms which rounds were constructed.
        "format_standings": {
            "players": len(format_points),
            "points_agree": sum(
                3 * (record.get(name, Counter())["won"] + byes[name])
                + record.get(name, Counter())["drew"]
                == points
                for name, points in format_points.items()
            ),
        }
        if format_points
        else None,
        "top_cut": {
            "size": sum(rank <= 8 for rank, _ in standings),
            "decks_known": sum(rank <= 8 and name in joined.values() for rank, name in standings),
        },
        "card_resolution": resolution(lines, args.catalog_dsn),
    }
    # The manifest names the event, so the saved pages can be scored on their own.
    manifest = {
        "probe_version": summary["probe_version"],
        "event": summary["event"],
        "requests": archive.records,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Raw pages and summary: {output}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ArchiveError as error:
        raise SystemExit(str(error)) from None
