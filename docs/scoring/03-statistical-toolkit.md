# 3. Statistical toolkit

The score methods share a small set of statistical devices. This document states
each one, says why it was chosen, shows what it does to small and large samples,
and names where it lives. The methods in [document 5](05-score-methods.md) are
compositions of these pieces.

## Proportions that keep their denominators

Every rate in the system is stored as a `FeatureObservation`
(`analytics/src/mtg_scorer/features.py`):

```text
value             estimate in [0, 1], or None for unknown
support           observations contributing to the estimate
opportunity_count eligible denominator, when the feature has one
```

`value` is `None`, never 0, when the numerator could not be observed: no games, no
known top-cut result, fewer than two labelled decks. The constructor rejects a
value outside [0, 1], a negative support, or a support larger than the
opportunity count. Keeping support and denominator beside the value is what lets
the methods shrink small samples correctly: a 100% win rate over 2 games and over
200 games are different observations with the same value.

## Shrinkage toward the field

Every rate that enters a score is first pulled toward the field's rate by a fixed
number of pseudo-observations. For a card with `n` observations whose observed
rate is `p`, a field rate `f` and a prior strength `k`:

```text
shrunk = (p * n + k * f) / (n + k)
       = w * p + (1 - w) * f        with  w = n / (n + k)
```

The card's evidence gets weight `w`, the field's prior gets `1 - w`. With `n = 0`
the shrunk rate is exactly the field's; as `n` grows it approaches the observed
rate. The strength `k` is the number of field-average observations every card is
assumed to carry.

This is the posterior mean of a Beta-Binomial model with a prior centred on the
field rate and worth `k` observations (a `Beta(k f, k (1 - f))` prior updated with
`p n` successes in `n` trials). The methods do not use anything else from that
model; only the mean is needed, and the interpretation as "add `k` field-average
games" is what the configuration comments say.

How much of the card's own rate survives, for the three strengths in use:

| Observations `n` | `k = 20` (top cuts, playsets use 5) | `k = 60` (games, Constructed and Signature) | `k = 100` (games, Hidden gem) |
| ---: | ---: | ---: | ---: |
| 1 | 0.048 | 0.016 | 0.010 |
| 5 | 0.200 | 0.077 | 0.048 |
| 10 | 0.333 | 0.143 | 0.091 |
| 20 | 0.500 | 0.250 | 0.167 |
| 60 | 0.750 | 0.500 | 0.375 |
| 100 | 0.833 | 0.625 | 0.500 |
| 300 | 0.938 | 0.833 | 0.750 |
| 1000 | 0.980 | 0.943 | 0.909 |

A card with two wins in two games under `k = 60` has a shrunk win rate of
`(2 + 30) / 62 = 0.516` against a 50% field, not 100%. A card with 60% over 200
games keeps `(120 + 30) / 260 = 0.577`. This single device is what makes "a tiny
sample is pulled toward the field" true in every method and is pinned by tests of
that name.

The prior strengths are deliberate, not fitted: 60 games is roughly a dozen
tournament decks' worth of Swiss rounds, 20 decks is a plausible count of known
top-cut results for a card seen at a few events, and the Hidden gem score uses 100
games because it searches the tail of the distribution, where luck gathers. They
live in each method's configuration dataclass and are part of its hash.

Two things shrinkage does not do. It does not widen into an interval: the methods
rank point estimates. And it does not know about correlation between a card's
games: the games of one deck's run through a tournament count as independent
observations.

## Mid-rank percentiles

`percentiles()` in `analytics/src/mtg_scorer/scoring/base.py` turns a mapping of
card to value into a mapping of card to a number in (0, 1):

```text
sort the cards by (value, card id)
for each run of tied values occupying 0-based positions start..end:
    rank       = (start + end) / 2 + 0.5
    percentile = rank / n
```

