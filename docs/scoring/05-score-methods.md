# 5. Score methods

A score method is a versioned, configured, deterministic function from one
cohort's `ScoringInput`s to a `ScoreRun`. The contract is in
`analytics/src/mtg_scorer/scoring/base.py`; the registry in `registry.py` lists
the five methods that run on every cohort, and `overall.py` holds the sixth,
which runs over finished runs rather than over a cohort.

| Method id | Label | Outputs | Scale | Where shown |
| --- | --- | --- | --- | --- |
| `constructed-score` | Constructed score | `score` | 0-100 percentile, 3 dp | Default grading of every format; the component of the Overall grade; compare page |
| `signature-score` | Signature score | `score` | 0-100 percentile | Grading menu; compare page |
| `hidden-gem-score` | Hidden gem score | `score` | 0-100 percentile, with 0 and `None` | Grading menu |
| `max-ratio` | Relative volume | `max_ratio` | 0-100 ratio, 1 dp | Grading menu; the API's fallback method |
| `foundation` | Staple, Build-around and Evidence | six outputs | 0-100 weighted means | Published in every run; not offered on the site |
| `overall-grade` | Overall grade | `score` | 0-100 percentile | The "Overall" format |

Every method obeys the same rules, checked by `tests/test_score_methods.py` for
each registered one:

- it scores every card of the population exactly once and returns exactly its
  declared outputs for each;
- an output is `None` when the card cannot be scored, never a stand-in zero;
- it is deterministic: the same inputs give the same run;
- its `version` and `config_hash` come from a frozen configuration dataclass,
  so a changed setting changes the identity;
- it publishes the inputs that explain each score.

The configuration defaults quoted below are the current values in each method's
dataclass. Changing any of them is a new configuration with a new hash; the
version label should be bumped at the same time so the change is visible by name.

---

## Constructed score (`constructed-score`)

File: `analytics/src/mtg_scorer/scoring/constructed.py`. Version
`constructed-score-v1`.

**Question.** How well do the decks that play this card perform against the
field, and how much of the field plays it?

**Configuration.**

| Setting | Default | Role |
| --- | ---: | --- |
| `win_rate_weight` | 0.60 | weight of the win-rate component |
| `top_cut_weight` | 0.25 | weight of the top-cut component |
| `share_weight` | 0.15 | weight of meta share |
| `win_rate_prior_games` | 60 | pseudo-games of field-average evidence added to every card |
| `top_cut_prior_decks` | 20 | pseudo-decks of field-average conversion added to every card |

The weights must be non-negative and sum to 1; the priors non-negative.

**Algorithm.** For every card:

```text
if win_rate known and field_win_rate known:
    games   = win_rate.support
    points  = win_rate.value * games
    shrunk  = (points + 60 * field_win_rate) / (games + 60)
    win_delta = shrunk - field_win_rate

if top_cut_rate known and field_top_cut_rate > 0:
    known   = top_cut_rate.support
    made    = top_cut_rate.value * known
    shrunk  = (made + 20 * field_top_cut_rate) / (known + 20)
    cut_lift = shrunk / field_top_cut_rate

if incidence known:
    share = incidence.value
```

Then, over the population:

```text
P_win   = percentiles(win_delta)      among cards that have one
P_cut   = percentiles(cut_lift)
P_share = percentiles(share)

blend[c] = (0.60 P_win[c] + 0.25 P_cut[c] + 0.15 P_share[c]) / (sum of the weights of the components c has)
score[c] = 100 * percentiles(blend)[c], rounded to 3 decimals
```

A card with none of the three components (impossible for a card in the
population, since incidence is always known) would have `None`.

**Published inputs.** `win_rate_delta` (shrunk, 4 dp), `top_cut_lift` (shrunk),
`meta_share`, `blend`.

**Behaviour the tests pin** (`tests/test_constructed_score.py`):

