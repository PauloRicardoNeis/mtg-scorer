import type { CSSProperties } from "react";
import { useI18n } from "#i18n";
import type { I18n } from "@/i18n/translator";
import type { RankedCard, RankingPage } from "@/lib/api";
import { deltaTone, grade, gradeTone, liftTone, movement } from "@/lib/format";
import { ColorPips } from "./mana";

type Run = RankingPage["score_run"];

/** What the win-rate and trend cells read; a ranked commander has the same fields. */
type Performance = Pick<RankedCard, "win_rate" | "win_rate_delta">;
type Series = Pick<RankedCard, "series_decks" | "share_delta">;

/** Methods whose 0–100 percentile scale carries letter grades. */
const GRADED_METHODS = [
  "constructed-score",
  "signature-score",
  "hidden-gem-score",
  "overall-grade",
];

export function isGraded(methodId: string): boolean {
  return GRADED_METHODS.includes(methodId);
}

/** The gradings a reader can rank by, in menu order; a run offers those it has. */
export const GRADINGS = [
  "constructed-score",
  "signature-score",
  "hidden-gem-score",
  "max-ratio",
];

/**
 * The gradings formats can be compared by, in menu order; the first is the default.
 * The comparison API grades by these alone.
 */
export const COMPARE_GRADINGS = ["constructed-score", "signature-score"];

/** The method the API ranks by without one: the first of these the run has. */
export function defaultMethod(run: Run): string {
  const ids = run.methods.map((method) => method.method_id);
  return (
    ["constructed-score", "max-ratio"].find((id) => ids.includes(id)) ?? ids[0]
  );
}

/**
 * A grade ring: the score fills the ring, the letter sits in the inner disc. Only
 * A grades glow. Sizes follow the design: table rows, the podium and the preview.
 */
export function GradeRing({
  score,
  size = "row",
}: {
  score: number | null;
  size?: "row" | "compare" | "podium" | "first" | "preview";
}) {
  const { t, fill } = useI18n();
  if (score === null)
    return (
      <span className={`grade-ring grade-ring-${size} grade-ring-unknown`}>
        <span className="grade-letter" aria-label={t.rankingData.noGrade}>
          —
        </span>
      </span>
    );
  const letter = grade(score);
  return (
    <span
      className={`grade-ring grade-ring-${size} ring-${gradeTone(letter)}`}
      style={
        {
          "--fill": `${Math.max(0, Math.min(100, score)) * 3.6}deg`,
        } as CSSProperties
      }
    >
      <span
        className="grade-letter"
        aria-label={fill(t.rankingData.grade, { letter })}
      >
        {letter}
      </span>
    </span>
  );
}

/** Places gained since the previous run; unknown without one. */
export function RankMove({ change }: { change: number | null | undefined }) {
  const { t, plural } = useI18n();
  if (change === null || change === undefined)
    return (
      <span className="rank-move">
        <span aria-hidden="true">—</span>
        <span className="sr-only">{t.rankingData.noEarlierRank}</span>
      </span>
    );
  const tone = change > 0 ? "up" : change < 0 ? "down" : "flat";
  return (
    <span className={`rank-move rank-move-${tone}`}>
      <span aria-hidden="true">{movement(change)}</span>
      <span className="sr-only">
        {change === 0
          ? t.rankingData.sameRank
          : plural(
              change > 0 ? t.rankingData.up : t.rankingData.down,
              Math.abs(change),
            )}
      </span>
    </span>
  );
}

/**
 * Win rate against the field: a bar grows left or right of the centre tick, with
 * the delta in points beside it and the raw win rate below. The overall run has
 * only the delta, since win rates of one-on-one and multiplayer formats differ.
 */
export function WinRate({ card }: { card: Performance }) {
  const { t, fill, percent, signed } = useI18n();
  if (card.win_rate_delta === null)
    return <span className="muted">{t.common.unknown}</span>;
  const points = 100 * card.win_rate_delta;
  // A ±6-point delta fills one half of the 72px track.
  const width = Math.min(36, (Math.abs(points) / 6) * 36);
  const tone = deltaTone(points);
  return (
    <span className="win-rate">
      <span className="diverging" aria-hidden="true">
        <span
          className={`diverging-fill ${points >= 0 ? "above" : "below"}`}
          style={{
            left: `${points >= 0 ? 36 : 36 - width}px`,
            width: `${Math.max(1.5, width)}px`,
          }}
        />
      </span>
      <span className="stacked">
        <span className={`tone-${tone}`}>
          {signed(points)}%
          <span className="sr-only"> {t.rankingData.againstField}</span>
        </span>
        {card.win_rate !== null && (
          <span className="sub">
            {fill(t.rankings.winRate, { value: percent(100 * card.win_rate) })}
          </span>
        )}
      </span>
    </span>
  );
}

