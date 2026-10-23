# 7. Worked example

A synthetic Modern cohort followed from saved responses to every method's score.
The numbers were produced by running the real pipeline (`read_saved_responses`,
`select_cohort`, `card_usage`, `cohort_performance`, `card_features`,
`build_score_run`) over the fixture below on 2026-10-21, and each intermediate is
recomputed by hand so the formulas in the earlier documents can be checked line
by line. Every event, deck, player and card here is invented; the oracle ids are
UUIDs derived from the names.

## The fixture

Two events in a window of 2026-03-01 to 2026-09-01 (184 days), rules
`min_decklist_coverage = 0.5`, `players_per_game = 2`.

**Event "doc-open", 2026-05-10, six players, top cut of 3, bracket columns present**

| Row | Record | Bracket W-L | Deck | Label |
| --- | --- | --- | --- | --- |
| 1 | 5-1 | 2-0 | Bolt ×4, Ragavan ×4, Mountain ×16 | Burn |
| 2 | 4-2 | 0-1 | Rite ×4, Bolt ×2, Mountain ×16 | Rite Combo |
| 3 | 4-2 | 0-1 | Snap ×4, Bolt ×4, Mountain ×16 | Control |
| 4 | 3-3 | 0-0 | Bolt ×4, Ragavan ×3, Mountain ×16 | Burn |
| 5 | 2-4 | 0-0 | Snap ×2, Mountain ×16 | Control |
| 6 | 1-5 | 0-0 | (no decklist) | |

**Event "doc-weekly", 2026-08-20, three players, no top cut**

| Row | Record | Deck | Label |
| --- | --- | --- | --- |
| 1 | 3-0-1 | Rite ×4, Mountain ×16 | Rite Combo |
| 2 | 2-1-1 | Bolt ×4, Ragavan ×4, Mountain ×16 | Burn |
| 3 | 1-3 | Snap ×4, Bolt ×4, Mountain ×16 | Control |

## Cohort selection

- "doc-open": 5 of 6 players have a mainboard, coverage 0.83 ≥ 0.5: included.
- "doc-weekly": 3 of 3, coverage 1.0: included.
- Decks: 8. Events: 2. No incomplete mainboards, no team events.

**Top cut.** "doc-open" has bracket columns on every row, so the basis is
`bracket_record`: rows 1-3 have `winsBracket + lossesBracket > 0` and made the
cut; rows 4-6 did not. "doc-weekly" reports no top cut: basis `no_top_cut`, every
result unknown.

**Field record.** Every deck has a complete record. Wins 5+4+4+3+2+3+2+1 = 24;
losses 1+2+2+3+4+0+1+3 = 16; draws 2; games 42.

```text
field win rate   = (24 + 2/2) / 42 = 25/42 = 0.5952
field matches    = 42 // 2 = 21
top-cut known    = 5 (the "doc-open" decks)   made = 3   rate = 0.6
```

(The field is not exactly 50% because the deck without a list, which went 1-5, is
not in the cohort's decks, and the synthetic records were not made to balance.)

**Trend series.** `period_days = min(30, ceil(184 / 12)) = 16`;
`series_starts_on = 2026-09-01 − 192 days = 2026-02-21`. "doc-open" is
`(114 − 1) // 16 = 7` periods back, index 4; "doc-weekly" is `(12 − 1) // 16 = 0`
back, index 11. Field series: `(0,0,0,0,5,0,0,0,0,0,0,3)`.

**Archetypes.** Burn 3 decks, Control 3, Rite Combo 2. Field concentration:
`(3·2 + 3·2 + 2·1) / (8·7) = 14/56 = 0.25`. Core cards are those in at least half
an archetype's decks: Burn {Bolt, Ragavan, Mountain}; Control {Snap, Bolt,
Mountain}, since Bolt is in 2 of its 3 decks; Rite Combo {Rite, Bolt, Mountain},
since Bolt is in 1 of its 2 decks, exactly half, which qualifies. Each archetype
therefore has 3 core cards.

