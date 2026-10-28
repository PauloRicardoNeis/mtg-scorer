# Research note: a Constructed score v2 prototype (2026-10-28)

Two statistical changes to the Constructed score were prototyped against the
published score runs and compared with `constructed-score-v1`. Nothing here is
registered as a method or published; the prototype is
[`scripts/prototype_constructed_v2.py`](../../../scripts/prototype_constructed_v2.py)
and its raw output for Modern and EDH is
[`constructed-v2-prototype-report.md`](constructed-v2-prototype-report.md).

```bash
python scripts/prototype_constructed_v2.py analytics/data/local/score-runs/<run>.json
python scripts/prototype_constructed_v2.py --survey analytics/data/local/score-runs
```

The script needs a run with a deck list (`card-usage-v7` or later): the
within-archetype contrast is computed from the run's decks, which the feature
pipeline does not yet carry per card.

## Why

[Document 8](../08-limitations-and-future-work.md) lists two weaknesses the
prototype addresses. The prior strengths (60 games, 20 decks) are fixed by hand, and
nothing checks them against the between-card variance a cohort actually shows. And
every method measures a card by the pooled results of the decks that happen to
contain it, which is mostly the archetype's result: a mediocre card in the best deck
grades A. A reader asking "is this card good" is asking about the card's marginal
contribution, which the field delta cannot separate from the deck's.

## What was tried

**Fitted priors.** The prior strength `k` that shrinks a card's win rate toward the
field is the beta-binomial maximum marginal likelihood estimate with the mean fixed at
the field rate, over every scored card's (points, games). The top-cut prior is fitted
the same way over (made, known). A fit that runs to its upper bound (100,000) means
the observed spread across cards is no wider than binomial noise: the cohort cannot
tell its cards apart on that statistic, and the component is dropped from the blend
instead of ranking noise. Both fitters recover known strengths on synthetic data
(true 20, 60, 300 fitted as 19, 57, 283; no variance fitted as the bound).

