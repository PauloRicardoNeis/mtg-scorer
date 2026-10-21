# MTG Scorer: how cards are ranked

This folder explains the whole project with an emphasis on the mathematics and
statistics behind the card rankings. It describes the code as it is on branch
`feat/all-formats` on 2026-10-21; every formula was read from the source and the
worked example was produced by running the real pipeline. Where a document states
a default (a weight, a prior strength, a threshold) it names the file that holds it,
so a reader can confirm the number has not changed.

The [measurement contract](../measurement-contract.md) remains the authority on
what the system is *allowed* to infer. These documents describe what it *does*.

## Reading order

| Document | What it covers |
| --- | --- |
| [1. Project overview](01-project-overview.md) | Purpose, the three applications, the pipeline from raw responses to a ranked page, identity and reproducibility, where each piece lives, the commands |
| [2. Data and cohorts](02-data-and-cohorts.md) | Sources, source-independent facts, coverage, cohort rules, which decks count, match records, how a top cut is established, archetypes and commanders, the trend series, the scored population |
| [3. Statistical toolkit](03-statistical-toolkit.md) | The shared mathematics: proportions with denominators, shrinkage toward the field, mid-rank percentiles, percentile blends, saturation curves, Simpson's index, the win-rate interval, lifts, pooling, rounding |
| [4. Features](04-features.md) | Every per-card feature and performance statistic, with numerator, denominator, support, when it is unknown, and its value in the worked example |
| [5. Score methods](05-score-methods.md) | Each registered method in full: Constructed, Signature, Hidden gem, Overall, Relative volume and the Foundation model; configuration, algorithm, published inputs, edge cases, the tests that pin the behaviour |
| [6. Publication and ranking](06-publication-and-ranking.md) | The run file and its identity, validation, PostgreSQL publication, how the API ranks and sorts, movement against the previous run, the compare and commander pages, letter grades, tones, prices |
| [7. Worked example](07-worked-example.md) | A tiny synthetic cohort followed end to end, every intermediate value recomputed by hand |
| [8. Limitations and open questions](08-limitations-and-future-work.md) | What the numbers cannot say, known statistical weaknesses, and the research the measurement contract still defers |

## One-paragraph summary

MTG Scorer reads published tournament decklists and standings (TopDeck.gg for
2024-2026, archived Wizards Pro Tour coverage for 2004-2010), keeps every raw
response and its hash, turns them into source-independent facts, selects a
**cohort** (one format, one date window, events whose decklists cover at least half
the field), counts how each card was used and how the decks playing it performed
against that field, and then runs a set of replaceable, versioned **score methods**
over the population of mainboard cards. The main grade, the **Constructed score**,
shrinks each card's win rate and top-cut conversion toward the field by a fixed
number of pseudo-games, turns each component into a percentile among the scored
cards, blends the percentiles 60/25/15 with meta share, and takes a percentile
again, so the median card scores 50. Other methods ask different questions:
how much a card belongs to one strategy (**Signature**), whether a rarely played
card is a build-around its decks win with (**Hidden gem**), how a card does across
every format at once (**Overall**), and plain volume (**Relative volume**). Scores are
written to a run file whose name hashes everything that produced it, published to
PostgreSQL atomically, ranked by SQL in the Java API and shown as letter grades by
the Next.js site. Unknown is never zero at any stage.

## Glossary

- **Cohort**: the events, decks and standings of one source, format and window that
  pass the cohort rules. The population every score is relative to.
- **Field**: the whole cohort, as the baseline a card is compared with: its win
  rate, its top-cut rate, its archetype concentration.
- **Stratum**: the measurement contract's word for the same idea, a bounded slice
  such as `source + format + era + coverage class`.
- **Oracle id**: Scryfall's identity for a card across printings; the key every
  count is made on.
- **Mainboard**: the main deck plus, in commander formats, the commander zone.
  Sideboards are kept but never counted as usage.
- **Record**: wins, losses and draws from a deck's standing. Byes are not matches.
- **Top cut**: the players who advanced to elimination rounds; a deck's top-cut
  result is known, true or false, only where the source lets it be established.
- **Archetype**: the source's own label for a deck, or in commander formats the
  deck's commander or partner pair. Not an analytical clustering.
- **Shrinkage**: pulling a small-sample rate toward the field's rate by adding a
  fixed number of field-average pseudo-observations.
- **Percentile**: a card's mid-rank position among the scored cards, in (0, 1).
- **Score method**: a versioned, configured, deterministic function from one
  cohort's features to named outputs per card, registered in `SCORE_METHODS`.
- **Run**: one cohort scored by every registered method, written as one file and
  published as one unit. The **active run** of a source and format is the one the
  site shows by default.
- **Grade**: the letter (A+ to F) the site prints for a 0-100 percentile score.
