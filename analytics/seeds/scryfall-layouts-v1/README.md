# Real bounded Scryfall seed

These are the exact eight successful JSON responses retained by milestone 1 on
2026-09-08 UTC. `manifest.json` records each request, retrieval time, Scryfall ID
and SHA-256 of the raw response. All original bytes are preserved. The separate
`contracts/fixtures/` files are synthetic adversarial conformance data.

Purposeful selection: Lightning Bolt (M11 common and 2X2 uncommon), Delver of
Secrets, Fire // Ice, Bonecrusher Giant, Valakut Awakening, Erayo and Bruna.
This sample demonstrates seven layouts; it is neither a full catalog nor evidence
of tournament use, historical legality or Forge implementation.

Attribution: card metadata from [Scryfall](https://scryfall.com/docs/api), Magic:
The Gathering card names and rules belong to Wizards of the Coast. No image
binaries are included or fetched by the application. Image URLs are retained only
as source metadata. This local demonstration does not grant a license to card art
or resolve the project's public-release licensing decision.

Regeneration is an explicit online operation outside CI:
`python scripts/probe_catalog.py --output analytics/data/local/new-layout-probe`.
A newly fetched response is a new source snapshot; never replace this seed in
place. Export locally with the documented demo command; replay needs no network.