/**
 * Meta share as a value over a bar sized against the run's most-played card. A
 * counted share shows the decks instead: across formats, a share of every deck
 * would mostly measure the largest format.
 */
export function MetaShare({
  decks,
  total,
  most,
  counted = false,
}: {
  decks: number;
  total: number;
  most: number;
  counted?: boolean;
}) {
  const { count, share } = useI18n();
  return (
    <span className="stacked share">
      <span>{counted ? count(decks) : share(decks, total)}</span>
      <span
        className="share-bar"
        aria-hidden="true"
        style={
          {
            "--fill": `${most > 0 ? (100 * decks) / most : 0}%`,
          } as CSSProperties
        }
      />
    </span>
  );
}

/** Top-cut conversion against the field's, as a lift. */
export function TopCutLift({ value }: { value: number | null }) {
  const { t, lift } = useI18n();
  if (value === null) return <span className="muted">{t.common.unknown}</span>;
  return <span className={`tone-${liftTone(value)}`}>{lift(value)}</span>;
}

/** The card's meta share in each trend period the cohort has decks for. */
export function shares(
  card: Pick<Series, "series_decks">,
  run: Run,
): (number | null)[] {
  const totals = run.series_decks;
  if (!card.series_decks || !totals) return [];
  return card.series_decks.map((decks, index) =>
    totals[index] ? decks / totals[index] : null,
  );
}

/** How far the trend series reaches back: "12 mo", "6 mo", or "8 wk" when shorter. */
export function trendLabel(run: Run, { t, fill }: I18n): string | null {
  const days = (run.series_period_days ?? 0) * (run.series_decks?.length ?? 0);
  if (!days) return null;
  return days >= 60
    ? fill(t.rankings.months, { count: Math.round(days / 30) })
    : fill(t.rankings.weeks, { count: Math.round(days / 7) });
}

/** Shares within 0.15 points count as flat. */
function trendTone(delta: number): "up" | "down" | "flat" {
  return delta > 0.0015 ? "up" : delta < -0.0015 ? "down" : "flat";
}

/**
 * A 64×24 sparkline of meta share, its end point marked, and the change in points
 * beside it. Periods without decks leave a gap in the data, not a zero.
 */
export function Trend({ card, run }: { card: Series; run: Run }) {
  const { t, signed } = useI18n();
  const series = shares(card, run);
  const known = series.flatMap((share, index) =>
    share === null ? [] : [[index, share] as const],
  );
  if (known.length < 2 || card.share_delta === null)
    return <span className="muted">—</span>;
  const values = known.map(([, share]) => share);
  const low = Math.min(...values);
  const span = Math.max(...values) - low || 1;
  const step = 64 / (series.length - 1);
  const points = known.map(
    ([index, share]) =>
      [index * step, 21 - ((share - low) / span) * 18] as const,
  );
  const path = points
    .map(
      ([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`,
    )
    .join(" ");
  const [endX, endY] = points[points.length - 1];
  const tone = trendTone(card.share_delta);
  const delta = 100 * card.share_delta;
  return (
    <span className={`trend trend-${tone}`}>
      <svg width="64" height="24" viewBox="0 0 64 24" aria-hidden="true">
        <path d={path} />
        <circle cx={endX.toFixed(1)} cy={endY.toFixed(1)} r="2.25" />
      </svg>
      <span>
        {signed(delta)}
        <span className="sr-only"> {t.rankingData.shareChange}</span>
      </span>
    </span>
  );
}

/** An archetype's color symbols, its name and how many more archetypes play the card. */
export function MostPlayedIn({ card }: { card: RankedCard }) {
  const { t, plural } = useI18n();
  const top = card.archetypes[0];
  if (!top) {
    if (!card.archetype_label)
      return <span className="muted">{t.rankingData.unlabelled}</span>;
    return <span className="archetype-name">{card.archetype_label}</span>;
  }
  const more = (card.archetype_count ?? card.archetypes.length) - 1;
  return (
    <span className="archetype">
      <ColorPips values={top.colors} />
      <span className="archetype-name">{top.label}</span>
      {more > 0 && (
        <span className="archetype-more">
          +{more}
          <span className="sr-only">
            {" "}
            {plural(t.rankingData.moreArchetypes, more)}
          </span>
        </span>
      )}
    </span>
  );
}

/** Rank as a share of the scored cards: rank 3 of 600 is "Top 1%". */
export function percentile(
  rank: number,
  scored: number,
  { t, fill }: I18n,
): string | null {
  if (!scored) return null;
  return fill(t.rankings.top, {
    value: Math.max(1, Math.ceil((100 * rank) / scored)),
  });
}
