"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type CSSProperties, type ReactNode } from "react";
import type { RankedCard, RankingPage } from "@/lib/api";
import { count, share } from "@/lib/format";
import { edition, rankedCardHref } from "@/lib/urls";
import { CardImage } from "./card-image";
import { Icon } from "./icon";
import { ManaCost } from "./mana";
import { Tooltip } from "./tooltip";

type Method = RankingPage["score_run"]["methods"][number];

function fill(percent: number): CSSProperties {
  return { "--fill": `${percent}%` } as CSSProperties;
}

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

function TopCuts({ card }: { card: RankedCard }) {
  if (card.top_cut_count === null)
    return <span className="muted">Unknown</span>;
  return (
    <span className="stacked">
      <span>{count(card.top_cut_count)}</span>
      <span className="sub">of {count(card.top_cut_known_decks)} known</span>
    </span>
  );
}

/** The selected card with the run's current numbers for it. */
function Preview({
  card,
  decks,
  method,
  href,
}: {
  card: RankedCard;
  decks: number;
  method: Method;
  href: string | null;
}) {
  const printing = card.preview_printing;
  return (
    <aside className="ranking-preview" aria-label="Selected card">
      <p className="preview-rank">Rank {card.rank}</p>
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
      <p className="preview-score">
        <span className="preview-score-value">{score(card) ?? "—"}</span>
        <span>{method.label}</span>
      </p>
      <dl className="preview-stats">
        <div>
          <dt>Meta share</dt>
          <dd>{share(card.deck_count, decks)}</dd>
        </div>
        <div>
          <dt>Decks</dt>
          <dd>{count(card.deck_count)}</dd>
        </div>
        <div>
          <dt>Events</dt>
          <dd>{count(card.event_count)}</dd>
        </div>
        <div>
          <dt>Top cuts</dt>
          <dd>
            <TopCuts card={card} />
          </dd>
        </div>
      </dl>
      <div className="preview-played">
        <p className="preview-label">Played in</p>
        {card.archetype_label ? (
          <p className="played-row">
            <span className="played-name">{card.archetype_label}</span>
            <span className="played-share">
              {share(card.archetype_deck_count, card.labelled_deck_count)}
            </span>
            <span
              className="played-bar"
              aria-hidden="true"
              style={fill(
                (100 * card.archetype_deck_count) / card.labelled_deck_count,
              )}
            />
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
  decks,
  method,
  catalogSnapshotId,
  clearHref,
  footer,
}: {
  items: RankedCard[];
  decks: number;
  method: Method;
  catalogSnapshotId: string | null;
  clearHref: string;
  footer: ReactNode;
}) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // A new page or filter may drop the selected card; the top row stands in.
  const selected =
    items.find((card) => card.oracle_id === selectedId) ?? items[0];
  // Share bars are relative to the largest share on this page.
  const most = Math.max(1, ...items.map((card) => card.deck_count));
  return (
    <div className="ranking-body">
      <div className="ranking-frame">
        <div className="ranking-scroll">
          <table className="ranking-table">
            <colgroup>
              <col className="col-rank" />
              <col />
              <col className="col-score" />
              <col className="col-share" />
              <col className="col-events" />
              <col className="col-cuts" />
              <col className="col-archetype" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Card</th>
                <th scope="col">
                  <span className="th-info">
                    <span>{method.label}</span>
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
                  </span>
                </th>
                <th scope="col">Meta share</th>
                <th scope="col">Events</th>
                <th scope="col">Top cuts</th>
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
                      // The name link navigates itself; selected text is left to copy.
                      if (
                        !href ||
                        (event.target as Element).closest("a") ||
                        String(window.getSelection())
                      )
                        return;
                      router.push(href);
                    }}
                  >
                    <td className="rank">{card.rank}</td>
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
                      {score(card) ?? <span className="muted">Unknown</span>}
                    </td>
                    <td>
                      <span className="stacked">
                        <span>{share(card.deck_count, decks)}</span>
                        <span
                          className="share-bar"
                          aria-hidden="true"
                          style={fill((100 * card.deck_count) / most)}
                        />
                      </span>
                    </td>
                    <td>{count(card.event_count)}</td>
                    <td>
                      <TopCuts card={card} />
                    </td>
                    <td>
                      {card.archetype_label ? (
                        <span className="stacked archetype">
                          <span className="archetype-name">
                            {card.archetype_label}
                          </span>
                          <span className="sub">
                            {count(card.archetype_deck_count)} of{" "}
                            {count(card.labelled_deck_count)} decks
                          </span>
                        </span>
                      ) : (
                        <span className="muted">Unlabelled</span>
                      )}
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
          decks={decks}
          method={method}
          href={rankedCardHref(selected, catalogSnapshotId)}
        />
      )}
    </div>
  );
}