- a better win rate scores higher when all else is equal;
- the median card scores 50;
- two wins in two games rank below 60% over two hundred games;
- a card without a record is blended from what is known and still has a score;
- top-cut conversion is compared with the field (lift above and below 1).

**Reading a score.** 50 is the median scored card of that cohort. Because the
components are percentiles, the score says where the card sits, not by how much.
The share component means that, between two cards with identical shrunk results,
the more played one scores higher; at 15% it is a tie-breaker and a mild
popularity prior, not a volume ranking. The 60/25/15 split expresses that match
results are the primary evidence, conversion is a coarser view of the same thing
(it is correlated with win rate but adds the bracket), and share is the weakest
signal of quality.

**What it cannot see.** It knows nothing about *why* the decks won; a card in a
dominant archetype inherits that archetype's results. See the Signature score for
the complementary question, and [document 8](08-limitations-and-future-work.md).

---

## Signature score (`signature-score`)

File: `analytics/src/mtg_scorer/scoring/signature.py`. Version
`signature-score-v1`.

**Question.** How much does this card belong to one strategy? A staple played
everywhere should rank low however strong it is; a card most of one archetype
plays, and little else does, should rank high.

**Configuration.**

| Setting | Default | Role |
| --- | ---: | --- |
| `focus_weight` | 0.50 | weight of archetype focus |
| `reliance_weight` | 0.30 | weight of home-archetype reliance |
| `win_rate_weight` | 0.20 | weight of the shrunk win-rate delta |
| `focus_prior_decks` | 10 | pseudo-decks of field-like concentration added to every card's focus |
| `adoption_prior_decks` | 10 | pseudo-decks of the card's own overall share added to its home adoption |
| `win_rate_prior_games` | 60 | as in the Constructed score |

**Eligibility.** A card is scored only when `archetype_adoption` is known, that
is, when at least one of its decks has an archetype. Without labels its spread
across strategies is unknown, not zero, so cards in a cohort without labels have
no Signature score, and a format whose source carries no labels is marked "needs
archetype labels" on the site.

**Algorithm.** For every eligible card:

```text
focus:
    F = field_archetype_concentration            (skip the component if None)
    n = archetype_concentration.support if known else 0
    c = archetype_concentration.value   if known else 0
    focus = (c * n + 10 * F) / (n + 10)

adoption and reliance:
    played   = incidence.value
    adoption = (home.support + 10 * played) / (home.opportunity + 10)
    reliance = adoption - played

win_delta: as in the Constructed score, prior 60 games.
```

Then percentiles of `focus`, `reliance` and `win_delta` among the eligible cards,
a weighted blend 0.50/0.30/0.20 over the components the card has, and a final
percentile × 100.

**Published inputs.** `focus`, `effective_archetypes` (= 1/focus, 2 dp),
`adoption`, `reliance`, `win_rate_delta`, `blend`.

**Why each component is shaped this way.**

- *Focus* is the without-replacement Simpson index of the card's labelled decks,
  shrunk toward the field's concentration. A card with one labelled deck has no
  concentration of its own and starts exactly at the field's: a card with no
  preference among archetypes. Two decks of one archetype give concentration 1
  but only 2 of the 12 effective decks, so focus is `(2 + 10 F) / 12`, a little
  above the field. Forty decks of which 36 share a label and four differ give
  concentration 0.81 and, with a 5% field, focus `(0.81·40 + 0.5) / 50 = 0.66`.
  `test_two_decks_of_one_archetype_are_weaker_evidence_than_forty` pins this.
- *Adoption* is the share of the home archetype's decks that play the card,
  shrunk toward the card's share of *all* decks. The prior is the card's own
  overall share rather than the field's, because the question is "does this
  archetype play it more than decks in general do". *Reliance* is the difference.
  A staple in 60% of all decks and 18 of its home archetype's 20 decks has
  adoption `(18 + 6) / 30 = 0.80` and reliance 0.20; a card in 5% of decks and
  the same 18 of 20 has adoption `(18 + 0.5) / 30 = 0.62` and reliance 0.57.
  `test_a_staple_ranks_below_a_card_its_archetype_relies_on` pins this.
