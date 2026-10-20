"""SYNTHETIC Wizards coverage directories built from the hand-written page fixtures."""

import json
import shutil
from hashlib import sha256
from pathlib import Path

from mtg_scorer.ingest.wizards import NameResolution, match_names

FIXTURES = Path(__file__).parent / "fixtures" / "wizards"
EVENT = {"code": "mtgevent/ptsyn05", "format": "Extended", "date": "2005-10-28"}
TABLE_PAGES = (
    "afdecks",
    "gzdecks",
    "t8decks",
    "res1",
    "res2",
    "res3",
    "standfin",
)


def oracle(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012d}"


# (alias_key, kind, oracle_id, catalog name) rows, as the catalog stores them.
CATALOG = [
    ("island", "canonical", oracle(1), "Island"),
    ("mountain", "canonical", oracle(2), "Mountain"),
    ("psychatog", "canonical", oracle(3), "Psychatog"),
    ("fire // ice", "canonical", oracle(4), "Fire // Ice"),
    ("fire", "face", oracle(4), "Fire // Ice"),
    ("start // fire", "canonical", oracle(5), "Start // Fire"),
    ("fire", "face", oracle(5), "Start // Fire"),
    ("stitch together", "canonical", oracle(6), "Stitch Together"),
    ("lim-dûl's vault", "canonical", oracle(7), "Lim-Dûl's Vault"),
    ("counterspell", "canonical", oracle(8), "Counterspell"),
    ("naturalize", "canonical", oracle(9), "Naturalize"),
    ("lightning helix", "canonical", oracle(10), "Lightning Helix"),
    ("frogmite", "canonical", oracle(11), "Frogmite"),
    ("aether vial", "canonical", oracle(12), "Aether Vial"),
    ("wear // tear", "canonical", oracle(13), "Wear // Tear"),
    ("tarmogoyf", "canonical", oracle(14), "Tarmogoyf"),
]


def resolver(names):
    return NameResolution("catalog-synthetic", match_names(names, CATALOG))


def save(
    tmp_path, template="table", pages=TABLE_PAGES, event=EVENT, retrieved_at=True, name="saved"
):
    """Copy fixture pages into a probe directory with a manifest naming the event."""

    directory = tmp_path / name
    directory.mkdir()
    requests = []
    for slug in pages:
        name = f"page-{slug}.html"
        shutil.copyfile(FIXTURES / template / name, directory / name)
        payload = (directory / name).read_bytes()
        request = {"url": f"https://example.invalid/{slug}", "raw_file": name}
        if retrieved_at:
            request["retrieved_at"] = "2026-10-20T04:48:00+00:00"
        requests.append({**request, "sha256": sha256(payload).hexdigest()})
    manifest = {"probe_version": "wizards-coverage-v1", "requests": requests}
    if event is not None:
        manifest["event"] = event
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory
