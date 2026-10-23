# 4. Features

A feature is one number about one card inside one cohort, with the support that
backs it. `card_features()` in `analytics/src/mtg_scorer/tournament_features.py`
builds the `CardFeatures` vector the score methods consume; `card_performance()`
builds the descriptive statistics the site shows. Both read the same `CardUsage`
and `CohortPerformance`.

The example values below come from the [worked example](07-worked-example.md): a
synthetic two-event Modern cohort of 8 decks, with 5 cards, in which the field's
win rate is 0.5952, its top-cut rate 0.6 (3 of 5 known results) and its archetype
concentration 0.25.

## Per-card usage (`CardUsage`)

Counted from the cohort's complete-mainboard decks only. A card is "in" a deck
when it has mainboard copies there.

| Field | Definition | Bolt in the example |
| --- | --- | ---: |
| `deck_count` | decks with the card | 6 |
| `event_count` | distinct events among those decks | 2 |
| `mainboard_copies` | total mainboard copies across its decks | 22 |
| `playset_deck_count` | its decks with at least 4 mainboard copies (`PLAYSET_COPIES`) | 5 |
| `top_cut_count` | its decks with a known result that made the cut; `None` when no result is known | 3 |
| `top_cut_known_decks` | its decks with a known top-cut result | 4 |
| `archetype_label`, `archetype_deck_count` | the most common label among its labelled decks and how many of its decks carry it; ties go to the alphabetically first label | Burn, 3 |
| `labelled_deck_count` | its decks that have any archetype | 6 |
| `archetypes` | up to three (label, decks) pairs, most decks first (`TOP_ARCHETYPES`) | Burn 3, Control 2, Rite Combo 1 |
| `archetype_count` | distinct archetypes among its decks | 3 |
| `archetype_concentration` | Simpson's index without replacement over its labelled decks; `None` below two | 0.2667 |
| `record` | summed wins/losses/draws of its decks with a complete record, and how many decks that is | 6 decks, 19-12-1 |
| `series` | its decks in each of the 12 trend periods | (0,0,0,0,4,0,0,0,0,0,0,2) |
| `decks`, `deck_copies` | positions of its decks in the run's deck list, and the copies in each | listed |

The usage record is published for every card including basic lands; the validator
recounts each field from the published deck list.

## The field (`CohortPerformance`)

| Field | Definition | Example |
| --- | --- | ---: |
| `record` | the summed records of every cohort deck with a complete record | 8 decks, 24-16-2 |
| `win_rate` | `(wins + draws / players_per_game) / games` | 0.5952 |
| `top_cut_known_decks`, `top_cut_decks` | decks with a known result, and those that made it | 5, 3 |
| `top_cut_rate` | `top_cut_decks / top_cut_known_decks`, `None` if none known | 0.6 |
| `matches` | `games // players_per_game` | 21 |
| `series`, `series_period_days`, `series_starts_on` | the trend denominators | (0,0,0,0,5,0,0,0,0,0,0,3), 16 days, 2026-02-21 |
| `archetypes` | one `ArchetypeCore` per label: decks, core cards, commanders, events, record, top cuts, series | Burn 3, Control 3, Rite Combo 2 |
| `archetype_concentration` | Simpson's index over the field's labelled decks | 0.25 |

## The feature vector (`CardFeatures`)

Each entry is a `FeatureObservation` unless noted. "Unknown" means `value=None`.

### `incidence` (meta share)

```text
value       = deck_count / cohort decks
support     = deck_count
opportunity = cohort decks
```

Always known for a card in the population. Example: Bolt 6/8 = 0.75. This is the
"Meta share" column, the Constructed score's share component, the Signature
score's `played` baseline, and the Hidden gem score's rarity input.

### `win_rate`

```text
value   = (wins + draws / players_per_game) / games   over the card's decks with a record
support = games
```

Unknown when none of its decks has a complete record (`games == 0`). The
opportunity count is not set: the number of games a card *could* have been played
in is not a meaningful denominator. Example: Bolt (19 + 1/2)/32 = 0.609375 over 32
games.