**Population.** Bolt, Ragavan, Rite, Snap are scored; Mountain is a basic land,
described but `scored: false`.

## Usage and features

| Card | Decks | Events | Copies | Playsets | Cut made/known | Label (decks/labelled) | Record | Series |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| Bolt | 6 | 2 | 22 | 5 | 3 / 4 | Burn (3/6) | 19-12-1, 32 games | 4 then 2 |
| Ragavan | 3 | 2 | 11 | 2 | 1 / 2 | Burn (3/3) | 10-5-1, 16 | 2 then 1 |
| Rite | 2 | 2 | 8 | 2 | 1 / 1 | Rite Combo (2/2) | 7-2-1, 10 | 1 then 1 |
| Snap | 3 | 2 | 10 | 2 | 1 / 2 | Control (3/3) | 7-9-0, 16 | 2 then 1 |
| Mountain | 8 | 2 | 128 | 8 | 3 / 5 | Burn (3/8, tie broken alphabetically) | 24-16-2, 42 | 5 then 3 |

Bolt's known top cuts: its "doc-open" decks are rows 1, 2, 3 (made) and 4 (did
not), so 3 of 4; its two "doc-weekly" decks are unknown and not counted.

| Feature | Bolt | Ragavan | Rite | Snap |
| --- | ---: | ---: | ---: | ---: |
| incidence | 6/8 = 0.75 | 0.375 | 0.25 | 0.375 |
| win_rate | (19 + 0.5)/32 = 0.6094 | (10 + 0.5)/16 = 0.6563 | (7 + 0.5)/10 = 0.75 | 7/16 = 0.4375 |
| top_cut_rate | 3/4 = 0.75 | 1/2 = 0.5 | 1/1 = 1.0 | 1/2 = 0.5 |
| archetype_concentration | (3·2 + 2·1 + 0)/(6·5) = 0.2667 | 1.0 | 1.0 | 1.0 |
| archetype_adoption | 3/3 = 1.0 | 3/3 | 2/2 | 3/3 |
| playset_rate | 5/6 = 0.8333 | 2/3 | 2/2 | 2/3 |

**Descriptive performance** (unshrunk, as the page shows):

| Statistic | Bolt | Ragavan | Rite | Snap |
| --- | ---: | ---: | ---: | ---: |
| win_rate_delta | 0.6094 − 0.5952 = +0.0141 | +0.0610 | +0.1548 | −0.1577 |
| win_rate_ci95 | 1.96·√(0.6094·0.3906/32) = 0.169 | 0.2327 | 0.2684 | 0.2431 |
| top_cut_lift | 0.75 / 0.6 = 1.25 | 0.8333 | 1.6667 | 0.8333 |
| share_delta | 2/3 − 4/5 = −0.1333 | 1/3 − 2/5 = −0.0667 | 1/3 − 1/5 = +0.1333 | −0.0667 |

Rite's +15.5 points carry a ±26.8 interval over 10 games: the page shows both.

## Constructed score

Shrunk win-rate delta, prior 60 games, field 0.5952:

```text
Bolt:    (19.5 + 60·0.5952) / (32 + 60) = 55.21 / 92 = 0.6002  -> +0.0049
Ragavan: (10.5 + 35.71) / 76 = 0.6081                          -> +0.0128
Rite:    ( 7.5 + 35.71) / 70 = 0.6173                          -> +0.0221
Snap:    ( 7.0 + 35.71) / 76 = 0.5620                          -> -0.0332
```

Shrunk top-cut lift, prior 20 decks, field 0.6:

```text
Bolt:    (3 + 12) / 24 = 0.625  / 0.6 = 1.0417
Ragavan: (1 + 12) / 22 = 0.5909 / 0.6 = 0.9848
Rite:    (1 + 12) / 21 = 0.6190 / 0.6 = 1.0317
Snap:    (1 + 12) / 22 = 0.5909 / 0.6 = 0.9848
```

Percentiles among the four cards (positions 0.5/4, 1.5/4, 2.5/4, 3.5/4; ties share
the mean position):

