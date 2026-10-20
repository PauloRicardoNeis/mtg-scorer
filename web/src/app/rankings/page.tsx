import type { Metadata } from "next";
import Link from "next/link";
import { api, ApiError, type RankedCard, type RankingPage } from "@/lib/api";
import { queryParams, rankedCardHref, type SearchParams } from "@/lib/urls";
import { ago, count, dateWindow, percent, windowLabel } from "@/lib/format";
import { Problem } from "@/components/problem";
import { CardImage } from "@/components/card-image";
import { Icon } from "@/components/icon";
import { FormatBar, type FormatTab } from "@/components/format-bar";
import {
  descriptors,
  designFormats,
  formatLabel as label,
} from "@/lib/formats";
import {
  RankingFilters,
  type SourceTab,
  type ViewTab,
  type WindowOption,
} from "@/components/ranking-filters";
import {
  GRADED_METHOD,
  GradeRing,
  trendLabel,
} from "@/components/ranking-data";
import { RankingTable, type SortLink } from "@/components/ranking-table";

export const metadata: Metadata = { title: "MTG Scorer · Card rankings" };

/** Sorts a header can apply, and the direction a first click uses. */
const sortable: Record<string, "asc" | "desc"> = {
  name: "asc",
  score: "desc",
  win_rate: "desc",
  decks: "desc",
  top_cut_lift: "desc",
  trend: "desc",
};

const views: [view: string, label: string][] = [
  ["all", "All"],
  ["risers", "Risers"],
  ["fallers", "Fallers"],
];

/** A link within the same pinned run, keeping only the given filters. */
function link(page: RankingPage, filters: [string, string][] = []) {
  const query = new URLSearchParams([
    ["format", page.score_run.format_name],
    ["score_run_id", page.score_run.score_run_id],
    ...filters,
  ]);
  return `/rankings?${query}`;
}

/** Replaces some filters and drops the page offset, which no longer applies. */
function relink(
  page: RankingPage,
  kept: [string, string][],
  changes: Record<string, string | null>,
) {
  const rest = kept.filter(([key]) => !(key in changes) && key !== "offset");
  const set = Object.entries(changes).flatMap(([key, value]) =>
    value === null ? [] : [[key, value] as [string, string]],
  );
  return link(page, [...rest, ...set]);
}

