"""Prototype of a Constructed score v2, computed from published score-run files.

Two changes against ``constructed-score-v1`` are tried here, on the standings data the
runs already hold:

1. **Fitted priors.** The prior strength that shrinks each card's win rate and top-cut
   conversion toward the field is fitted per cohort by empirical Bayes (beta-binomial
   maximum marginal likelihood with the mean fixed at the field rate) instead of the
   hand-set 60 games and 20 decks. A fit that finds no between-card variance (the
   strength runs off to its upper bound) drops that component from the blend: the
   cohort cannot tell its cards apart on that statistic.
2. **Within-archetype delta.** A card's decks are compared with the other decks of the
   same archetype (the decks that would play something else in that slot), pooled across
   the card's archetypes, instead of with the whole field only. The contrast is
   leave-one-out: an archetype every one of whose decks plays the card says nothing
   about the card and contributes nothing. The pooled delta is shrunk toward 0 with a
   random-effects variance fitted by maximum likelihood.

Three rankings are compared: v1 as published in the run file, v1 with fitted priors only,
and v2 with both changes. The script is a research tool: the production feature pipeline
does not yet carry per-archetype records, so this does not register a method.

Usage::

    python scripts/prototype_constructed_v2.py analytics/data/local/score-runs/<run>.json ...
    python scripts/prototype_constructed_v2.py --survey analytics/data/local/score-runs
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

PRIOR_UPPER_BOUND = 1.0e5
PRIOR_LOWER_BOUND = 0.5
# v1 constants, reproduced to check the reimplementation against the published scores.
V1_WIN_RATE_PRIOR_GAMES = 60.0
V1_TOP_CUT_PRIOR_DECKS = 20.0
V1_WEIGHTS = (0.60, 0.25, 0.15)
# v2 weights: field delta, within-archetype delta, top-cut lift, meta share.
V2_WEIGHTS = (0.35, 0.25, 0.25, 0.15)
TOP_N = 50
# Below this many effective games the within-archetype contrast is unknown rather than
# weak: a near-zero shrunk delta would otherwise read as "median card" and pull down a
# card (a commander, an archetype's defining card) that merely has nothing to be compared
# against.
MIN_WITHIN_EFFECTIVE_GAMES = 30.0


# --- statistical devices -------------------------------------------------------------


def percentiles(values: Mapping[str, float]) -> dict[str, float]:
    """Mid-rank percentiles in (0, 1); ties share their average rank (as scoring/base.py)."""

    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    result: dict[str, float] = {}
    start = 0
    while start < len(ordered):
        end = start
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[start][1]:
            end += 1
        rank = (start + end) / 2 + 0.5
        for card_id, _ in ordered[start : end + 1]:
            result[card_id] = rank / len(ordered)
        start = end + 1
    return result


def golden_section_max(fn: Callable[[float], float], low: float, high: float) -> float:
    """Argmax of a unimodal function on [low, high] to a relative tolerance of 1e-4."""

    ratio = (math.sqrt(5) - 1) / 2
    a, b = low, high
    c = b - ratio * (b - a)
    d = a + ratio * (b - a)
    fc, fd = fn(c), fn(d)
    while abs(b - a) > 1e-4 * (abs(a) + abs(b) + 1e-12):
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - ratio * (b - a)
            fc = fn(c)
        else:
            a, c, fc = c, d, fd
            d = a + ratio * (b - a)
            fd = fn(d)
    return (a + b) / 2


def lbeta(x: float, y: float) -> float:
    return math.lgamma(x) + math.lgamma(y) - math.lgamma(x + y)


def fit_beta_binomial_strength(
    observations: Iterable[tuple[float, float]], mean: float
) -> tuple[float, bool]:
    """Prior strength k maximising the beta-binomial marginal likelihood at a fixed mean.

    ``observations`` are (successes, trials) pairs; successes may be fractional (draws).
    Returns the strength and whether it ran into the upper bound, which means the data
    show no between-card variance beyond binomial noise.
    """

    rows = [(s, n) for s, n in observations if n > 0]
    if not rows or not 0 < mean < 1:
        return PRIOR_UPPER_BOUND, True

    def log_likelihood(log_k: float) -> float:
        k = math.exp(log_k)
        a, b = k * mean, k * (1 - mean)
        base = lbeta(a, b)
        return sum(lbeta(a + s, b + n - s) - base for s, n in rows)

    best = math.exp(
        golden_section_max(log_likelihood, math.log(PRIOR_LOWER_BOUND), math.log(PRIOR_UPPER_BOUND))
    )
    return best, best >= PRIOR_UPPER_BOUND * 0.99


def fit_random_effects_variance(observations: Iterable[tuple[float, float]]) -> float:
    """Between-unit variance tau^2 maximising sum log N(d; 0, tau^2 + v) over (d, v) pairs."""

    rows = [(d, v) for d, v in observations if v > 0]
    if not rows:
        return 0.0

    def log_likelihood(log_tau2: float) -> float:
        tau2 = math.exp(log_tau2)
        return -0.5 * sum(math.log(tau2 + v) + d * d / (tau2 + v) for d, v in rows)

    tau2 = math.exp(golden_section_max(log_likelihood, math.log(1e-10), math.log(1.0)))
    return 0.0 if tau2 <= 2e-10 else tau2


def shrink(successes: float, trials: float, prior_rate: float, strength: float) -> float:
    return (successes + strength * prior_rate) / (trials + strength)


# --- the run file --------------------------------------------------------------------


@dataclass(frozen=True)
class Record:
    points: float
    games: float

    def __add__(self, other: Record) -> Record:
        return Record(self.points + other.points, self.games + other.games)

    def __sub__(self, other: Record) -> Record:
        return Record(self.points - other.points, self.games - other.games)

    @property
    def rate(self) -> float | None:
        return self.points / self.games if self.games > 0 else None


@dataclass(frozen=True)
class Card:
    card_id: str
    name: str
    deck_count: int
    incidence: float
    record: Record
    top_cut_made: int | None
    top_cut_known: int
    # The within-archetype contrast. In each archetype that has decks both with and without
    # the card, d_a = rate(with) - rate(without) is weighted by its precision,
    # w_a = n_with n_without / (n_with + n_without), so a contrast against three decks
    # without the card cannot dominate however many decks play it.
    within_games: float  # own games in the archetypes that offer a contrast
    within_weight: float  # sum of w_a: the contrast's effective games
    within_contrast: float  # sum of w_a d_a
    within_archetypes: int

    @property
    def within_delta(self) -> float | None:
        return self.within_contrast / self.within_weight if self.within_weight > 0 else None


@dataclass(frozen=True)
class Cohort:
    format_name: str
    window: str
    decks: int
    players_per_game: int
    field_win_rate: float
    field_top_cut_rate: float | None
    cards: tuple[Card, ...]
    published_v1: dict[str, float]
    labelled_decks: int


def deck_record(raw: Mapping[str, object] | None, players_per_game: int) -> Record | None:
    if not raw:
        return None
    wins, losses, draws = (raw.get(key) for key in ("wins", "losses", "draws"))
    if wins is None or losses is None or draws is None:
        return None
    counts = (int(wins), int(losses), int(draws))
    return Record(counts[0] + counts[2] / players_per_game, sum(counts))


def load_cohort(path: Path) -> Cohort:
    with path.open(encoding="utf-8") as handle:
        doc = json.load(handle)
    if "decks" not in doc:
        raise SystemExit(f"{path.name}: run has no deck list (needs card-usage-v7 or later)")
    cohort = doc["cohort"]
    rules = cohort["rules"]
    performance = cohort["performance"]
    players_per_game = int(performance.get("players_per_game", rules.get("players_per_game", 2)))

    decks = doc["decks"]
    deck_records = [deck_record(deck.get("record"), players_per_game) for deck in decks]
    deck_archetypes = [deck.get("archetype") for deck in decks]
    archetype_totals: dict[str, Record] = {}
    for archetype, record in zip(deck_archetypes, deck_records, strict=True):
        if archetype is not None and record is not None:
            archetype_totals[archetype] = archetype_totals.get(archetype, Record(0, 0)) + record

    cards: list[Card] = []
    for raw in doc["cards"]:
        if not raw.get("scored"):
            continue
        positions = raw.get("decks") or []
        total = Record(0.0, 0)
        per_archetype: dict[str, Record] = {}
        for position in positions:
            record = deck_records[position]
            if record is None:
                continue
            total = total + record
            archetype = deck_archetypes[position]
            if archetype is not None:
                per_archetype[archetype] = per_archetype.get(archetype, Record(0, 0)) + record
        within_games = 0.0
        weight = 0.0
        contrast = 0.0
        contributing = 0
        for archetype, own in per_archetype.items():
            others = archetype_totals[archetype] - own
            own_rate, other_rate = own.rate, others.rate
            if own_rate is None or other_rate is None:
                continue
            w = own.games * others.games / (own.games + others.games)
            within_games += own.games
            weight += w
            contrast += w * (own_rate - other_rate)
            contributing += 1
        cards.append(
            Card(
                card_id=raw["oracle_id"],
                name=raw["name"],
                deck_count=int(raw["deck_count"]),
                incidence=int(raw["deck_count"]) / len(decks),
                record=total,
                top_cut_made=raw.get("top_cut_count"),
                top_cut_known=int(raw.get("top_cut_known_decks") or 0),
                within_games=within_games,
                within_weight=weight,
                within_contrast=contrast,
                within_archetypes=contributing,
            )
        )

    published = next((run for run in doc["runs"] if run["method_id"] == "constructed-score"), None)
    published_scores = (
        {
            row["card_id"]: row["values"]["score"]
            for row in published["scores"]
            if row["values"].get("score") is not None
        }
        if published
        else {}
    )
    return Cohort(
        format_name=rules["format_name"],
        window=f"{rules['starts_on']} to {rules['ends_before']}",
        decks=len(decks),
        players_per_game=players_per_game,
        field_win_rate=float(performance["win_rate"]),
        field_top_cut_rate=performance.get("top_cut_rate"),
        cards=tuple(cards),
        published_v1=published_scores,
        labelled_decks=sum(1 for archetype in deck_archetypes if archetype is not None),
    )


# --- the methods ---------------------------------------------------------------------


@dataclass(frozen=True)
class Fit:
    win_rate_strength: float
    win_rate_flat: bool
    top_cut_strength: float
    top_cut_flat: bool
    within_tau2: float
    within_strength: float  # f(1-f)/tau^2, the equivalent in games


def fit_priors(cohort: Cohort) -> Fit:
    f = cohort.field_win_rate
    win_k, win_flat = fit_beta_binomial_strength(
        ((card.record.points, card.record.games) for card in cohort.cards), f
    )
    cut_rate = cohort.field_top_cut_rate
    if cut_rate:
        cut_k, cut_flat = fit_beta_binomial_strength(
            (
                (float(card.top_cut_made or 0), float(card.top_cut_known))
                for card in cohort.cards
                if card.top_cut_made is not None
            ),
            cut_rate,
        )
    else:
        cut_k, cut_flat = PRIOR_UPPER_BOUND, True
    noise = f * (1 - f)
    tau2 = fit_random_effects_variance(
        (card.within_contrast / card.within_weight, noise / card.within_weight)
        for card in cohort.cards
        if card.within_weight >= MIN_WITHIN_EFFECTIVE_GAMES
    )
    within_k = noise / tau2 if tau2 > 0 else math.inf
    return Fit(win_k, win_flat, cut_k, cut_flat, tau2, within_k)


def blend(
    components: Sequence[tuple[float, Mapping[str, float]]], ids: Iterable[str]
) -> dict[str, float]:
    ranked = [(weight, percentiles(values)) for weight, values in components if values]
    result: dict[str, float] = {}
    for card_id in ids:
        known = [(w, ranks[card_id]) for w, ranks in ranked if card_id in ranks]
        total = sum(w for w, _ in known)
        if total:
            result[card_id] = sum(w * r for w, r in known) / total
    return {card_id: 100.0 * value for card_id, value in percentiles(result).items()}


def field_deltas(cohort: Cohort, strength: float) -> dict[str, float]:
    f = cohort.field_win_rate
    return {
        card.card_id: shrink(card.record.points, card.record.games, f, strength) - f
        for card in cohort.cards
        if card.record.games > 0
    }


def cut_lifts(cohort: Cohort, strength: float) -> dict[str, float]:
    rate = cohort.field_top_cut_rate
    if not rate:
        return {}
    return {
        card.card_id: shrink(float(card.top_cut_made), float(card.top_cut_known), rate, strength)
        / rate
        for card in cohort.cards
        if card.top_cut_made is not None and card.top_cut_known > 0
    }


def within_deltas(cohort: Cohort, strength: float) -> dict[str, float]:
    if not math.isfinite(strength):
        return {}
    return {
        card.card_id: card.within_contrast / (card.within_weight + strength)
        for card in cohort.cards
        if card.within_weight >= MIN_WITHIN_EFFECTIVE_GAMES
    }


def shares(cohort: Cohort) -> dict[str, float]:
    return {card.card_id: card.incidence for card in cohort.cards}


def score_v1(cohort: Cohort) -> dict[str, float]:
    ids = [card.card_id for card in cohort.cards]
    w_win, w_cut, w_share = V1_WEIGHTS
    return blend(
        (
            (w_win, field_deltas(cohort, V1_WIN_RATE_PRIOR_GAMES)),
            (w_cut, cut_lifts(cohort, V1_TOP_CUT_PRIOR_DECKS)),
            (w_share, shares(cohort)),
        ),
        ids,
    )


def score_v1_fitted(cohort: Cohort, fit: Fit) -> dict[str, float]:
    ids = [card.card_id for card in cohort.cards]
    w_win, w_cut, w_share = V1_WEIGHTS
    return blend(
        (
            (w_win, {} if fit.win_rate_flat else field_deltas(cohort, fit.win_rate_strength)),
            (w_cut, {} if fit.top_cut_flat else cut_lifts(cohort, fit.top_cut_strength)),
            (w_share, shares(cohort)),
        ),
        ids,
    )


def score_v2(cohort: Cohort, fit: Fit) -> dict[str, float]:
    ids = [card.card_id for card in cohort.cards]
    w_win, w_within, w_cut, w_share = V2_WEIGHTS
    return blend(
        (
            (w_win, {} if fit.win_rate_flat else field_deltas(cohort, fit.win_rate_strength)),
            (w_within, within_deltas(cohort, fit.within_strength)),
            (w_cut, {} if fit.top_cut_flat else cut_lifts(cohort, fit.top_cut_strength)),
            (w_share, shares(cohort)),
        ),
        ids,
    )


# --- comparison ----------------------------------------------------------------------


def spearman(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    keys = [k for k in a if k in b]
    if len(keys) < 3:
        return math.nan
    ra, rb = percentiles({k: a[k] for k in keys}), percentiles({k: b[k] for k in keys})
    ma = sum(ra.values()) / len(keys)
    mb = sum(rb.values()) / len(keys)
    cov = sum((ra[k] - ma) * (rb[k] - mb) for k in keys)
    va = math.sqrt(sum((ra[k] - ma) ** 2 for k in keys))
    vb = math.sqrt(sum((rb[k] - mb) ** 2 for k in keys))
    return cov / (va * vb) if va and vb else math.nan


def top(scores: Mapping[str, float], n: int = TOP_N) -> list[str]:
    return [k for k, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def rank_of(scores: Mapping[str, float]) -> dict[str, int]:
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return {k: i + 1 for i, (k, _) in enumerate(ordered)}


def describe_fit(cohort: Cohort, fit: Fit) -> list[str]:
    games = sorted(card.record.games for card in cohort.cards if card.record.games > 0)
    median_games = games[len(games) // 2] if games else 0
    within = [card for card in cohort.cards if card.within_weight >= MIN_WITHIN_EFFECTIVE_GAMES]
    return [
        f"## {cohort.format_name} ({cohort.window})",
        "",
        f"- decks {cohort.decks:,}, labelled {cohort.labelled_decks:,}; scored cards "
        f"{len(cohort.cards):,}; median games per card {median_games:.0f}; field win rate "
        f"{cohort.field_win_rate:.4f}",
        f"- win-rate prior: v1 60 games; fitted {fit.win_rate_strength:,.0f} games"
        + (" (no between-card variance: component dropped)" if fit.win_rate_flat else ""),
        f"- top-cut prior: v1 20 decks; fitted {fit.top_cut_strength:,.0f} decks"
        + (" (no between-card variance: component dropped)" if fit.top_cut_flat else ""),
        f"- within-archetype delta: {len(within):,} cards have a leave-one-out contrast of at "
        f"least {MIN_WITHIN_EFFECTIVE_GAMES:.0f} effective games; "
        f"tau = {math.sqrt(fit.within_tau2):.4f} ({math.sqrt(fit.within_tau2) * 100:.1f} points); "
        f"equivalent prior {fit.within_strength:,.0f} games"
        if math.isfinite(fit.within_strength)
        else f"- within-archetype delta: {len(within):,} cards have a contrast; no between-card "
        "variance found, component dropped",
    ]


def compare(label_a: str, a: Mapping[str, float], label_b: str, b: Mapping[str, float]) -> str:
    overlap = len(set(top(a)) & set(top(b)))
    return (
        f"- {label_a} vs {label_b}: Spearman {spearman(a, b):.3f}; "
        f"top {TOP_N} overlap {overlap}/{TOP_N}"
    )


def movers(
    cohort: Cohort, fit: Fit, a: Mapping[str, float], b: Mapping[str, float], n: int = 12
) -> list[str]:
    """Cards that enter and leave the top 50 between a and b, with the inputs that moved them."""

    by_id = {card.card_id: card for card in cohort.cards}
    ranks_a, ranks_b = rank_of(a), rank_of(b)
    within = within_deltas(cohort, fit.within_strength)
    field = field_deltas(cohort, fit.win_rate_strength)
    entered = sorted(set(top(b)) - set(top(a)), key=lambda k: ranks_b[k])[:n]
    left = sorted(set(top(a)) - set(top(b)), key=lambda k: ranks_a[k])[:n]

    def row(card_id: str) -> str:
        card = by_id[card_id]
        raw = card.record.rate
        raw_delta = (raw - cohort.field_win_rate) if raw is not None else math.nan
        within_raw = card.within_delta if card.within_delta is not None else math.nan
        return (
            f"| {card.name} | {ranks_a.get(card_id, '-')} | {ranks_b.get(card_id, '-')} | "
            f"{card.deck_count} | {card.record.games:.0f} | {100 * raw_delta:+.1f} | "
            f"{100 * field.get(card_id, math.nan):+.2f} | {100 * within_raw:+.1f} | "
            f"{100 * within.get(card_id, math.nan):+.2f} | {card.within_weight:.0f} | "
            f"{card.within_archetypes} |"
        )

    header = [
        "| card | rank before | rank after | decks | games | raw delta field | shrunk delta field"
        " | raw delta within | shrunk delta within | effective games within"
        " | archetypes with contrast |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines = ["", f"Entered the top {TOP_N}:", "", *header]
    lines.extend(row(card_id) for card_id in entered)
    lines.extend(["", f"Left the top {TOP_N}:", "", *header])
    lines.extend(row(card_id) for card_id in left)
    return lines


def report(path: Path) -> list[str]:
    cohort = load_cohort(path)
    fit = fit_priors(cohort)
    v1 = score_v1(cohort)
    v1_fitted = score_v1_fitted(cohort, fit)
    v2 = score_v2(cohort, fit)
    lines = describe_fit(cohort, fit)
    lines.append("")
    if cohort.published_v1:
        lines.append(compare("published v1", cohort.published_v1, "reimplemented v1", v1))
    lines.append(compare("v1", v1, "v1 with fitted priors", v1_fitted))
    lines.append(compare("v1", v1, "v2", v2))
    lines.append(compare("v1 with fitted priors", v1_fitted, "v2", v2))
    lines.extend(movers(cohort, fit, v1, v2))
    lines.append("")
    return lines


def survey(directory: Path) -> list[str]:
    """One line per run with a deck list: the fitted strengths and the gates."""

    lines = [
        "| format | window | decks | cards | median games | win prior (v1 60)"
        " | top-cut prior (v1 20) | within tau (points) | within prior (games) | v1 vs v2 top 50 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    seen: set[tuple[str, str]] = set()
    for path in sorted(directory.glob("scores-*.json"), key=lambda p: -p.stat().st_mtime):
        try:
            cohort = load_cohort(path)
        except SystemExit:
            continue
        key = (cohort.format_name, cohort.window)
        if key in seen:
            continue
        seen.add(key)
        fit = fit_priors(cohort)
        v1, v2 = score_v1(cohort), score_v2(cohort, fit)
        games = sorted(card.record.games for card in cohort.cards if card.record.games > 0)
        median_games = games[len(games) // 2] if games else 0
        win = "dropped" if fit.win_rate_flat else f"{fit.win_rate_strength:,.0f}"
        cut = "dropped" if fit.top_cut_flat else f"{fit.top_cut_strength:,.0f}"
        tau = f"{100 * math.sqrt(fit.within_tau2):.1f}" if fit.within_tau2 > 0 else "0 (dropped)"
        within = f"{fit.within_strength:,.0f}" if math.isfinite(fit.within_strength) else "-"
        overlap = len(set(top(v1)) & set(top(v2)))
        lines.append(
            f"| {cohort.format_name} | {cohort.window} | {cohort.decks:,} | "
            f"{len(cohort.cards):,} | {median_games:.0f} | {win} | {cut} | {tau} | {within} | "
            f"{overlap}/{TOP_N} |"
        )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="*", type=Path, help="score-run files to report on")
    parser.add_argument(
        "--survey", type=Path, help="directory of runs: one summary line per cohort"
    )
    parser.add_argument("--out", type=Path, help="also write the Markdown report to this file")
    args = parser.parse_args(argv)
    lines: list[str] = []
    if args.survey:
        lines.extend(survey(args.survey))
        lines.append("")
    for path in args.paths:
        lines.extend(report(path))
    text = "\n".join(lines)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.write(text + "\n")
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
