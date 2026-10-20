import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { useI18n } from "#i18n";
import type { I18n } from "@/i18n/translator";
import type { ComparedCard, ComparePage } from "@/lib/api";
import { deltaTone, grade, gradeTone, liftTone } from "@/lib/format";
import { formatLabel } from "@/lib/formats";
import { ManaCost } from "./mana";
import { GradeRing } from "./ranking-data";

type Cell = ComparedCard["formats"][string];
type Format = ComparePage["formats"][number];

export type CompareStat =
  "grade" | "score" | "win_rate" | "share" | "top_cut_lift" | "trend";
export type CompareSummary = "best" | "count";
export type CompareSort = {
  href: string;
  active: boolean;
  order: "asc" | "desc";
};

/** Each stat's column width (px), as the design sizes them; messages name them. */
export const STATS: Record<CompareStat, { width: number }> = {
  grade: { width: 92 },
  score: { width: 72 },
  win_rate: { width: 88 },
  share: { width: 84 },
  top_cut_lift: { width: 80 },
  trend: { width: 84 },
};

export const SUMMARIES: Record<CompareSummary, { width: number }> = {
  best: { width: 156 },
  count: { width: 92 },
};

/** The card column's smallest width; it takes whatever room the stats leave. */
const CARD_WIDTH = 250;

/** Heat tints mark the cells that stand out in their format; the rest stay plain. */
function tint(
  stat: CompareStat,
  cell: Cell,
): { className?: string; alpha?: number } {
  if (stat === "grade" || stat === "score") {
    if (cell.score === null) return {};
    if (cell.score >= 80)
      return {
        className: "heat-up",
        alpha: Math.min((cell.score - 74) / 90, 0.22),
      };
    if (cell.score < 50)
      return {
        className: "heat-down",
        alpha: Math.min((56 - cell.score) / 110, 0.16),
      };
    return {};
  }
  if (stat === "win_rate" && cell.win_rate_delta !== null) {
    const points = 100 * cell.win_rate_delta;
    if (Math.abs(points) < 0.05) return {};
    return {
      className: points > 0 ? "heat-up" : "heat-down",
      alpha: Math.min(Math.abs(points) / 22, 0.24),
    };
  }
  if (stat === "share" && cell.share !== null)
    return {
      className: "heat-share",
      alpha: Math.min((100 * cell.share) / 900, 0.1),
    };
  return {};
}

function value(
  stat: CompareStat,
  cell: Cell,
  { decimal, signed, percent, lift }: I18n,
): ReactNode {
  switch (stat) {
    case "grade":
      return <GradeRing score={cell.score} size="compare" />;
    case "score":
      return cell.score === null ? "—" : decimal(cell.score, 1);
    case "win_rate": {
      if (cell.win_rate_delta === null) return "—";
      const points = 100 * cell.win_rate_delta;
      return (
        <span className={`tone-${deltaTone(points)}`}>{signed(points)}%</span>
      );
    }
    case "share":
      return cell.share === null ? "—" : percent(100 * cell.share);
    case "top_cut_lift":
      return cell.top_cut_lift === null ? (
        "—"
      ) : (
        <span className={`tone-${liftTone(cell.top_cut_lift)}`}>
          {lift(cell.top_cut_lift)}
        </span>
      );
    case "trend": {
      if (cell.share_delta === null) return "—";
      const delta = cell.share_delta;
      const tone =
        delta > 0.0015 ? "positive" : delta < -0.0015 ? "negative" : "neutral";
      return <span className={`tone-${tone}`}>{signed(100 * delta)}</span>;
    }
  }
}

function Sortable({
  label,
  sort,
  className,
}: {
  label: string;
  sort: CompareSort;
  className?: string;
}) {
  return (
    <th
      scope="col"
      className={className}
      aria-sort={
        sort.active
          ? sort.order === "desc"
            ? "descending"
            : "ascending"
          : undefined
      }
    >
      <Link className="sort-link" href={sort.href} scroll={false}>
        {label}
        {sort.active && (
          <span aria-hidden="true">{sort.order === "desc" ? " ↓" : " ↑"}</span>
        )}
      </Link>
    </th>
  );
}

/**
 * Cards as rows and formats as column groups, each format showing the chosen stats.
 * The card column stays put while the table scrolls sideways.
 */
