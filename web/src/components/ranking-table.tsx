"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type CSSProperties, type ReactNode } from "react";
import type { RankedCard, RankingPage } from "@/lib/api";
import { deltaTone, lift, percent, share, signed } from "@/lib/format";
import { edition, rankedCardHref } from "@/lib/urls";
import { CardImage } from "./card-image";
import { Icon } from "./icon";
import { ColorPips, ManaCost } from "./mana";
import {
  GradeRing,
  MetaShare,
  MostPlayedIn,
  RankMove,
  TopCutLift,
  Trend,
  WinRate,
  percentile,
} from "./ranking-data";
import { Tooltip } from "./tooltip";

type Run = RankingPage["score_run"];
type Method = Run["methods"][number];

export type SortLink = { href: string; active: boolean; order: "asc" | "desc" };

export type ColumnLabels = { share: string; cut: string; trend: string | null };

function score(card: RankedCard): string | null {
  return card.score === null ? null : card.score.toFixed(1);
}

/** The row thumbnail is decorative: the card's name sits beside it. */
function Thumb({ card }: { card: RankedCard }) {
  const src = card.preview_printing?.images[0]?.source_uri;
  return (
    <span className="thumb" aria-hidden="true">
      {src && (
        <img
          src={src}
          alt=""
          width={30}
          height={42}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
        />
      )}
    </span>
  );
}

/** A sortable column header: the active one reads text-1 with its direction. */
function Sortable({
  label,
  link,
  children,
}: {
  label: string;
  link: SortLink | undefined;
  children?: ReactNode;
}) {
  if (!link) return <th scope="col">{label}</th>;
  return (
    <th
      scope="col"
      aria-sort={
        link.active
          ? link.order === "desc"
            ? "descending"
            : "ascending"
          : undefined
      }
    >
      <span className="th-info">
        <Link className="sort-link" href={link.href} scroll={false}>
          {label}
          {link.active && (
            <span aria-hidden="true">
              {link.order === "desc" ? " ↓" : " ↑"}
            </span>
          )}
        </Link>
        {children}
      </span>
    </th>
  );
}

/** The selected card with the run's numbers for it. */
function Preview({
  card,
  run,
  graded,
  method,
  labels,
  href,
}: {
  card: RankedCard;
  run: Run;
  graded: boolean;
  method: Method;
  labels: ColumnLabels;
  href: string | null;
}) {
  const printing = card.preview_printing;
  const top = percentile(card.rank, run.scored_cards);
  return (
    <aside className="ranking-preview" aria-label="Selected card">
      <p className="preview-rank">
        <span>Rank {card.rank}</span>
        <RankMove change={card.rank_change} />
      </p>
      <div className="preview-art">
        {printing ? (
          <CardImage
            key={card.oracle_id}
            src={printing.images[0]?.source_uri ?? null}
            alt={`${card.name} — ${edition(printing)}`}
            featured
          />
        ) : (
          <div className="preview-placeholder">{card.name}</div>
        )}
      </div>
      <div className="preview-score">
        {graded && <GradeRing score={card.score} size="preview" />}
        <p>
          <span className="preview-score-value">{score(card) ?? "—"}</span>
          <span>{graded ? (top ?? method.label) : method.label}</span>
        </p>
      </div>
      <dl className="preview-stats">
        <div>
          <dt>Win rate</dt>
          <dd>
            {card.win_rate === null ? (
              "—"
            ) : (
              <>
                {percent(100 * card.win_rate)}{" "}
                {card.win_rate_ci95 !== null && (
                  <span className="sub">
                    ±{percent(100 * card.win_rate_ci95)}
                  </span>
                )}
              </>
            )}
          </dd>
        </div>
        <div>
          <dt>Vs field</dt>
          <dd
            className={
              card.win_rate_delta === null
                ? undefined
                : `tone-${deltaTone(100 * card.win_rate_delta)}`
            }
          >
            {card.win_rate_delta === null
              ? "—"
              : `${signed(100 * card.win_rate_delta)}%`}
          </dd>
        </div>
        <div>
          <dt>{labels.share}</dt>
          <dd>{share(card.deck_count, run.decks)}</dd>
        </div>
        <div>
          <dt>{labels.cut} · copies</dt>
          <dd>
            {card.top_cut_lift === null ? "—" : lift(card.top_cut_lift)}{" "}
            <span className="sub">
              · {card.avg_copies === null ? "—" : card.avg_copies.toFixed(1)}
            </span>
          </dd>
        </div>
      </dl>
      <div className="preview-played">
        <p className="preview-label">Played in</p>
        {card.archetypes.length > 0 ? (
          card.archetypes.map((archetype) => {
            const part = (100 * archetype.deck_count) / card.deck_count;
            return (
              <p className="played-row" key={archetype.label}>
                <ColorPips values={archetype.colors} />
                <span className="played-name">{archetype.label}</span>
                <span className="played-share">{percent(part)}</span>
                <span
                  className="played-bar"
                  aria-hidden="true"
                  style={{ "--fill": `${part}%` } as CSSProperties}
                />
              </p>
            );
          })
        ) : card.archetype_label ? (
          <p className="played-row">
            <span className="played-name">{card.archetype_label}</span>
            <span className="played-share">
              {share(card.archetype_deck_count, card.deck_count)}
            </span>
          </p>
        ) : (
          <p className="muted">No labelled decks</p>
        )}
      </div>
      {href && (
        <Link
          className="button preview-open"
          href={href}
          aria-label={`Open card: ${card.name}`}
        >
          Open card
          <Icon name="arrow-right" size={14} />
        </Link>
      )}
    </aside>
  );
}