| Component | Snap | Bolt | Ragavan | Rite |
| --- | ---: | ---: | ---: | ---: |
| win delta | 0.125 | 0.375 | 0.625 | 0.875 |
| cut lift | 0.25 (tied with Ragavan) | 0.875 | 0.25 | 0.625 |
| share | 0.5 (tied with Ragavan) | 0.875 | 0.5 | 0.125 |

Blends, 0.60/0.25/0.15:

```text
Bolt:    0.60·0.375 + 0.25·0.875 + 0.15·0.875 = 0.575
Ragavan: 0.60·0.625 + 0.25·0.25  + 0.15·0.5   = 0.5125
Rite:    0.60·0.875 + 0.25·0.625 + 0.15·0.125 = 0.7
Snap:    0.60·0.125 + 0.25·0.25  + 0.15·0.5   = 0.2125
```

Final percentile of the blend × 100: Snap 12.5, Ragavan 37.5, Bolt 62.5, Rite 87.5.
Rite leads on the strength of its (shrunk) results despite the lowest share; Bolt
is second because its share and conversion percentiles are the highest even though
its shrunk win rate is only a hair above the field.

Pipeline output (`runs[constructed-score]`):

```text
Rite    score 87.5   win_rate_delta 0.0221  top_cut_lift 1.0317  meta_share 0.25   blend 0.7
Bolt    score 62.5   win_rate_delta 0.0049  top_cut_lift 1.0417  meta_share 0.75   blend 0.575
Ragavan score 37.5   win_rate_delta 0.0128  top_cut_lift 0.9848  meta_share 0.375  blend 0.5125
Snap    score 12.5   win_rate_delta -0.0332 top_cut_lift 0.9848  meta_share 0.375  blend 0.2125
```

## Signature score

All four cards have labelled decks, so all are eligible. Field concentration
0.25, priors 10 decks.

Focus `(c·n + 10·0.25) / (n + 10)`:

```text
Bolt:    (0.2667·6 + 2.5) / 16 = 0.2563   effective archetypes 3.90
Ragavan: (1.0·3 + 2.5) / 13    = 0.4231   2.36
Rite:    (1.0·2 + 2.5) / 12    = 0.3750   2.67
Snap:    (1.0·3 + 2.5) / 13    = 0.4231   2.36
```

Rite is in only one archetype, as are Ragavan and Snap, but with two labelled
decks its focus is pulled further toward the field than theirs with three.

Adoption `(home.support + 10·played) / (home.opportunity + 10)` and reliance:

```text
Bolt:    (3 + 7.5)  / 13 = 0.8077   reliance 0.8077 - 0.75  = 0.0577
Ragavan: (3 + 3.75) / 13 = 0.5192   reliance 0.5192 - 0.375 = 0.1442
Rite:    (2 + 2.5)  / 12 = 0.3750   reliance 0.375  - 0.25  = 0.1250
Snap:    (3 + 3.75) / 13 = 0.5192   reliance 0.1442
```

Win deltas as in the Constructed score. Percentiles and blend 0.50/0.30/0.20:

| | Bolt | Ragavan | Rite | Snap |
| --- | ---: | ---: | ---: | ---: |
| focus percentile | 0.125 | 0.75 (tie) | 0.375 | 0.75 (tie) |
| reliance percentile | 0.125 | 0.75 (tie) | 0.375 | 0.75 (tie) |
| win percentile | 0.375 | 0.625 | 0.875 | 0.125 |
| blend | 0.175 | 0.725 | 0.475 | 0.625 |

Scores: Bolt 12.5, Rite 37.5, Snap 62.5, Ragavan 87.5. Bolt, played in three of
the three archetypes, is the least distinctive; Ragavan and Snap tie on
distinctiveness and the win rate separates them.

## Hidden gem score

Pooled playset share among the scored cards: `(5 + 2 + 2 + 2) / (6 + 3 + 2 + 3)
= 11/14 = 0.7857 ≥ 0.05`, so the cohort is not singleton.