**Within-archetype delta.** For each archetype that has decks both with and without
the card, the contrast `d_a = rate(with) − rate(without)` is weighted by its
precision `w_a = n_with · n_without / (n_with + n_without)` and pooled over the
card's archetypes. The pooled delta is shrunk toward 0 by a random-effects variance
fitted by maximum likelihood (`d ~ N(0, τ² + f(1−f)/Σw)`), expressed as an
equivalent prior in games. A card whose contrast rests on fewer than 30 effective
games has no within delta rather than a weak one, because a near-zero shrunk value
would read as "median card" and pull down a card that merely has nothing to be
compared against (a commander, an archetype's defining card). The comparison is
leave-one-out, so an archetype every one of whose decks plays the card contributes
nothing.

**The blend.** v2 ranks field delta 35%, within-archetype delta 25%, top-cut lift
25% and meta share 15%, with missing components renormalised as in v1, then takes a
percentile of the blend as v1 does. Three rankings are compared: v1 as published,
v1 with the fitted priors only, and v2.

The reimplemented v1 reproduces the published scores exactly (Spearman 1.000, top
50 identical) in both cohorts, so the differences below are the changes, not the
reimplementation.

## Results

### Modern, 2024-01 to 2026-10 (667 decks, 939 scored cards, median 14 games per card)

| | fitted | v1 |
| --- | ---: | ---: |
| win-rate prior | 323 games | 60 games |
| top-cut prior | no between-card variance; dropped | 20 decks |
| within-archetype τ | 1.1 points; equivalent prior 1,997 games | not used |
| cards with a contrast of at least 30 effective games | 148 of 939 | |

| comparison | Spearman | top 50 overlap |
| --- | ---: | ---: |
| v1 vs v1 with fitted priors | 0.952 | 32 / 50 |
| v1 vs v2 | 0.943 | 28 / 50 |

Three findings.

- **The fitted win-rate prior is five times the hand-set one.** With mirror matches
  pulling every staple toward 50%, cards genuinely differ less than 60 games of
  shrinkage assumes. Cards that led v1 on 6 to 25 decks with +8 to +19 raw points
  (Springleaf Drum, Skateboard, Claws of Gix, Haliya) fall to the 60s to 100s;
  cards with hundreds of games and +2 to +5 points (Sacred Foundry, Phlage, Fable,
  Steam Vents) rise into the top 25. This is the sample-size correction working.
- **Top-cut conversion carries no card-level signal in Modern.** The variance of
  observed conversion across cards is *below* binomial noise (0.059 against 0.089
  over all cards; 0.0032 against 0.0036 among the 137 cards with 30 or more known
  results). Top-cut results within an event are not independent trials (at most
  eight decks make the cut), and a quarter of the field's results are unknown. The
  gate drops the component. In v1 it is 25% of the blend.
- **The within-archetype contrast is too thin in a 667-deck cohort.** Only 148 cards
  have 30 effective games of contrast, and the fitted τ of 1.1 points means the
  shrunk deltas are ordered mostly by evidence. The component changes little here
  and should not be weighted at 25% in a cohort this size.

### EDH, 2025-10 to 2026-10 (83,339 decks, 20,534 scored cards, median 30 games per card)

| | fitted | v1 |
| --- | ---: | ---: |
| win-rate prior | 21 games | 60 games |
| top-cut prior | 51 decks | 20 decks |
| within-archetype τ | 2.0 points; equivalent prior 474 games | not used |
| cards with a contrast of at least 30 effective games | 8,299 of 20,534 | |

| comparison | Spearman | top 50 overlap |
| --- | ---: | ---: |
| v1 vs v1 with fitted priors | 0.970 | 47 / 50 |
| v1 vs v2 | 0.930 | 34 / 50 |

- **The fitted win-rate prior is a third of the hand-set one.** In four-player pods
  with a 25% field rate and commander-defined archetypes, cards differ more than
  60 games of shrinkage assumes. The top 50 barely moves, because the leaders
  already have thousands of games.
- **The within-archetype contrast is informative here.** τ = 2 points on a 25%
  base rate, measured on 8,299 cards. It separates two kinds of card that v1 grades
  alike. Cards that *ride* a strong commander fall: Corridor Monitor (rank 30 to
  1,765), Arcum Dagsson (31 to 1,671), Silver Myr (28 to 639), Combat Courier,
  Tomb Trawler and Simulacrum Synthesizer all have +4.5 to +5.6 field points and a
  within-archetype contrast of −1.4 to +1.2: the decks of the same commander do as
  well without them. Cards whose decks win *because of them* rise: Disrupting
  Shoal (52 to 10, +4.1 within over 13,702 effective games and 127 commanders),
  Snapback, Hidden Strings, Sculpting Steel, Nexus of Becoming.
- **Commanders lose their standing by design.** Kraum (17 to 686) and Scion of the
  Ur-Dragon (22 to 1,127) name their own archetype, so every deck of it plays them
  and the leave-one-out contrast has nothing to compare; what remains is their
  record in other decks' 99. A commander's quality is the archetype's, which the
  commander page already ranks. v2 should exclude commander cards from the within
  component (treat them as unknown), or the Constructed score should not grade
  commanders at all.

### Every cohort with a deck list

The `--survey` run fits the priors for every cohort whose latest run carries a deck
list. "Dropped" means the fit found no between-card variance beyond sampling noise.

| format | window | decks | cards | median games | win prior (v1 60) | top-cut prior (v1 20) | within τ (points) | within prior (games) | v1 vs v2 top 50 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EDH | 2025-10 to 2026-10 | 83,339 | 20,534 | 30 | 21 | 51 | 2.0 | 474 | 34/50 |
| Legacy | 2024-01 to 2026-10 | 2,936 | 1,363 | 19 | 268 | 261 | 2.0 | 601 | 26/50 |
| Pauper | 2024-01 to 2026-10 | 2,448 | 1,505 | 15 | 99 | dropped | 3.2 | 251 | 30/50 |
| Premodern | 2024-01 to 2026-10 | 1,598 | 1,016 | 21 | 420 | 216 | 2.5 | 391 | 30/50 |
| Modern | 2024-01 to 2026-10 | 667 | 939 | 14 | 323 | dropped | 1.1 | 1,997 | 28/50 |
| Vintage | 2024-01 to 2026-10 | 429 | 2,760 | 6 | 1,934 | dropped | 5.1 | 95 | 14/50 |
| 7pt Highlander | 2024-07 to 2026-10 | 265 | 1,634 | 11 | 361 | dropped | dropped | | 27/50 |
| Pauper EDH | 2024-01 to 2026-10 | 233 | 3,441 | 7 | 850 | dropped | dropped | | 26/50 |
| Canadian Highlander | 2025-01 to 2026-10 | 208 | 2,009 | 11 | dropped | 206 | dropped | | 15/50 |
| Standard | 2024-01 to 2026-10 | 114 | 818 | 6 | 46 | 162 | dropped | | 46/50 |
| Duel Commander | 2024-07 to 2026-10 | 106 | 2,381 | 7 | 64 | dropped | dropped | | 37/50 |
| Casual EDH | 2026-07 to 2026-10 | 98 | 2,395 | 6 | dropped | dropped | dropped | | 6/50 |
| Old School 93/94 | 2025-01 to 2026-10 | 32 | 157 | 11 | 195 | dropped | dropped | | 40/50 |
| Tiny Leaders | 2025-01 to 2026-10 | 28 | 650 | 4 | dropped | dropped | dropped | | 15/50 |
| Sealed | 2025-07 to 2026-10 | 5 | 122 | 4 | dropped | dropped | dropped | | 29/50 |

What the survey adds to the two detailed cohorts:

- **No cohort's data support 60 games.** Where the win-rate prior can be fitted it
  ranges from 21 (EDH) to 1,934 (Vintage). The 60-card formats with a few hundred to
  a few thousand decks sit at 100 to 400 games; a fixed 60 lets small samples rank
  far too high in all of them.
- **Top-cut conversion has no card-level signal in 10 of 15 cohorts**, including
  Pauper with 2,448 decks. It survives only in EDH, Legacy, Premodern, Standard and
  Canadian Highlander. At 25% of the v1 blend it is mostly ranking noise.
- **Four cohorts cannot grade performance at all** (Tiny Leaders, Sealed, Casual
  EDH, Canadian Highlander): no component beyond meta share has detectable
  between-card variance. v1 prints A+ to F letters there; v2 would rank by share
  alone, which is why Casual EDH keeps only 6 of its top 50. These cohorts should
  say so on the page rather than grade.
- **The within-archetype contrast needs volume and exact labels.** It is fitted with a
  usable τ only in the five cohorts with 600 or more labelled decks, and Vintage's
  5.1 points on 95 games of prior should be read with its 6-game median in mind.

## Caveats

- **Cards are not independent observations.** A 60-card deck contributes to about 40
  cards' records, so the beta-binomial likelihood overstates its sample size. The
  point estimates of `k` are unbiased in expectation; their uncertainty is not
  computed.
- **Heteroscedasticity.** Staples vary less than rare cards (mirror matches), so one
  `k` per cohort is a compromise. A prior strength that depends on incidence is the
  next refinement; it would also replace the Hidden gem score's separate 100-game
  prior with a fitted one.
- **Decks without a staple are selected, not random.** Within an archetype, the decks
  that omit a near-universal card are often budget or mislabelled builds, which
  biases the contrast in the card's favour. The precision weighting limits how much
  such a contrast can count but does not remove the bias; the 30-effective-game
  floor removes the thinnest cases.
- **Labels are the source's.** TopDeck's Modern archetype labels split one strategy
  into several names (Esper, Jeskai, Orzhov, Azorius Blink) and merge others. In
  commander formats the archetype is exact by construction, which is one reason the
  contrast works far better in EDH.
- **The floor is a constant.** 30 effective games was chosen by eye after seeing the
  46-game Kraum contrast rank a commander by its record in the 99. A principled
  version would carry the contrast's standard error into the blend instead.

## Recommendation

1. **Adopt fitted priors with the no-variance gate** in the Constructed, Signature
   and Hidden gem scores as a `v2` configuration. It is a small change to each
   method (one fit per component per cohort, exposed in the run's method config and
   `inputs`), fixes a documented weakness, and the evidence above shows the hand-set
   60 is wrong by a factor of 3 to 5 in both directions.
2. **Add the within-archetype delta as a feature** (`CardFeatures.within_archetype_delta`
   with its effective games as support) in a new feature pipeline version, computed
   from the per-archetype records the cohort already has. Blend it into the
   Constructed score only where the cohort's fitted τ is above a floor and the card
   is not a commander; otherwise leave the component unknown. In EDH it is the
   first statistic that separates a card's contribution from its deck's.
3. **Let the gate decide the top-cut component per cohort** rather than fixing its
   weight at 25%. The survey finds no card-level variance in conversion in 10 of 15
   cohorts; where it is dropped the other weights renormalise as they already do for
   an unknown component. A cohort where every performance component is dropped
   should publish no letter grade.
4. **Document in `03-statistical-toolkit.md`** the fitting procedure and the gate
   when either lands, and add the recovered-strength synthetic checks as tests.