/**
 * The ranked cards of one page with a preview of the selected card. Hovering or
 * focusing a row selects it; clicking a row opens the card, as its name does.
 */
export function RankingTable({
  items,
  run,
  method,
  graded,
  labels,
  sorts,
  maxDeckCount,
  catalogSnapshotId,
  clearHref,
  footer,
}: {
  items: RankedCard[];
  run: Run;
  method: Method;
  graded: boolean;
  labels: ColumnLabels;
  sorts: Record<string, SortLink>;
  maxDeckCount: number;
  catalogSnapshotId: string | null;
  clearHref: string;
  footer: ReactNode;
}) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // A new page or filter may drop the selected card; the top row stands in.
  const selected =
    items.find((card) => card.oracle_id === selectedId) ?? items[0];
  return (
    <div className="ranking-body">
      <div className="ranking-frame">
        <div className="ranking-scroll">
          <table className="ranking-table">
            <colgroup>
              <col className="col-rank" />
              <col />
              <col className="col-score" />
              <col className="col-win" />
              <col className="col-share" />
              <col className="col-cut" />
              <col className="col-trend" />
              <col className="col-archetype" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">#</th>
                <Sortable label="Card" link={sorts.name} />
                <Sortable
                  label={graded ? "Grade" : method.label}
                  link={sorts.score}
                >
                  <Tooltip
                    label="About this score"
                    eyebrow="Method"
                    title={method.label}
                    placement="below"
                  >
                    {method.description}
                    <span className="tooltip-meta">
                      {method.method_version}
                    </span>
                  </Tooltip>
                </Sortable>
                <Sortable label="Win rate vs field" link={sorts.win_rate} />
                <Sortable label={labels.share} link={sorts.decks} />
                <Sortable label={labels.cut} link={sorts.top_cut_lift} />
                <Sortable
                  label={labels.trend ? `Trend · ${labels.trend}` : "Trend"}
                  link={sorts.trend}
                />
                <th scope="col">Most played in</th>
              </tr>
            </thead>
            <tbody>
              {items.map((card) => {
                const href = rankedCardHref(card, catalogSnapshotId);
                return (
                  <tr
                    key={card.oracle_id}
                    data-selected={card === selected || undefined}
                    data-opens={href ? "" : undefined}
                    onPointerEnter={() => setSelectedId(card.oracle_id)}
                    onFocus={() => setSelectedId(card.oracle_id)}
                    onClick={(event) => {
                      // Links navigate themselves; selected text is left to copy.
                      if (
                        !href ||
                        (event.target as Element).closest("a, button") ||
                        String(window.getSelection())
                      )
                        return;
                      router.push(href);
                    }}
                  >
                    <td className="rank-cell">
                      <span className="stacked">
                        <span className="rank">{card.rank}</span>
                        <RankMove change={card.rank_change} />
                      </span>
                    </td>
                    <th scope="row" className="card-cell">
                      <span className="card-cell-inner">
                        <Thumb card={card} />
                        <span className="card-text">
                          {href ? (
                            <Link className="card-name" href={href}>
                              {card.name}
                            </Link>
                          ) : (
                            <span className="card-name">{card.name}</span>
                          )}
                          <span className="card-meta">
                            {card.mana_cost && (
                              <ManaCost cost={card.mana_cost} />
                            )}
                            {card.type_line ? (
                              <span className="card-type">
                                {card.type_line}
                              </span>
                            ) : (
                              <span className="muted">Not in this catalog</span>
                            )}
                          </span>
                        </span>
                      </span>
                    </th>
                    <td>
                      {graded ? (
                        <span className="grade-cell">
                          <GradeRing score={card.score} />
                          <span className="grade-score">
                            {score(card) ?? "—"}
                          </span>
                        </span>
                      ) : (
                        (score(card) ?? <span className="muted">Unknown</span>)
                      )}
                    </td>
                    <td>
                      <WinRate card={card} />
                    </td>
                    <td>
                      <MetaShare
                        decks={card.deck_count}
                        total={run.decks}
                        most={maxDeckCount}
                      />
                    </td>
                    <td>
                      <TopCutLift value={card.top_cut_lift} />
                    </td>
                    <td>
                      <Trend card={card} run={run} />
                    </td>
                    <td>
                      <MostPlayedIn card={card} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {items.length === 0 && (
          <div className="ranking-empty">
            <h3>No ranked cards match.</h3>
            <p>Loosen a filter or search a different name.</p>
            <Link className="button secondary" href={clearHref}>
              Clear filters
            </Link>
          </div>
        )}
        <div className="ranking-footer">{footer}</div>
      </div>
      {selected && (
        <Preview
          card={selected}
          run={run}
          graded={graded}
          method={method}
          labels={labels}
          href={rankedCardHref(selected, catalogSnapshotId)}
        />
      )}
    </div>
  );
}