### `top_cut_rate`

```text
value       = top_cut_count / top_cut_known_decks
support     = top_cut_known_decks
opportunity = top_cut_known_decks
```

Unknown when no deck with the card has a known top-cut result. Example: Bolt 3/4
= 0.75.

### `archetype_concentration` (focus)

```text
value   = sum(n_i (n_i - 1)) / (N (N - 1))   over its labelled decks
support = N (labelled decks)
```

Unknown below two labelled decks. Example: Bolt's six labelled decks are Burn 3,
Control 2, Rite Combo 1: (3·2 + 2·1 + 0) / (6·5) = 8/30 = 0.2667. A commander is
fully concentrated on its own archetype by construction (every deck it leads has
its name as its archetype).

### `archetype_adoption`

```text
value       = archetype_deck_count / (decks of that archetype in the whole cohort)
support     = archetype_deck_count
opportunity = the archetype's deck count
```

The share of the card's home archetype that plays it. Unknown when the card has
no labelled deck (no home archetype). Example: Bolt is in 3 of Burn's 3 decks:
1.0; Snap is in 3 of Control's 3: 1.0.

### `playset_rate`

```text
value       = playset_deck_count / deck_count
support     = playset_deck_count
opportunity = deck_count
```

Always known for a card in the population. Example: Bolt 5/6 = 0.8333. In a
singleton format this is 0 for nearly every card; the Hidden gem score detects
that cohort-wide and declines to score.

### Field baselines (plain floats, `None` when unknown)

`field_win_rate`, `field_top_cut_rate`, `field_archetype_concentration`: the
cohort values above, copied onto every card so a method can shrink toward them
without a second argument.

### Counts

`deck_count` and `event_count` as in usage. `full_field_match_count` is defined
in the dataclass for the Foundation model but the current pipeline never sets it
(no adapter produces round-level matches), so it is 0 in every run.

### Features the pipeline does not fill

`CardFeatures` also declares `deck_family_breadth`, `format_era_breadth`,
`competitive_proof`, `commitment`, `specificity`, `package_coherence`,
`recurrence`, `choice_freedom` and `coverage_strength`. These are the measurement
contract's planned features, consumed only by the Foundation model, and
`card_features()` leaves all of them unknown. The Foundation model reweights
around them, which is why its published Staple score equals 100 × incidence today
and its Build-around signal is 0 with 0% coverage. [Document 5](05-score-methods.md#foundation-model-foundation)
spells this out.

## Descriptive performance (`CardPerformance`)

Shown on the rankings, compare and commander pages. Rounded to 4 decimals. `None`
means unknown.

| Statistic | Formula | Bolt |
| --- | --- | ---: |
| `win_rate` | as the feature, unshrunk | 0.6094 |
| `win_rate_delta` | `win_rate - field_win_rate` | +0.0141 |
| `win_rate_ci95` | `1.96 * sqrt(win_rate (1 - win_rate) / games)` | 0.169 |
| `top_cut_lift` | `(top_cut_count / top_cut_known_decks) / field_top_cut_rate`; `None` without a known result or a zero field rate | 1.25 |
| `share_delta` | `sum(series[6:]) / sum(field.series[6:]) - sum(series[:6]) / sum(field.series[:6])`; `None` when either half of the field series is empty | −0.1333 |

The trend compares pooled shares of the newer and the older half of the series
rather than the last period against the first, so one thin month cannot swing it.

The same function describes an archetype (`archetype_performance`), which is how
commanders are ranked with a win rate, lift and trend of their own.

## The `inputs` a method publishes

Beyond the feature vector, every `CardScore` carries an `inputs` mapping: the
intermediate values the method computed for that card (shrunk deltas, lifts,
focus, the blend). They are stored in `scores.card_score_input` and are the
explanation layer the measurement contract requires: a reader can see why a card
got its score without rerunning anything. The inputs for each method are listed in
[document 5](05-score-methods.md).
