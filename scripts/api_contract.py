"""Capture or compare live Spring OpenAPI and verify its checked-in TypeScript consumer."""

import argparse
import json
import os
import subprocess
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/catalog-api.openapi.json"


def normalized(spec: dict) -> dict:
    spec.pop("servers", None)
    return spec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    with urlopen(args.url.rstrip("/") + "/v3/api-docs", timeout=15) as response:
        actual = normalized(json.load(response))
    if args.update:
        CONTRACT.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif actual != normalized(json.loads(CONTRACT.read_bytes())):
        raise SystemExit(
            "Spring OpenAPI drift: run scripts/api_contract.py --url <API> --update, "
            "regenerate the TS client, and review both."
        )
    generated = ROOT / "web/src/lib/api.generated.ts"
    before = generated.read_bytes() if generated.exists() else None
    npm = "npm.cmd" if os.name == "nt" else "npm"
    subprocess.run(
        [npm, "--prefix", str(ROOT / "web"), "run", "generate:api"], check=True, cwd=ROOT
    )
    if not args.update and generated.read_bytes() != before:
        raise SystemExit("Generated TypeScript drift; review the regenerated client.")
    print("Live Spring OpenAPI and generated TypeScript client agree.")


if __name__ == "__main__":
    main()