For `n` cards without ties the `i`-th card (1-based) gets `(i - 0.5) / n`: the
bottom card `0.5 / n`, the top card `1 - 0.5 / n`, and with odd `n` the middle card
exactly `0.5`. Ties share the mean of the positions they occupy, so ten cards tied
at the top all get the same percentile and none of them gets 100. The sort is by
value then card id, so reruns are identical.

| `n` | bottom | median | top |
| ---: | ---: | ---: | ---: |
| 3 | 16.7 | 50.0 | 83.3 |
| 10 | 5.0 | 45 / 55 | 95.0 |
| 100 | 0.5 | 49.5 / 50.5 | 99.5 |
| 5000 | 0.01 | 49.99 / 50.01 | 99.99 |

(With even `n` the two middle cards straddle 50.)

Properties worth knowing:

- A percentile is a statement about *position in this cohort*, not about the
  size of the underlying difference. The top card of a cohort where every card is
  within a hair of the field still scores near 100.
- A percentile depends on the population. Add or remove scored cards and every
  percentile moves; this is why basic lands are excluded before scoring and why
  the run file records the population rule.
- Nothing scores 100.000 exactly: the top of `n` cards scores `100 - 50 / n`. In a
  cohort of 5,000 cards that is 99.99, which rounds to an A+ grade either way.

## Percentile blends and the double percentile

The Constructed and Signature scores blend several components. Each component is
turned into a percentile on its own, then the percentiles are averaged by weight,
then the average is turned into a percentile again:

```text
for each component c with weight w_c:
    p_c = percentile of the card's value among the cards that have one
blend  = sum(w_c * p_c for known c) / sum(w_c for known c)
score  = 100 * percentile(blend)
```

Why percentiles before blending: the components live on different scales (a win
rate delta of a few points, a top-cut lift around 1.0, a meta share of a few
percent). Ranking each first makes a weight of 0.60 mean "60% of the say", not
"60% of some unit".

Why a component the card lacks is left out and the other weights rescaled: a card
without a known record is blended from its top-cut conversion and meta share
alone. The alternative, treating a missing component as the lowest or the median
percentile, would turn unavailability into a judgment. The test
`test_a_card_without_a_record_is_blended_from_what_is_known` pins this.