- *Win rate* enters at 20% so that, among equally distinctive cards, the one
  whose decks win ranks higher, without letting results dominate distinctiveness.

**Reading a score.** 50 is the median eligible card. High scores name cards that
define a strategy; they are not claims that the card *caused* the strategy, which
the measurement contract forbids inferring from decklists. A commander in a
commander format is fully focused by construction and is scored like a card that
names a labelled archetype.

---

## Hidden gem score (`hidden-gem-score`)

File: `analytics/src/mtg_scorer/scoring/hidden_gem.py`. Version
`hidden-gem-score-v1`.

**Question.** Which cards almost nobody plays still earn their place: the decks
that play one play a full playset, those decks beat the field, and they do so at
more than one event?

**Configuration.**

| Setting | Default | Role |
| --- | ---: | --- |
| `win_rate_weight` | 0.70 | weight of win-rate lift inside the result factor |
| `top_cut_weight` | 0.30 | weight of top-cut lift inside the result factor |
| `playset_prior_decks` | 5 | pseudo-decks of field-like playset share added to every card |
| `win_rate_prior_games` | 100 | stronger than the Constructed score's 60: gems come from the tail, where luck gathers |
| `top_cut_prior_decks` | 20 | as in the Constructed score |
| `half_recurrence_events` | 2 | events at which the recurrence factor is 0.5 |
| `half_score_share` | 0.02 | meta share at which the rarity discount halves the score |
| `min_field_playset_rate` | 0.05 | below this pooled playset share the cohort is singleton and nothing is scored |

**Singleton detection.** Over the cards with a known playset rate:

```text
field_playsets = sum(playset_rate.support) / sum(playset_rate.opportunity)
singleton      = field_playsets < 0.05
```

In a singleton cohort every card's score is `None`: copies say nothing about
commitment there. One Relentless Rats deck among a hundred singleton decks does
not make the cohort scoreable (`test_a_few_playsets_in_a_singleton_format_do_not_make_it_scoreable`).

**Algorithm.** For every card with known playset rate and incidence:

```text
win_lift  = shrunk_win_rate(prior 100) / field_win_rate - 1        if known and field > 0
cut_lift  = shrunk_cut_rate(prior 20)  / field_top_cut_rate - 1    if known and field > 0
lift      = (0.70 win_lift + 0.30 cut_lift) / (sum of the weights present)
            -> no score if neither is known

playsets   = (playset.support + 5 * field_playsets) / (playset.opportunity + 5)
recurrence = events / (events + 2)                                 (0 when events = 0)
rarity     = 1 / (1 + incidence / 0.02)

gem = playsets * lift * recurrence * rarity
```

Then:

```text
ranks = percentiles({card: gem for cards with gem > 0})
score = 100 * ranks[card]  (3 dp)   if gem > 0
      = 0.0                         if gem <= 0 (decks do no better than the field)
      = None                        if the card was not scored at all
```

**Published inputs.** `playset_rate` (shrunk), `win_rate_lift`, `top_cut_lift`,
`result_lift`, `recurrence`, `rarity`, `gem` (6 dp).

**Why a product, and why percentiles only at the end.** The four factors are
multiplied so a card needs all of them: a four-of with no results, or a winner
played as a one-of, or a staple that wins, each loses most of its score to the
factor it lacks. Unlike the other methods the factors keep their magnitudes until
the end, because among thousands of cards seen once or twice a per-component
percentile would turn a tiny lucky edge into a high rank. Cards whose decks do no
better than the field get exactly 0 rather than a low percentile: there is nothing
to rank among them. The percentile is taken only among the cards that look like a
gem at all, so 50 is the median of those.

**The factors in numbers.**

| Factor | 1 | 2 | 4 | 8 | 20 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recurrence at that many events | 0.33 | 0.50 | 0.67 | 0.80 | 0.91 |

