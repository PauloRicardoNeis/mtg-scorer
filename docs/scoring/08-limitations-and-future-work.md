# 8. Limitations and open questions

The rankings are honest about their inputs, but a reader should know what the
numbers cannot say and where the statistics are deliberately simple. This
document collects those points, with the measurement contract's deferred research
at the end. Items are grouped by where they arise; none of them is hidden by the
code, and several are already surfaced on the site.

## What the data can support

- **Standings, not matches.** Every record comes from a deck's final standing
  (wins, losses, draws). No adapter produces round-level matches today, so the
  system cannot see who beat whom, cannot remove mirror matches, and cannot
  weight a win by the opponent's strength. `Match` exists in the domain for when
  a source provides it.
- **Mirror matches pull toward the field.** A card's games are counted per deck.
  When two decks that both play a card meet, the card records one win and one
  loss. The more a card dominates a cohort, the closer its win rate is forced to
  the field's, so a card in 70% of decks can show at most a small delta however
  strong it is. Meta share is the signal that remains, which is one reason the
  Constructed score includes it.
- **Games are not independent.** The games of one deck's run through a
  tournament share a pilot, a build and a day. Shrinkage and the interval treat
  them as independent trials, which overstates the evidence somewhat for cards
  concentrated in few decks.
- **Top cuts depend on inference.** Where the source lacks bracket columns the
  cut is read from the row order, and only when that order agrees with the Swiss
  records; otherwise the cut is unknown for the whole event. Each event states its
  basis, and the known-result denominator is kept beside every count, so the
  reader can see how much of a card's conversion rests on inference.
- **Coverage is a floor, not a correction.** An event with 60% of its lists
  published is in the cohort, and the 40% missing are assumed to resemble the 60%
  present. If the missing lists are systematically the losing ones (a common
  pattern when players withdraw lists), incidence is overstated for winning cards
  and understated for losing ones. The contract's distinction between full-field
  and partial coverage is recorded but not yet used to weight events.
- **Archetype labels are the source's.** TopDeck labels only 60-card formats and
  labels inconsistently across events; the Signature score inherits that
  inconsistency. Commander archetypes are exact by construction (the commander
  names the deck) but say nothing about the strategy beyond the commander.
- **Historical legality is not modelled.** A cohort window is chosen so the card
  pool is homogeneous enough; the pipeline does not check that a card was legal
  at each event, so a card banned mid-window simply stops appearing.
- **One source per run.** TopDeck and Wizards coverage are never mixed in a cohort
  and the overall run refuses components from different sources. Comparisons
  across eras are therefore comparisons across runs, by eye.

## Where the statistics are simple on purpose

- **Point estimates are ranked, not intervals.** A card's percentile is its
  shrunk point estimate's position. Two cards with overlapping intervals are
  still ordered. The prior strengths are the only guard against ranking noise,
  and they are fixed by hand rather than fitted. An empirical-Bayes fit of the
  prior strength per cohort (estimating the between-card variance of true win
  rates) would let the shrinkage adapt to formats where cards genuinely differ
  more or less.
- **The Wald interval** collapses at 0% and 100% and is too narrow under about
  30 games. It is descriptive only, but a Wilson or Jeffreys interval would be
  more honest on the page for cards with few games.
- **Percentiles hide magnitude.** A cohort where every card is within a point of
  the field still produces an A+ and an F. The score inputs are published so a
  reader can see that the top card's delta is +0.3 points, but the letter alone
  does not say so. A hybrid that scales the percentile by the spread of the
  shrunk deltas has been considered and rejected for now because it would make
  grades incomparable across formats, which the overall grade needs.
- **Blend weights are not a decomposition.** Because components are ranked
  before blending, 60/25/15 controls influence on order, not shares of the final
  number. Readers who want the pieces have the inputs.
- **The share component rewards popularity.** At 15% it is small, and it is
  also the only component immune to the mirror-match problem, but it means a
  card's grade can rise because more people chose it, not because it won more.
- **Ties in small cohorts are coarse.** A format with 40 scored cards has
  percentile steps of 2.5 points; grade bands are 5 points wide. The compare
  page's per-format ranks are more informative than letters in such formats.
