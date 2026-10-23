# 2. Data and cohorts

Everything a score says is a statement about one cohort. This document describes
how raw tournament data becomes that cohort: the sources, the facts kept from
them, how coverage is recorded, which events and decks count, how a deck's record
and top-cut result are established, how archetypes are named, and which cards are
scored at all.

## Sources

| Source | Era | What it provides | Adapter |
| --- | --- | --- | --- |
| TopDeck.gg bulk tournament API | 2024-2026, every Magic format TopDeck lists | Standings with wins/losses/draws/byes per player, structured decklists keyed by Scryfall oracle id, archetype labels for 60-card formats, commander zones, optional bracket records, top-cut size | `analytics/src/mtg_scorer/ingest/topdeck.py` (parser `topdeck-bulk-v5`) |
| Wizards of the Coast Pro Tour coverage via the Internet Archive | 2004-2010 constructed Pro Tours | Every player's decklist, every round's results, final standings; card names resolved against the local catalog | `analytics/src/mtg_scorer/ingest/wizards.py` (parser `wizards-coverage-v1`) |

Both adapters are offline. They read a directory saved by an opt-in probe script,
verify each file against the manifest's SHA-256, and refuse a file that does not
match. No application request ever calls a third-party site.

The dataset identity is derived, not assigned. For TopDeck it is `topdeck-` plus
the SHA-256 of the source name, parser version and the sorted list of
`[file name, file sha256]`. The same saved bytes always yield the same identity.

## Facts

`analytics/src/mtg_scorer/domain.py` defines the source-independent facts. The
relevant ones for scoring:

- **Tournament**: provenance, the date it occurred, format name, player count,
  top-cut size (0 when the event had no elimination rounds, `None` when unknown),
  and a `CoverageProfile` with three independent dimensions: decklists, standings
  and matches. Each dimension carries a scope (`FULL_FIELD`, `TOP_CUT`, `WINNERS`,
  `PARTIAL`, `NONE`, `UNKNOWN`) and observed/expected counts. `observed_fraction` is
  defined only when the expected count is known and non-zero.
- **DeckEntry**: one registered deck with at most one `DeckCard` per oracle id,
  each with mainboard and sideboard copies. `sideboard_observed` is false unless the
  source reported a sideboard zone and every line of it was readable, so a missing
  sideboard stays unknown instead of reading as empty. `archetype_label` is the
  source's own name for the deck. `commanders` are the sorted oracle ids the source
  listed as commanders, at most two (partners, a background, an oathbreaker and its
  signature spell); a longer commander zone is treated as a misplaced decklist and
  names no commander.
- **Standing**: a deck's final rank, wins, losses, draws, byes and `made_top_cut`,
  each independently `None` when unknown. `recorded_matches` is `None` when wins,
  losses and draws are all unknown.
- **Match** and **MatchParticipant** exist for round-level results, but neither
  adapter produces them for scoring today; every record comes from standings.

Every fact carries a `Provenance`: source, source record id, timezone-aware
retrieval time, parser version and the raw snapshot reference.

### What the TopDeck adapter reads as "played"

A card counts as played in a deck when it has mainboard copies. The TopDeck
adapter sums the `Mainboard` zone and any commander zone (`Commanders`,
`Commander`, case-insensitively) into mainboard copies, because commander formats
keep the commander apart from the main deck. The `Sideboard` zone is kept
separately and never counted as usage.

A card line without a Scryfall oracle id or with a non-positive count is
quarantined. A quarantined mainboard line makes the whole deck's mainboard
**incomplete**; such decks are excluded from the cohort and counted in
`incomplete_decks_excluded`. Team events report one standing per team and are
skipped entirely.

Counts the source reports as negative (it occasionally returns -1) are read as
unknown.

## Cohort rules

A cohort is defined by a JSON file in `analytics/cohorts/` loaded into
`CohortRules`:

| Field | Meaning | Default |
| --- | --- | --- |
| `version` | A label; part of the hash | required |
| `format_name` | The source's format name an event must match exactly | required |
| `starts_on`, `ends_before` | ISO dates; the window includes the start and excludes the end | required |
| `min_decklist_coverage` | The minimum observed fraction of decklists an event needs | 0.5 |
| `excluded_events` | Source event ids excluded on purpose, each with a reason | none |
| `players_per_game` | 2 for one-on-one, 4 for Commander pods | 2 |

An event is included only when all of these hold, checked in this order so the
recorded exclusion reason is the first that applies:

1. it is not in `excluded_events`;
2. its format name equals the rules' format name;
3. `starts_on <= occurred_on < ends_before`;
4. its decklist coverage is known (observed and expected counts both present,
   expected non-zero);
5. that coverage is at least `min_decklist_coverage`.

Every excluded event is listed in the run file with its reason, so a reader can
see why a known event is missing.

Of the included events, the cohort keeps every deck whose mainboard was read
completely and every standing. Decklist coverage is `listed decks / players` for
the event, where a player counts as listed when their row carries a non-empty
`Mainboard`.

The 50% floor is a bias control rather than a sample-size rule. Events where only
the top tables publish lists would make a card's incidence an incidence *among
winners*, which the measurement contract forbids as a field-wide share. Requiring
half the field keeps the denominator close to the field.

