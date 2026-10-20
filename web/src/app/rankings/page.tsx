import type { Metadata } from "next";
import Link from "next/link";
import { api, ApiError, type RankedCard, type RankingPage } from "@/lib/api";
import { queryParams, rankedCardHref, type SearchParams } from "@/lib/urls";
import { ago, count, dateWindow } from "@/lib/format";
import { Problem } from "@/components/problem";
import { CardImages } from "@/components/card-image";
import { Icon } from "@/components/icon";
import { UnderlineTabs } from "@/components/primitives";
import { RankingFilters } from "@/components/ranking-filters";
import { RankingTable } from "@/components/ranking-table";

export const metadata: Metadata = { title: "MTG Scorer · Card rankings" };

// The design's formats always show, so missing data is visible; any other format
// with a published run follows them.
const designFormats = [
  "Standard",
  "Pioneer",
  "Modern",
  "Legacy",
  "Vintage",
  "Pauper",
];

// What kind of format each is, under its name. Formats without an entry say
// where their events come from instead.
const descriptors: Record<string, string> = {
  Standard: "Rotating · 60 cards · 1v1",
  Pioneer: "Non-rotating · Return to Ravnica forward · 1v1",
  Modern: "Non-rotating · Eighth Edition forward · 1v1",
  Legacy: "Eternal · 60 cards · 1v1",
  Vintage: "Eternal · restricted list · 1v1",
  Pauper: "Commons only · 60 cards · 1v1",
  Commander: "cEDH · 100-card singleton · 4-player pods",
  EDH: "cEDH · 100-card singleton · 4-player pods",
};

// The podium shows second, first and third from left to right.
const numerals = ["I", "II", "III"];

/** A link within the same pinned run, keeping only the given filters. */
function link(page: RankingPage, filters: [string, string][] = []) {
  const query = new URLSearchParams([
    ["format", page.score_run.format_name],
    ["score_run_id", page.score_run.score_run_id],
    ...filters,
  ]);
  return `/rankings?${query}`;
}

/** A card's catalog page, pinned to the joined catalog; plain text outside it. */
function CardName({ page, card }: { page: RankingPage; card: RankedCard }) {
  const href = rankedCardHref(card, page.catalog_snapshot_id);
  if (!href) return <span>{card.name}</span>;
  return <Link href={href}>{card.name}</Link>;
}