- **The Hidden gem score multiplies noisy factors.** A product of four factors
  compounds their uncertainty; the 100-game prior and the zero floor for cards at
  or below the field are the mitigation. Its percentiles are taken among cards
  with a positive product, so a format with few such cards has a very coarse
  scale, and its scores are not comparable across formats (which is why it is
  not offered on the compare page).
- **The overall grade's constants** (250 decks for half weight, one format of a
  50) encode a judgment about how much breadth should count. They are explicit
  in the configuration and in the run's `components[].weight`, but nothing
  validates them against an external ground truth.
- **Rank movement compares runs with different populations.** A card's rank in
  the previous run is among that run's scored cards; a format that grew from
  1,000 to 1,400 scored cards makes most cards "fall" in rank with no change in
  standing. The page shows the counts, but the arrow does not normalise for it.

## The Foundation model

Its Staple score currently equals incidence and its Build-around signal is
always 0, because the tournament pipeline fills only one of its eleven inputs
(see [document 5](05-score-methods.md#foundation-model-foundation)). It remains
registered and published; it should either be retired from runs or fed the
features it was designed for. Both are tracked as research items below.

## Research the measurement contract still defers

These are specified in the [measurement contract](../measurement-contract.md)
and not implemented. Each would be a new feature pipeline version and, where it
feeds a score, a new method or configuration.

| Item | What it needs | What it would change |
| --- | --- | --- |
| Co-occurrence and package discovery | Pairwise card counts within a cohort; a regularised association statistic (smoothed log-lift, normalised PMI or prior-adjusted log odds) with pair support kept | `package_coherence` for the Foundation model; grouping adjacent build-around candidates into one strategy fingerprint instead of ten near-duplicate recommendations |
| Empirical deck clustering | Decklist-based clusters or externally versioned labels, applied consistently across sources and eras | `deck_family_breadth` and `specificity`; a Signature score that does not depend on TopDeck's labels; archetype pages for formats without labels |
| Multiple strata per card | Several cohorts (formats, eras, sources) scored and then joined on oracle id | `format_era_breadth` and `recurrence` across eras; a historical reach beyond one window per format |
| Round-level matches | A source that publishes pairings and results (TopDeck's round data, Wizards' round pages already parsed for records) | `competitive_proof` from matches; mirror-match removal; opponent-adjusted win rates; `full_field_match_count` for the Evidence score |
| Coverage-aware weighting | Using each event's decklist/standings/match coverage scope beyond the 50% floor | `coverage_strength`; down-weighting partial events rather than including them at par |
| Historical legality | A versioned legality dataset by format and date | Opportunity denominators that count only decks in which the card was a legal option |
| Sideboard usage | The sideboard copies already stored per deck | A sideboard incidence feature, kept separate from mainboard usage as the contract requires |
| Calibration study | A set of sentinel cards per format with agreed pairwise expectations, maintained as tests | Regression protection for every method; evidence for or against the fixed prior strengths |

## Questions a reader may ask

**Why not fit the weights to something?** There is no ground truth for "how good
a card is". The contract's position is that weights are judgments, must be
explicit and versioned, and are checked by pairwise sentinel tests rather than
fitted. Fitting to, say, prices or public tier lists would import their biases.

**Why percentiles rather than a model-based probability?** Percentiles make
every format's grade mean the same thing (position in its own field), which the
overall grade and the compare page rely on. A probability that a card's true win
rate exceeds the field's would be a sound alternative for a single format but
would be dominated by sample size: staples would always be near 1 and rare cards
near 0.5.

**Why is the median 50 and not the field?** A field-relative score of 50 would
mean "exactly the field's results". With percentiles 50 means "the median scored
card", which is usually a card slightly above the field, because the scored
population excludes the decks' worst cards only insofar as losing decks publish
lists less often. The inputs show the field-relative figure.

**Can a card be graded A+ in a format of three events?** Yes. The grade is a
percentile and the cohort is whatever passed the rules. The page shows the
decklists, players, matches and events behind the run so the reader can weigh
it, and the overall grade weights that format at `decks / (decks + 250)`.