| Meta share | 0.5% | 1% | 2% | 5% | 10% | 25% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rarity | 0.80 | 0.67 | 0.50 | 0.29 | 0.17 | 0.07 |

**Behaviour the tests pin** (`tests/test_hidden_gem_score.py`): a rare four-of
outranks a staple with the same results; four-of beats one-of; cards at or below
the field score 0; the median of the rest scores 50; one lucky deck ranks below a
card that keeps winning; each factor is 0.5 at its configured point; top-cut
conversion alone can show success; a card without any known result has no score;
singleton formats have no scores.

---

## Overall grade (`overall-grade`)

File: `analytics/src/mtg_scorer/scoring/overall.py`, assembled by
`publish/overall_run.py`. Version `overall-grade-v1`.

**Question.** Taking every format at once, how good is this card? The per-format
Constructed scores are already percentiles against their own fields, so they are
comparable; the overall grade averages them with two corrections.

**Configuration.**

| Setting | Default | Role |
| --- | ---: | --- |
| `component_method`, `component_output` | `constructed-score`, `score` | which per-format output is combined |
| `half_weight_decks` | 250 | a format with this many decklists counts half as much as an unlimited one |
| `prior_formats` | 1 | formats' worth of a median score added to every card |
| `prior_score` | 50 | that median score |

**Algorithm.**

```text
weight(format) = decks / (decks + 250)             (formats with 0 decks are ignored)

for each card graded in at least one format:
    weighted = sum(weight_f * score_f)
    evidence = sum(weight_f)
    blend    = (weighted + 1 * 50) / (evidence + 1)

score = 100 * percentiles(blend)   among every graded card
```

**Published inputs.** `blend`, `evidence` (the summed weights), `formats` (how
many formats graded the card).

**What the two corrections do.**

- *Evidence weighting.* A format with a few dozen decklists barely moves a card,
  while every format with thousands counts about the same: 50 decks weigh 0.17,
  250 weigh 0.5, 1,000 weigh 0.8, 5,000 weigh 0.95. The curve saturates so a
  single huge format cannot swamp the others.
- *The median prior.* Every card carries one format's worth of a 50. A card
  graded 90 in one 1,000-deck format blends to `(0.8·90 + 50) / 1.8 = 67.8`; the
  same card graded 90 in three such formats blends to `(2.4·90 + 50) / 3.4 =
  78.2`. Breadth of proof is rewarded; a specialist strong in a single format is
  not penalised below the median, only held nearer to it.
  `test_a_card_proven_in_many_formats_outranks_one_strong_in_a_single_format`
  pins the order staple > specialist > filler.

A format that does not grade a card is no evidence, never a zero: a card may be
illegal there. The final percentile is among every card graded anywhere, so a
card from a small format alone is ranked against cards from every format.