The rules hash (`CohortRules.fingerprint`) covers every field, so a changed window,
threshold or exclusion yields a different run identity.

## Records and the win rate

A deck's record is used only when wins, losses and draws are all known. Byes are
not matches and are never counted. The cohort's `Record` sums the records of every
deck with a standing.

```text
games    = wins + losses + draws
win_rate = (wins + draws / players_per_game) / games
```

A draw shares the win among the players at the table. In a one-on-one format each
match contributes one win and one loss, or two half-wins, so a complete field
averages exactly 50%. In a four-player pod each game contributes one win and three
losses, or four quarter-wins, so the field averages 25%. This is why the site shows
win rate against the field rather than the raw figure in commander formats, and
why the overall run never pools raw win rates across formats.

Games are counted per deck. A match between two decks that both play a card
contributes one win and one loss to that card's record, which pulls the card
toward the field; a mirror-heavy card cannot show a large delta from standings
alone. The field's own win rate is not exactly 50% whenever some decks lack
records or the source's rows disagree with each other.

`matches` in the run file is `games // players_per_game`: every player at a table
reports the same game.

## Establishing the top cut

A deck's top-cut result is a tri-state: made it, did not, unknown. The TopDeck
adapter establishes it per event and records the basis used
(`cohort.events[].top_cut_basis`):

| Basis | When | Result |
| --- | --- | --- |
| `no_top_cut` | the event reports no `topCut` | every deck `None`; the event has no elimination rounds |
| `unknown_top_cut` | the `topCut` value is unreadable (for example "8-0") | every deck `None` |
| `bracket_record` | every row carries `winsBracket` and `lossesBracket` | a deck made the cut when `winsBracket + lossesBracket > 0` |
| `standing_order` | no bracket columns, every row has known wins, and no player below the cut has more wins than the lowest inside it | the first `topCut` rows made it |
| `inconsistent_order` | the response order contradicts the wins | every deck `None` |

The standing-order fallback exists because the saved Modern responses carry no
bracket columns. TopDeck does not document that its row order is the final
standing, so the order is trusted only when it is consistent with the Swiss
records. When it is not, nothing is inferred.

The Wizards adapter uses the final standings page: every Pro Tour of the era cut
to a top 8, so a deck with a final rank of 8 or better made the cut, and the basis
is `standing_order`. When the standings do not place exactly eight players at
rank 8 or better, the cut is unknown.

The field's top-cut rate is `top_cut_decks / top_cut_known_decks` over the
cohort's decks with a standing, and is `None` when no result is known.

## Archetypes and commanders

A deck's archetype is, in order:

1. the source's `archetype` label, trimmed, when present; otherwise
2. in commander formats, its commanders: the names of the commander cards,
   sorted, joined with ` + ` so a partner pair is one archetype; otherwise
3. none.

TopDeck labels only 60-card formats, so commander decks fall to rule 2. A commander
card is named as the cohort's decks most often spell it, so a double-faced
commander listed with and without its back face stays one archetype.

For every archetype the cohort computes an `ArchetypeCore`: its decks, events,
record, top cuts with denominator, trend series, the commanders that name it (for
rule-2 archetypes; for a source label that also happens to be a commander name,
the commanders most of its decks share) and its **core cards**: the oracle ids
played by at least 50% of its decks (`CORE_CARD_SHARE`). Archetypes are compared
with the field exactly as cards are, which is how the commander rankings page
works.

The cohort's **archetype concentration** is the chance that two different labelled
decks share an archetype (see [Simpson's index](03-statistical-toolkit.md#simpsons-index-without-small-sample-bias)).
It is the field baseline the Signature score shrinks a card's focus toward.

## The trend series

Each run carries a 12-period series of deck counts ending where the window ends.
The period length is a twelfth of the window rounded up, capped at 30 days:

```text
period_days  = min(30, ceil(window_days / 12))
series_start = ends_before - 12 * period_days
```

Weeks would leave most periods empty in formats with a few events a month. An
event's period index is counted back from the end, so with a 184-day window the
periods are 16 days long and the series starts 192 days before the end, slightly
before the window; events before the series start are not in any period. Every
card and archetype carries its own 12 counts, and the cohort carries the
denominators, so the site can draw a share sparkline and leave a gap, not a zero,
in a period without decks.

## The published deck order

From feature pipeline `card-usage-v7` a run lists its decks and each card lists
the positions of its decks. The order is: newest event first, events of the same
day by source event id, and each event's decks in the order the source listed
them. The validator recounts each card's decks, copies, events, top cuts and record
from this list and refuses a run where they disagree. TopDeck's row order is not
read as a final rank; a deck carries only the result its standing reported.

## The scored population

`POPULATION_RULE = "mainboard-cards-without-basic-lands-v1"`: every card with
mainboard copies in some cohort deck, except the ten basic lands, their snow
versions and Wastes. Basic lands are still described in the run (decks, record,
performance) but marked `scored: false`, because they would otherwise lead every
volume ranking and dilute every percentile.

A method receives the whole population at once. Percentiles are therefore among
the scored cards of that cohort, and a card absent from the population has no
score rather than a score of zero. The site's ranks run from 1 to `scored_cards`.