Why a percentile again at the end: the blend of percentiles is itself unevenly
distributed (a card that is median in everything blends to about 0.5, but the
blend's spread depends on how correlated the components are). The final percentile
restores the promise that 50 is the median scored card and that a score reads as
"better than this share of the cohort".

A consequence to keep in mind: the blend weights control *influence on order*,
not a decomposition of the final score. One cannot read a Constructed score of 80
as "48 points from win rate, 20 from top cuts, 12 from share".

## Saturation curves

Two shapes turn an unbounded count into a factor in [0, 1).

The **rational** form reaches half at a configured point `h` and is used where the
half point is the natural parameter:

```text
r(x) = x / (x + h)        r(h) = 0.5,  r(3h) = 0.75,  r(9h) = 0.9
```

- Hidden gem recurrence: `events / (events + 2)`; one event gives 0.33, two 0.5,
  eight 0.8.
- Overall format weight: `decks / (decks + 250)`; 50 decks give 0.17, 250 give
  0.5, 1,000 give 0.8, 5,000 give 0.95.

Its complement is the Hidden gem **rarity discount**, `1 / (1 + share / 0.02)`,
which is `1 - r(share)` with `h = 0.02`: a card in 2% of decks keeps half its
score, in 0.5% of decks 80%, in 20% of decks 9%, in 50% of decks 4%.

The **exponential** form is used by the Foundation model's evidence score:

```text
e(x) = 1 - exp(-x / s)    e(s) = 0.632,  e(s ln 2) = 0.5,  e(3s) = 0.95
```

with `s = 8` decks, 4 events and 40 full-field matches. It rises faster at first
and saturates harder than the rational form.

Both are monotone and bounded, so more evidence never lowers the factor and no
amount of evidence takes it past 1.

## Simpson's index without small-sample bias

The chance that two of a card's decks share an archetype is the card's **focus**.
With `n_i` decks under label `i` and `N = sum(n_i)` labelled decks:

```text
concentration = sum(n_i * (n_i - 1)) / (N * (N - 1))      defined for N >= 2
```

This is the probability that two decks drawn *without replacement* share a label.
The more familiar `sum((n_i / N)^2)` draws with replacement and is biased upward
for small `N`: a card seen in a single labelled deck would have concentration 1,
and two decks of one label would be certainty. Without-replacement sampling makes
one deck undefined (unknown, not 1) and two decks of one label exactly 1 only
because both were in fact that label, which the Signature score then shrinks
toward the field with a 10-deck prior. The same statistic over the whole cohort's
labelled decks is the field concentration.

The inverse, `1 / concentration`, is the number of equally played archetypes that
would give the same focus (the Hill number of order 2). The Signature score
publishes it as `effective_archetypes` because "2.4 archetypes" reads better than
"0.42".

## The 95% interval on a win rate

`card_performance` publishes a half-width beside every win rate:

```text
ci95 = 1.96 * sqrt(win_rate * (1 - win_rate) / games)
```

This is the normal approximation (Wald interval) for a proportion. It is shown as
"±" on the site and is purely descriptive: no score uses it. Its known weaknesses
apply: it collapses to zero at a win rate of 0 or 1, it is too narrow for small
`games`, and the games of a deck are not independent trials. A Wilson interval
would behave better at the extremes; see [document 8](08-limitations-and-future-work.md).

## Deltas and lifts against the field

A card's performance is always expressed relative to its cohort:

| Statistic | Formula | Reads as |
| --- | --- | --- |
| Win-rate delta | `win_rate - field_win_rate` | percentage points above or below the field |
| Top-cut lift | `(top_cut_count / top_cut_known_decks) / field_top_cut_rate` | 1.0 is the field's conversion; 1.5 is 50% better |
| Share delta | share of the newer half of the trend series minus the older half | points of meta share gained |
| Hidden gem result lift | `shrunk_rate / field_rate - 1` | relative gain; 0 is the field |

Deltas suit win rates because the field rate is a fixed baseline (50% or 25%).
Lifts suit top-cut conversion because the field's rate varies with how large the
cuts are relative to the fields; "converted 1.4 times as often" is comparable
across events with top 8s of 32 and top 16s of 200.

The descriptive statistics on the rankings page are **unshrunk**: the "vs field"
column and the "Top cut" lift show the raw observed rates. The scores use the
shrunk rates. A card can therefore show +12.0 points on the page and still grade
C, because 12 points over 6 games shrinks to a fraction of a point.

## Pooling across formats

When the overall run combines formats, only additive quantities are summed:
decks, events, top cuts and their known denominators, copies, wins, losses,
draws. Rates are pooled in a way that respects the formats' different baselines:

```text
pooled win-rate delta = sum(delta_f * games_f) / sum(games_f)
pooled top-cut lift   = sum(top_cut_count_f) / sum(top_cut_known_decks_f * field_rate_f)
```

The delta is a games-weighted average of each format's gap to its own field. The
lift is observed top cuts over the top cuts the fields' rates would have expected.
The raw win rate, the interval, the archetype and the trend series are left `None`
in the overall run.

## Rounding and determinism

- Published fractions are rounded to 4 decimals (`DIGITS = 4` in
  `tournament_features.py`) so reruns write identical files.
- Percentile scores keep 3 decimals so a population of thousands does not tie whole
  rows; the hidden-gem product keeps 6 because its magnitudes are tiny.
- Foundation outputs and the relative-volume ratio are rounded to 1 decimal and
  clamped to [0, 100].
- Ties are broken alphabetically everywhere a choice has to be made (archetype
  labels with equal counts, card names with equal counts, percentile ordering), so
  two runs over the same inputs are byte-identical.
- Scores are `float`; the API stores them as `double precision` and rejects
  infinities.