**What the overall run pools** (see [document 3](03-statistical-toolkit.md#pooling-across-formats)):
counts are summed; the win-rate delta is a games-weighted average of each
format's delta; the top-cut lift is top cuts made over expected; the raw win rate,
the interval, the archetype and the trend are left unknown. The run's identity
hashes its component run ids, and each of those already pins everything that
produced it.

---

## Relative volume (`max-ratio`)

File: `analytics/src/mtg_scorer/scoring/max_ratio.py`. Version `max-ratio-v1`.

**Question.** How often was the card played, compared with the most played card?

```text
max_ratio = 100 * count / max(count over the population)   (1 dp)
          = None when the largest count is 0
```

`count` is the configured measure, `deck_count` by default (`event_count` and
`full_field_match_count` are the other options). It is deliberately descriptive:
it measures volume, not quality, and it moves whenever the leading card changes.
The site's lead text for this grading says so. It is the API's fallback method
for a run that lacks the Constructed score and is why basic lands are excluded
from the population. Published inputs: `count`, `max_count`.

---

## Foundation model (`foundation`)

File: `analytics/src/mtg_scorer/scoring/foundation.py`. Version `foundation-v2`.

This is the project's original model, kept as a registered method so it keeps
running under the shared contract. It implements the three-score design in the
README (Staple, Build-around, Evidence) over the measurement contract's full
feature list.

**Configuration.** Three weight groups, each summing to 1:

| Staple | | Build-around | | Evidence | |
| --- | ---: | --- | ---: | --- | ---: |
| incidence | 0.35 | specificity | 0.25 | decks (scale 8) | 0.30 |
| deck_family_breadth | 0.25 | package_coherence | 0.25 | events (scale 4) | 0.25 |
| format_era_breadth | 0.15 | commitment | 0.15 | full-field matches (scale 40) | 0.20 |
| competitive_proof | 0.20 | competitive_proof | 0.20 | source coverage | 0.15 |
| commitment | 0.05 | recurrence | 0.10 | feature availability | 0.10 |
| | | choice_freedom | 0.05 | | |

**Algorithm.**

```text
weighted_estimate(group):
    known    = the group's features whose value is not None
    coverage = sum of their weights
    estimate = sum(value * weight) / coverage      (0 if coverage is 0)
    return 100 * estimate, coverage

staple, staple_coverage           = weighted_estimate(staple group)
buildaround, buildaround_coverage = weighted_estimate(buildaround group)   (both 0 if deck_count == 0)

evidence = 100 * ( 0.30 (1 - e^(-decks/8))
                 + 0.25 (1 - e^(-events/4))
                 + 0.20 (1 - e^(-full_field_matches/40))
                 + 0.15 coverage_strength (0 if unknown)
                 + 0.10 (staple_coverage + buildaround_coverage) / 2 )

distinctiveness_delta = buildaround - staple
```

Outputs are rounded to 1 decimal and clamped to [0, 100]; the two coverages are
published as percentages.

**Reweighting around unknowns** is the model's distinctive idea: a group's
estimate is the weighted mean of the features that were observed, and the
coverage says how much of the configured weight that was. A card with 100
Build-around at 25% coverage is not equivalent to one at 100% coverage.

**Status today.** The tournament feature pipeline fills only `incidence` of the
features these groups use (see [document 4](04-features.md#features-the-pipeline-does-not-fill)),
and never sets `full_field_match_count` or `coverage_strength`. In every current
run, therefore:

- `staple = 100 × incidence`, with `staple_feature_coverage = 35.0`;
- `buildaround_signal = 0.0` with `buildaround_feature_coverage = 0.0`;
- `distinctiveness_delta = -staple`;
- `evidence` is at most `100 × (0.30 + 0.25 + 0.10 × 0.175) = 56.75`.

The method is published in every run for continuity and because its contract
tests exercise the registry, but the site does not offer it as a grading. Its
pairwise tests in `tests/test_scoring.py` (obscurity alone does not create a
build-around signal; one coherent success can be high signal but low evidence;
broad repeated usage produces a high staple score) are written against
hand-built feature vectors and still pass, which is what they protect.

---

## Adding or changing a method

1. Create a module with a frozen configuration dataclass (a `version` label plus
   settings, hashed with `config_fingerprint`) and a method class providing
   `method_id`, `label`, `description`, `outputs`, `version`, `config_hash` and
   `score()`. Finish `score()` with `build_run`, which checks the declared
   outputs.
2. Register an instance in `SCORE_METHODS` (`scoring/registry.py`). The shared
   contract tests then cover it.
3. Write pairwise tests in the measurement contract's style: sentinel inputs and
   the orderings they must produce, not sacred target numbers.
4. If the site should offer it, add its id to `GRADINGS` and, if its scale is a
   0-100 percentile, to `GRADED_METHODS` in `web/src/components/ranking-data.tsx`;
   if it should be comparable across formats, to `CompareQuery.METHODS` in the
   API.
5. Rescore and republish. The run id changes because the method identities are
   part of it; the previous run stays published and the site's "movement" column
   compares against it only when it holds the same method.

A changed weight is a new configuration. Bump the version label with it so the
change is visible in run summaries, not only in the hash.
