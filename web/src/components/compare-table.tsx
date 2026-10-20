import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import type { ComparedCard, ComparePage } from "@/lib/api";
import {
  deltaTone,
  grade,
  gradeTone,
  lift,
  liftTone,
  percent,
  signed,
} from "@/lib/format";
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

/** Column header, chip label and width (px) of each stat, as the design sizes them. */
export const STATS: Record<
  CompareStat,
  { header: string; chip: string; width: number }
> = {
  grade: { header: "Grade", chip: "Grade", width: 92 },
  score: { header: "Score", chip: "Score", width: 72 },
  win_rate: { header: "Vs field", chip: "Win rate vs field", width: 88 },
  share: { header: "Share", chip: "Meta share", width: 84 },
  top_cut_lift: { header: "Top cut", chip: "Top-cut conversion", width: 80 },
  trend: { header: "Trend", chip: "Trend", width: 84 },
};

export const SUMMARIES: Record<
  CompareSummary,
  { header: string; chip: string; width: number }
> = {
  best: { header: "Best format", chip: "Best format", width: 156 },
  count: { header: "Ranked in", chip: "Formats ranked", width: 92 },
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

function value(stat: CompareStat, cell: Cell): ReactNode {
  switch (stat) {
    case "grade":
      return <GradeRing score={cell.score} size="compare" />;
    case "score":
      return cell.score === null ? "—" : cell.score.toFixed(1);
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
  const formats: Format[] = page.formats;
  const multiplayer = (format: Format) => (format.players_per_game ?? 2) > 2;
  const header = (format: Format, stat: CompareStat) =>
    stat === "share" && multiplayer(format) ? "Inclusion" : STATS[stat].header;
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
                  {page.total.toLocaleString("en-US")} cards
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
                    title={`Open ${formatLabel(format.format_name)} rankings`}
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
                  Summary
                </th>
              )}
            </tr>
            <tr className="compare-metrics">
              <Sortable
                label="Card"
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
                  label={SUMMARIES[summary].header}
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
                      <span className="muted">Not in this catalog</span>
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
                          title={`Not ranked in ${formatLabel(format.format_name)}`}
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
                        {value(stat, cell)}
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
                      title={`Ranked in ${card.ranked_in} of ${formats.length} formats`}
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
          <h3>No cards match.</h3>
          <p>
            Add a format, turn off &ldquo;In every selected format&rdquo;, or
            clear the color filter.
          </p>
        </div>
      )}
      <div className="ranking-footer compare-footer">
        {footer}
        <dl className="compare-legend">
          <dt>Grade</dt>
          <dd>
            <span className="tone-a">A</span> Top tier
          </dd>
          <dd>
            <span className="tone-b">B</span> Strong
          </dd>
          <dd>
            <span className="tone-c">C</span> Playable
          </dd>
          <dd>
            <span className="tone-d">D</span> Fringe
          </dd>
          <dd>
            <span className="tone-f">F</span> Underperforming
          </dd>
          <dd>
            <span className="legend-swatch" aria-hidden="true" /> Tinted cells
            stand out in that format
          </dd>
        </dl>
      </div>
    </div>
  );
}