/** One podium place: the card, its numeral above and its grade on the card's edge. */
function Place({
  page,
  card,
  numeral,
  graded,
}: {
  page: RankingPage;
  card: RankedCard;
  numeral: string;
  graded: boolean;
}) {
  const href = rankedCardHref(card, page.catalog_snapshot_id);
  const first = numeral === "I";
  const image = card.preview_printing ? (
    <CardImage
      src={card.preview_printing.images[0]?.source_uri ?? null}
      alt={card.name}
      featured={first}
      interactive
    />
  ) : (
    <div className="podium-placeholder">{card.name}</div>
  );
  return (
    <li data-place={numeral}>
      <span className="podium-place" aria-hidden="true">
        {numeral}
      </span>
      <div className="podium-card">
        {href ? (
          <Link href={href} aria-label={`Rank ${card.rank}: ${card.name}`}>
            {image}
          </Link>
        ) : (
          image
        )}
        {graded && (
          <GradeRing score={card.score} size={first ? "first" : "podium"} />
        )}
      </div>
      <p className="podium-stats">
        <span className="sr-only">
          Rank {card.rank}: {card.name}.{" "}
        </span>
        <span className="podium-score">
          {card.score === null ? "—" : card.score.toFixed(1)}
        </span>
        {card.win_rate !== null ? (
          <span>{percent(100 * card.win_rate)} WR</span>
        ) : (
          <span>{count(card.deck_count)} decks</span>
        )}
      </p>
    </li>
  );
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
    const graded = method.method_id === GRADED_METHOD;
    const multiplayer = (run.players_per_game ?? 2) > 2;
    const labels = {
      share: multiplayer ? "Inclusion" : "Meta share",
      cut: "Top cut",
      trend: trendLabel(run),
    };
    const decksOf = new Map(page.formats.map((f) => [f.format_name, f.decks]));
    const tabs: FormatTab[] = [
      ...designFormats.map(([tab, format]) => ({
        label: tab,
        format,
        decks: decksOf.get(format) ?? null,
      })),
      ...page.formats
        .filter(
          (f) => !designFormats.some(([, format]) => format === f.format_name),
        )
        .map((f) => ({
          label: f.format_name,
          format: f.format_name,
          decks: f.decks,
        }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    ];
    const kept = [...query].filter(([key]) =>
      ["q", "type", "color", "sort", "order", "view", "limit"].includes(key),
    ) as [string, string][];
    const filtered = kept.some(([key]) => ["q", "type", "color"].includes(key));
    const podium =
      page.offset === 0 &&
      page.sort === "score" &&
      page.order === "desc" &&
      page.view === "all" &&
      !filtered
        ? page.items.slice(0, 3)
        : [];
    const sorts = Object.fromEntries(
      Object.entries(sortable).map(([key, first]): [string, SortLink] => {
        const active = page.sort === key;
        const next = active ? (page.order === "desc" ? "asc" : "desc") : first;
        return [
          key,
          {
            href: relink(page, kept, {
              sort: key === "score" ? null : key,
              order: next === first ? null : next,
            }),
            active,
            order: active ? (page.order as "asc" | "desc") : first,
          },
        ];
      }),
    );
    const viewTabs: ViewTab[] = views.map(([view, name]) => ({
      view,
      label: name,
      count: page.view_counts[view as keyof typeof page.view_counts],
      href: relink(page, kept, { view: view === "all" ? null : view }),
      current: page.view === view,
    }));
    // Windows of the shown source; another source opens its own latest window.
    const latestEnd = page.windows.reduce(
      (latest, window) =>
        window.window_ends_before > latest ? window.window_ends_before : latest,
      "",
    );
    const windows: WindowOption[] = page.windows
      .filter((window) => window.source === run.source)
      .map((window) => ({
        scoreRunId: window.score_run_id,
        label: windowLabel(
          window.window_starts_on,
          window.window_ends_before,
          latestEnd,
        ),
      }));
    const sources: SourceTab[] = [
      ...new Set(page.windows.map((w) => w.source)),
    ].map((name) => {
      const window =
        page.windows.find((w) => w.source === name && w.active) ??
        page.windows.find((w) => w.source === name)!;
      return {
        source: name,
        label: name === "topdeck" ? "TopDeck" : name,
        href: `/rankings?${new URLSearchParams({ format: run.format_name, score_run_id: window.score_run_id })}`,
        current: name === run.source,
      };
    });
    const first = page.offset + 1;
    const last = page.offset + page.items.length;
    const more = Math.min(page.limit + 25, 100);
    const pageLink = (offset: number) =>
      link(page, offset ? [...kept, ["offset", String(offset)]] : kept);
    const source = run.source === "topdeck" ? "TopDeck" : run.source;
    return (
      <>
        <FormatBar tabs={tabs} current={run.format_name} />
        <section className="intro band rankings-intro">
          <div className="intro-inner band-inner">
            <div className="intro-copy">
              <div className="rankings-heading">
                <p className="eyebrow">Constructed card rankings</p>
                <h1>{label(run.format_name)}</h1>
                <p className="format-descriptor">
                  {descriptors[run.format_name] ??
                    `Competitive ${source} events`}
                </p>
                <p className="lead">
                  {graded
                    ? `Every card scored by how the decks that play it perform in tournaments: win rate against the field, top-cut conversion and ${labels.share.toLowerCase()}.`
                    : `Ranked by ${method.label.toLowerCase()}: how often each card was played, compared with the most-played card. It measures popularity in published decklists, not card strength.`}
                </p>
              </div>
              <dl className="stat-strip">
                <div>
                  <dt>Decklists</dt>
                  <dd>{count(run.decks)}</dd>
                </div>
                <div>
                  <dt>{run.matches === null ? "Players" : "Matches"}</dt>
                  <dd>{count(run.matches ?? run.players)}</dd>
                </div>
                <div>
                  <dt>Events</dt>
                  <dd>{count(run.events)}</dd>
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
            {podium.length === 3 && (
              <section className="podium" aria-label="Top ranked cards">
                <span className="podium-ring" aria-hidden="true" />
                <span className="podium-ring dashed" aria-hidden="true" />
                <ol>
                  {[1, 0, 2].map((place) => (
                    <Place
                      key={podium[place].oracle_id}
                      page={page}
                      card={podium[place]}
                      numeral={["I", "II", "III"][place]}
                      graded={graded}
                    />
                  ))}
                </ol>
              </section>
            )}
          </div>
        </section>
        <RankingFilters
          format={run.format_name}
          scoreRunId={run.score_run_id}
          query={new URLSearchParams(kept).toString()}
          clearHref={link(page)}
          views={viewTabs}
          windows={windows}
          sources={sources}
        />
        <section aria-labelledby="ranking-heading" className="ranking-results">
          <h2 id="ranking-heading" className="sr-only">
            {label(run.format_name)} rankings
          </h2>
          <RankingTable
            items={page.items}
            run={run}
            method={method}
            graded={graded}
            labels={labels}
            sorts={sorts}
            maxDeckCount={page.max_deck_count}
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
                  {last < page.total &&
                    (page.limit < 100 && page.offset === 0 ? (
                      <Link
                        className="button secondary sm"
                        href={relink(page, kept, { limit: String(more) })}
                        scroll={false}
                      >
                        Load {more - page.limit} more
                      </Link>
                    ) : (
                      <Link
                        className="button secondary sm"
                        href={pageLink(last)}
                      >
                        Next {page.limit} <Icon name="arrow-right" size={14} />
                      </Link>
                    ))}
                </div>
              </>
            }
          />
          <p className="cohort-note">
            Counts come from published decklists at competitive events with at
            least half their lists published; basic lands are not ranked. A top
            cut counts only where the result is known, and win rates come from
            reported match records. Ranks keep their place when you filter.
          </p>
        </section>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
