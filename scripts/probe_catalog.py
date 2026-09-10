"""Bounded, opt-in live feasibility probe; never used by normal CI."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CASES = (
    ("Lightning Bolt", "m11"),
    ("Lightning Bolt", "2x2"),
    ("Delver of Secrets", None),
    ("Fire // Ice", None),
    ("Bonecrusher Giant", None),
    ("Valakut Awakening", None),
    ("Erayo, Soratami Ascendant", None),
    ("Bruna, the Fading Light", None),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Exclusive directory creation prevents overwriting an earlier observation.
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for index, (name, set_code) in enumerate(CASES):
        params = {"exact": name}
        if set_code:
            params["set"] = set_code
        url = "https://api.scryfall.com/cards/named?" + urlencode(params)
        request = Request(
            url,
            headers={
                "User-Agent": "mtg-scorer/0.2 feasibility (+https://github.com/PauloRicardoNeis/mtg-scorer)",
                "Accept": "application/json",
            },
        )
        time.sleep(1)
        with urlopen(request, timeout=30) as response:
            payload = response.read(2_000_001)
            if len(payload) > 2_000_000:
                raise ValueError("probe response exceeds 2 MB limit")
            status = response.status
        filename = f"{index:02d}.json"
        (args.output / filename).write_bytes(payload)
        card = json.loads(payload)
        records.append(
            {
                "request_url": url,
                "http_status": status,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "raw_file": filename,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "scryfall_id": card["id"],
                "oracle_id": card.get("oracle_id"),
                "name": card["name"],
                "layout": card["layout"],
                "set_code": card["set"],
                "rarity": card["rarity"],
                "face_count": len(card.get("card_faces", [])),
                "top_level_missing": [
                    key for key in ("mana_cost", "oracle_text", "colors") if key not in card
                ],
                "has_display_image": bool(card.get("image_uris"))
                or any(face.get("image_uris") for face in card.get("card_faces", [])),
            }
        )
    manifest = {
        "probe_version": "catalog-feasibility-v1",
        "selection": "purposeful-layout-sample",
        "records": records,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