export default async function Rankings({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  // Without JavaScript the filters submit as a GET form, so unset fields arrive
  // as empty values; the API accepts only set ones.
  const query = new URLSearchParams(
    [...queryParams(await searchParams)].filter(([, value]) => value !== ""),
  );
  try {
    const page = await api.rankings(query);
    const run = page.score_run;
    const method = run.methods.find(
      (candidate) => candidate.method_id === page.method_id,
    )!;
    const active = new Set(page.formats.map((format) => format.format_name));
    const formats = [
      ...designFormats,
      ...[...active].filter((format) => !designFormats.includes(format)).sort(),
    ];
    const kept = [...query].filter(([key]) =>
      ["q", "type", "color", "sort", "limit"].includes(key),
    );
    const filtered = kept.some(([key]) => ["q", "type", "color"].includes(key));
    const sort = query.get("sort") ?? "score";
    const source = run.source === "topdeck" ? "TopDeck" : run.source;
    const podium =
      page.offset === 0 && sort === "score" && !filtered
        ? page.items.slice(0, 3)
        : [];
    const first = page.offset + 1;
    const last = page.offset + page.items.length;
    const pageLink = (offset: number) =>
      link(page, offset ? [...kept, ["offset", String(offset)]] : kept);
    return (
      <>
        <section className="intro band rankings-intro">
          <div className="intro-inner band-inner">
            <div className="intro-copy">
              <div className="rankings-heading">
                <p className="eyebrow">Constructed card rankings</p>
                <h1>{run.format_name}</h1>
                <p className="format-descriptor">
                  {descriptors[run.format_name] ??
                    `Competitive ${source} events`}
                </p>
                <p className="lead">
                  Ranked by {method.label.toLowerCase()}: how often each card
                  was played, compared with the most-played card. It measures
                  popularity in published decklists, not card strength.
                </p>
              </div>
              <dl className="stat-strip">
                <div>
                  <dt>Decklists</dt>
                  <dd>{count(run.decks)}</dd>
                </div>
                <div>
                  <dt>Events</dt>
                  <dd>{count(run.events)}</dd>
                </div>
                <div>
                  <dt>Players</dt>
                  <dd>{count(run.players)}</dd>
                </div>
                <div>
                  <dt>Top-cut decks</dt>
                  <dd>{count(run.top_cut_decks)}</dd>
                </div>
                <div>
                  <dt>Window</dt>
                  <dd>
                    {dateWindow(run.window_starts_on, run.window_ends_before)}
                  </dd>
                </div>
              </dl>
              <p className="freshness">
                <span className="pulse" aria-hidden="true" />
                <span>
                  Updated{" "}
                  <time
                    dateTime={run.published_at}
                    title={`Published ${new Date(run.published_at).toUTCString()}`}
                  >
                    {ago(run.published_at)}
                  </time>
                  {" · "}
                  {run.source === "topdeck" ? (
                    <a href="https://topdeck.gg" rel="noreferrer">
                      TopDeck.gg
                    </a>
                  ) : (
                    run.attribution
                  )}
                </span>
              </p>
            </div>
          </div>
        </section>
        <div className="band format-tabs">
          <div className="band-inner">
            <UnderlineTabs
              label="Formats"
              items={formats.map((format) => ({
                href: `/rankings?format=${encodeURIComponent(format)}`,
                label: format,
                current: format === run.format_name,
                disabled: !active.has(format),
                count: active.has(format) ? undefined : "No data yet",
              }))}
            />
          </div>
        </div>
        {podium.length > 0 && (
          <section className="podium band" aria-label="Most played cards">
            <ol className="band-inner podium-inner">
              {[1, 0, 2]
                .filter((place) => place < podium.length)
                .map((place) => [podium[place], numerals[place]] as const)
                .map(([card, numeral]) => (
                  <li key={card.oracle_id} data-place={numeral}>
                    <span className="podium-place" aria-hidden="true">
                      {numeral}
                    </span>
                    {card.preview_printing ? (
                      <CardImages
                        name={card.name}
                        printing={card.preview_printing}
                        preview
                      />
                    ) : (
                      <div className="podium-placeholder">{card.name}</div>
                    )}
                    <p>
                      <span className="sr-only">Rank {card.rank}: </span>
                      <CardName page={page} card={card} />
                    </p>
                    <p className="mono-label">
                      {card.score === null ? "—" : card.score.toFixed(1)} ·{" "}
                      {count(card.deck_count)} decks
                    </p>
                  </li>
                ))}
            </ol>
          </section>
        )}
        <RankingFilters
          format={run.format_name}
          scoreRunId={run.score_run_id}
          query={new URLSearchParams(kept).toString()}
          clearHref={link(page)}
        />
        <section aria-labelledby="ranking-heading" className="ranking-results">
          <h2 id="ranking-heading" className="sr-only">
            {run.format_name} rankings
          </h2>
          <RankingTable
            items={page.items}
            decks={run.decks}
            method={method}
            catalogSnapshotId={page.catalog_snapshot_id}
            clearHref={link(page)}
            footer={
              <>
                <p role="status">
                  {page.total === 0
                    ? "No ranked cards match"
                    : `${count(first)}–${count(last)} of ${count(page.total)} ranked cards`}
                </p>
                <div className="pagination-links">
                  {page.offset > 0 && (
                    <Link
                      className="button secondary sm"
                      href={pageLink(Math.max(0, page.offset - page.limit))}
                    >
                      <Icon name="arrow-left" size={14} /> Previous
                    </Link>
                  )}
                  {last < page.total && (
                    <Link className="button secondary sm" href={pageLink(last)}>
                      Next {page.limit} <Icon name="arrow-right" size={14} />
                    </Link>
                  )}
                </div>
              </>
            }
          />
          <p className="cohort-note">
            Counts come from published decklists at competitive events with at
            least half their lists published; basic lands are not ranked. A top
            cut counts only where the result is known. Ranks keep their place
            when you filter.
          </p>
        </section>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