export function CompareTable({
  page,
  stats,
  summaries,
  sorts,
  footer,
}: {
  page: ComparePage;
  stats: CompareStat[];
  summaries: CompareSummary[];
  sorts: (key: string) => CompareSort;
  footer: ReactNode;
}) {
  const i18n = useI18n();
  const { t, fill, plural } = i18n;
  const formats: Format[] = page.formats;
  const multiplayer = (format: Format) => (format.players_per_game ?? 2) > 2;
  const header = (format: Format, stat: CompareStat) =>
    stat === "share" && multiplayer(format)
      ? t.rankings.inclusion
      : t.compare.statHeaders[stat];
  return (
    <div className="compare-frame">
      <div className="compare-scroll">
        <table
          className="compare-table"
          style={{
            minWidth:
              CARD_WIDTH +
              formats.length *
                stats.reduce((sum, stat) => sum + STATS[stat].width, 0) +
              summaries.reduce(
                (sum, summary) => sum + SUMMARIES[summary].width,
                0,
              ),
          }}
        >
          <colgroup>
            <col />
            {formats.flatMap((format) =>
              stats.map((stat) => (
                <col
                  key={`${format.format_name}:${stat}`}
                  style={{ width: STATS[stat].width }}
                />
              )),
            )}
            {summaries.map((summary) => (
              <col key={summary} style={{ width: SUMMARIES[summary].width }} />
            ))}
          </colgroup>
          <thead>
            <tr className="compare-groups">
              <th scope="col" className="sticky-col">
                <span className="compare-count">
                  {plural(t.compare.cardCount, page.total)}
                </span>
              </th>
              {formats.map((format, index) => (
                <th
                  key={format.format_name}
                  scope="colgroup"
                  colSpan={stats.length}
                  className={index % 2 ? "band-alt group-start" : "group-start"}
                >
                  <Link
                    href={`/rankings?format=${encodeURIComponent(format.format_name)}`}
                    title={fill(t.compare.openRankings, {
                      format: formatLabel(format.format_name),
                    })}
                  >
                    <span className="format-dot" aria-hidden="true" />
                    {formatLabel(format.format_name)}
                  </Link>
                </th>
              ))}
              {summaries.length > 0 && (
                <th
                  scope="colgroup"
                  colSpan={summaries.length}
                  className="group-start summary-group"
                >
                  {t.compare.summary}
                </th>
              )}
            </tr>
            <tr className="compare-metrics">
              <Sortable
                label={t.common.card}
                sort={sorts("name")}
                className="sticky-col"
              />
              {formats.flatMap((format, index) =>
                stats.map((stat, position) => (
                  <Sortable
                    key={`${format.format_name}:${stat}`}
                    label={header(format, stat)}
                    sort={sorts(`${format.format_name}:${stat}`)}
                    className={
                      [
                        index % 2 ? "band-alt" : "",
                        position === 0 ? "group-start" : "",
                      ]
                        .join(" ")
                        .trim() || undefined
                    }
                  />
                )),
              )}
              {summaries.map((summary, position) => (
                <Sortable
                  key={summary}
                  label={t.compare.summaryHeaders[summary]}
                  sort={sorts(summary)}
                  className={position === 0 ? "group-start" : undefined}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {page.items.map((card) => (
              <tr key={card.oracle_id}>
                <th scope="row" className="sticky-col compare-card">
                  <span className="card-name">{card.name}</span>
                  <span className="card-meta">
                    {card.mana_cost && <ManaCost cost={card.mana_cost} />}
                    {card.type_line ? (
                      <span className="card-type">{card.type_line}</span>
                    ) : (
                      <span className="muted">{t.common.notInCatalog}</span>
                    )}
                  </span>
                </th>
                {formats.flatMap((format, index) => {
                  const cell = card.formats[format.format_name];
                  return stats.map((stat, position) => {
                    const classes = [
                      index % 2 ? "band-alt" : "",
                      position === 0 ? "group-start" : "",
                    ];
                    if (!cell)
                      return (
                        <td
                          key={`${format.format_name}:${stat}`}
                          className={[...classes, "unranked"].join(" ").trim()}
                          title={fill(t.compare.notRanked, {
                            format: formatLabel(format.format_name),
                          })}
                        >
                          —
                        </td>
                      );
                    const heat = tint(stat, cell);
                    return (
                      <td
                        key={`${format.format_name}:${stat}`}
                        className={
                          [...classes, heat.className ?? ""].join(" ").trim() ||
                          undefined
                        }
                        style={
                          heat.alpha
                            ? ({
                                "--tint": heat.alpha.toFixed(3),
                              } as CSSProperties)
                            : undefined
                        }
                        title={`${card.name} · ${formatLabel(format.format_name)} · #${cell.rank}`}
                      >
                        {value(stat, cell, i18n)}
                      </td>
                    );
                  });
                })}
                {summaries.map((summary, position) => {
                  const className = position === 0 ? "group-start" : undefined;
                  if (summary === "best") {
                    const letter =
                      card.best_score === null ? null : grade(card.best_score);
                    return (
                      <td key={summary} className={className}>
                        <span className="best-format">
                          <span>{formatLabel(card.best_format)}</span>
                          {letter && (
                            <span
                              className={`best-grade tone-${gradeTone(letter)}`}
                            >
                              {letter}
                            </span>
                          )}
                        </span>
                      </td>
                    );
                  }
                  return (
                    <td
                      key={summary}
                      className={
                        [className ?? "", card.ranked_in >= 3 ? "" : "muted"]
                          .join(" ")
                          .trim() || undefined
                      }
                      title={plural(t.compare.rankedIn, formats.length, {
                        ranked: card.ranked_in,
                      })}
                    >
                      {card.ranked_in} / {formats.length}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {page.items.length === 0 && (
        <div className="ranking-empty">
          <h3>{t.compare.emptyTitle}</h3>
          <p>{fill(t.compare.emptyBody, { every: t.compare.every })}</p>
        </div>
      )}
      <div className="ranking-footer compare-footer">
        {footer}
        <dl className="compare-legend">
          <dt>{t.compare.legendGrade}</dt>
          <dd>
            <span className="tone-a">A</span> {t.compare.gradeA}
          </dd>
          <dd>
            <span className="tone-b">B</span> {t.compare.gradeB}
          </dd>
          <dd>
            <span className="tone-c">C</span> {t.compare.gradeC}
          </dd>
          <dd>
            <span className="tone-d">D</span> {t.compare.gradeD}
          </dd>
          <dd>
            <span className="tone-f">F</span> {t.compare.gradeF}
          </dd>
          <dd>
            <span className="legend-swatch" aria-hidden="true" />{" "}
            {t.compare.tinted}
          </dd>
        </dl>
      </div>
    </div>
  );
}