Per card (win prior 100 games, cut prior 20 decks, playset prior 5 decks):

```text
Bolt:
  win lift   = ((19.5 + 59.52) / 132) / 0.5952 - 1 = 0.5986/0.5952 - 1 = +0.0058
  cut lift   = 0.625 / 0.6 - 1                     = +0.0417
  result     = 0.7·0.0058 + 0.3·0.0417             = 0.0165
  playsets   = (5 + 5·0.7857) / (6 + 5)            = 0.8117
  recurrence = 2 / (2 + 2)                         = 0.5
  rarity     = 1 / (1 + 0.75 / 0.02)               = 0.0260
  gem        = 0.8117 · 0.0165 · 0.5 · 0.0260       = 0.000174

Ragavan: win lift +0.0141, cut lift -0.0152, result +0.0054, playsets 0.7411,
         rarity 1/(1+18.75) = 0.0506, gem 0.000100
Rite:    win lift +0.0236, cut lift +0.0317, result +0.0261, playsets 0.8469,
         rarity 1/(1+12.5) = 0.0741, gem 0.000818
Snap:    win lift -0.0366, cut lift -0.0152, result -0.0301, gem -0.000565
```

Snap's decks do no better than the field: score 0.0. The other three rank by
gem: Ragavan 16.667, Bolt 50.0, Rite 83.333 (positions 0.5/3, 1.5/3, 2.5/3). Rite
is the gem of this cohort: a four-of in every deck that plays it, the best
results, and only a quarter of the field.

## Relative volume

Leader Bolt with 6 decks: Bolt 100.0, Ragavan 50.0, Snap 50.0, Rite 33.3.

## Foundation model

Only incidence is known of the staple group, so `staple = 100 × incidence` at 35%
coverage; the build-around group is entirely unknown. Evidence for Bolt:

```text
0.30·(1 − e^(−6/8)) + 0.25·(1 − e^(−2/4)) + 0.20·0 + 0.15·0 + 0.10·(0.35 + 0)/2
= 0.30·0.5276 + 0.25·0.3935 + 0.0175 = 0.2742  -> 27.4
```

| Card | staple | buildaround | evidence | delta | staple coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bolt | 75.0 | 0.0 | 27.4 | −75.0 | 35.0 |
| Ragavan | 37.5 | 0.0 | 21.0 | −37.5 | 35.0 |
| Rite | 25.0 | 0.0 | 18.2 | −25.0 | 35.0 |
| Snap | 37.5 | 0.0 | 21.0 | −37.5 | 35.0 |

## Overall grade

A separate illustration with three formats, since the fixture has one:

```text
Modern 1000 decks: weight 1000/1250 = 0.8    staple 90, specialist 95, filler 10
Legacy  250 decks: weight 0.5                staple 90, filler 20
Pauper   50 decks: weight 50/300  = 0.1667   staple 90, filler 30

staple:     (0.8·90 + 0.5·90 + 0.1667·90 + 50) / (1.4667 + 1) = 182 / 2.4667 = 73.78
specialist: (0.8·95 + 50) / 1.8                               = 126 / 1.8    = 70.00
filler:     (8 + 10 + 5 + 50) / 2.4667                        = 73 / 2.4667  = 29.59
```

Percentiles: filler 16.667, specialist 50.0, staple 83.333. The specialist's 95
in one format loses to the staple's 90 in three, and the evidence weights show
that Pauper's 50 decks contributed a sixth of a format.

## The run file

The run id for this fixture is a SHA-256 over the dataset snapshot id (itself a
hash of the one saved file), the parser version `topdeck-bulk-v5`, the feature
pipeline version `card-usage-v8`, the rules hash, the population rule and the
five method identities. Rerunning the script reproduces the same file byte for
byte; changing any prior in any configuration changes the id.

To reproduce, the script is small: build the two events with
`analytics/tests/synthetic_topdeck.py`, save them, and call the functions named
at the top of this document in order. `tests/test_score_run.py` does the same
with its own fixture.
