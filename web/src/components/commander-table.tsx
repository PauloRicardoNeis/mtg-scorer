"use client";

import Link from "next/link";
import { Fragment, useState, type ReactNode } from "react";
import { useI18n } from "#i18n";
import type { CommanderPage, RankedCommander } from "@/lib/api";
import { deltaTone } from "@/lib/format";
import { edition, rankedCardHref } from "@/lib/urls";
import { CardImage } from "./card-image";
import { Icon } from "./icon";
import { ColorPips } from "./mana";
import {
  MetaShare,
  RankMove,
  TopCutLift,
  Trend,
  WinRate,
} from "./ranking-data";
import type { SortLink } from "./ranking-table";

type Run = CommanderPage["score_run"];
type Commander = RankedCommander["commanders"][number];

/** A sortable column header, as on the card rankings. */
function Sortable({ label, link }: { label: string; link: SortLink }) {
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
      <Link className="sort-link" href={link.href} scroll={false}>
        {label}
        {link.active && (
          <span aria-hidden="true">{link.order === "desc" ? " ↓" : " ↑"}</span>
        )}
      </Link>
    </th>
  );
}

/** The row's thumbnails are decorative: the names sit beside them. */
function Thumbs({ commanders }: { commanders: Commander[] }) {
  return (
    <span
      className={
        commanders.length > 1 ? "commander-thumbs pair" : "commander-thumbs"
      }
      aria-hidden="true"
    >
      {commanders.map((commander) => {
        const src = commander.preview_printing?.images[0]?.source_uri;
        return (
          <span className="thumb" key={commander.oracle_id}>
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
      })}
    </span>
  );
}

/** Each commander's name, linked to its card when the catalog has it. */
export function CommanderNames({
  commanders,
  catalogSnapshotId,
}: {
  commanders: Commander[];
  catalogSnapshotId: string | null;
}) {
  return (
    <span className="commander-names">
      {commanders.map((commander, index) => {
        const href = rankedCardHref(commander, catalogSnapshotId);
        return (
          <Fragment key={commander.oracle_id}>
            {index > 0 && <span className="commander-plus"> + </span>}
            {href ? (
              <Link className="card-name" href={href}>
                {commander.name}
              </Link>
            ) : (
              <span className="card-name">{commander.name}</span>
            )}
          </Fragment>
        );
      })}
    </span>
  );
}

/** The selected commander's cards with the run's numbers for its decks. */
function Preview({
  commander,
  run,
  shareLabel,
  catalogSnapshotId,
}: {
  commander: RankedCommander;
  run: Run;
  shareLabel: string;
  catalogSnapshotId: string | null;
}) {
  const { t, fill, plural, count, percent, signed, share, lift } = useI18n();
  const pair = commander.commanders.length > 1;
  return (
    <aside className="ranking-preview" aria-label={t.commanders.selected}>
      <p className="preview-rank">
        <span>{fill(t.rankingTable.rank, { rank: commander.rank })}</span>
        <RankMove change={commander.rank_change} />
      </p>
      <div className={pair ? "preview-art preview-art-pair" : "preview-art"}>
        {commander.commanders.map((card) =>
          card.preview_printing ? (
            <CardImage
              key={card.oracle_id}
              src={card.preview_printing.images[0]?.source_uri ?? null}
              alt={fill(t.images.alt, {
                name: card.name,
                edition: edition(card.preview_printing),
              })}
              featured={!pair}
            />
          ) : (
            <div className="preview-placeholder" key={card.oracle_id}>
              {card.name}
            </div>
          ),
        )}
      </div>
      <dl className="preview-stats">
        <div>
          <dt>{t.rankingTable.winRate}</dt>
          <dd>
            {commander.win_rate === null ? (
              "—"
            ) : (
              <>
                {percent(100 * commander.win_rate)}{" "}
                {commander.win_rate_ci95 !== null && (
                  <span className="sub">
                    ±{percent(100 * commander.win_rate_ci95)}
                  </span>
                )}
              </>
            )}
          </dd>
        </div>
        <div>
          <dt>{t.rankingTable.vsField}</dt>
          <dd
            className={
              commander.win_rate_delta === null
                ? undefined
                : `tone-${deltaTone(100 * commander.win_rate_delta)}`
            }
          >
            {commander.win_rate_delta === null
              ? "—"
              : `${signed(100 * commander.win_rate_delta)}%`}
          </dd>
        </div>
        <div>
          <dt>{shareLabel}</dt>
          <dd>{share(commander.deck_count, run.decks)}</dd>
        </div>
        <div>
          <dt>{t.rankings.topCut}</dt>
          <dd>
            {commander.top_cut_lift === null
              ? "—"
              : lift(commander.top_cut_lift)}
          </dd>
        </div>
        <div>
          <dt>{t.commanders.decks}</dt>
          <dd>{count(commander.deck_count)}</dd>
        </div>
        <div>
          <dt>{t.commanders.events}</dt>
          <dd>{count(commander.event_count)}</dd>
        </div>
      </dl>
      <p className="preview-played muted">
        {plural(t.commanders.coreCards, commander.core_card_count)}
      </p>
      {commander.commanders.map((card) => {
        const href = rankedCardHref(card, catalogSnapshotId);
        return (
          href && (
            <Link
              key={card.oracle_id}
              className={
                pair ? "button secondary preview-open" : "button preview-open"
              }
              href={href}
              aria-label={fill(t.rankingTable.openCardNamed, {
                name: card.name,
              })}
            >
              {pair ? card.name : t.rankingTable.openCard}
              <Icon name="arrow-right" size={14} />
            </Link>
          )
        );
      })}
    </aside>
  );
}

/**
 * One page of a run's commanders with a preview of the selected one. Hovering or
 * focusing a row selects it; each commander's name opens its card.
 */
export function CommanderTable({
  items,
  run,
  sorts,
  shareLabel,
  trendLabel,
  maxDeckCount,
  catalogSnapshotId,
  clearHref,
  footer,
}: {
  items: RankedCommander[];
  run: Run;
  sorts: Record<string, SortLink>;
  shareLabel: string;
  trendLabel: string | null;
  maxDeckCount: number;
  catalogSnapshotId: string | null;
  clearHref: string;
  footer: ReactNode;
}) {
  const { t, fill, count } = useI18n();
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  // A new page or filter may drop the selected commander; the top row stands in.
  const selected =
    items.find((commander) => commander.label === selectedLabel) ?? items[0];
  return (
    <div className="ranking-body">
      <div className="ranking-frame">
        <div className="ranking-scroll">
          <table className="ranking-table commander-table">
            <colgroup>
              <col className="col-rank" />
              <col />
              <col className="col-share" />
              <col className="col-win" />
              <col className="col-cut" />
              <col className="col-trend" />
              <col className="col-events" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">#</th>
                <Sortable label={t.commanders.commander} link={sorts.name} />
                <Sortable label={shareLabel} link={sorts.decks} />
                <Sortable
                  label={t.rankingTable.winRateVsField}
                  link={sorts.win_rate}
                />
                <Sortable label={t.rankings.topCut} link={sorts.top_cut_lift} />
                <Sortable
                  label={
                    trendLabel
                      ? fill(t.rankingTable.trendOver, { period: trendLabel })
                      : t.rankingTable.trend
                  }
                  link={sorts.trend}
                />
                <th scope="col">{t.commanders.events}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((commander) => {
                const single =
                  commander.commanders.length === 1
                    ? commander.commanders[0]
                    : null;
                return (
                  <tr
                    key={commander.label}
                    data-selected={commander === selected || undefined}
                    onPointerEnter={() => setSelectedLabel(commander.label)}
                    onFocus={() => setSelectedLabel(commander.label)}
                  >
                    <td className="rank-cell">
                      <span className="stacked">
                        <span className="rank">{commander.rank}</span>
                        <RankMove change={commander.rank_change} />
                      </span>
                    </td>
                    <th scope="row" className="card-cell">
                      <span className="card-cell-inner">
                        <Thumbs commanders={commander.commanders} />
                        <span className="card-text">
                          <CommanderNames
                            commanders={commander.commanders}
                            catalogSnapshotId={catalogSnapshotId}
                          />
                          <span className="card-meta">
                            <ColorPips values={commander.colors} />
                            {single?.type_line && (
                              <span className="card-type">
                                {single.type_line}
                              </span>
                            )}
                          </span>
                        </span>
                      </span>
                    </th>
                    <td>
                      <MetaShare
                        decks={commander.deck_count}
                        total={run.decks}
                        most={maxDeckCount}
                      />
                    </td>
                    <td>
                      <WinRate card={commander} />
                    </td>
                    <td>
                      <TopCutLift value={commander.top_cut_lift} />
                    </td>
                    <td>
                      <Trend card={commander} run={run} />
                    </td>
                    <td>{count(commander.event_count)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {items.length === 0 && (
          <div className="ranking-empty">
            <h3>{t.commanders.emptyTitle}</h3>
            <p>{t.commanders.emptyBody}</p>
            <Link className="button secondary" href={clearHref}>
              {t.common.clearFilters}
            </Link>
          </div>
        )}
        <div className="ranking-footer">{footer}</div>
      </div>
      {selected && (
        <Preview
          commander={selected}
          run={run}
          shareLabel={shareLabel}
          catalogSnapshotId={catalogSnapshotId}
        />
      )}
    </div>
  );
}
