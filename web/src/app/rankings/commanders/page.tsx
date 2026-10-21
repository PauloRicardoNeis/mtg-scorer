import type { Metadata } from "next";
import Link from "next/link";
import {
  api,
  ApiError,
  type CommanderPage,
  type RankedCommander,
} from "@/lib/api";
import { queryParams, rankedCardHref, type SearchParams } from "@/lib/urls";
import { useI18n } from "#i18n";
import { getI18n } from "@/i18n/server";
import type { Messages } from "@/i18n/types";
import { Problem } from "@/components/problem";
import { CardImage } from "@/components/card-image";
import { Icon } from "@/components/icon";
import { FormatBar, type FormatTab } from "@/components/format-bar";
import { designFormats, formatLabel as label } from "@/lib/formats";
import {
  RankingFilters,
  type KindTab,
  type MinDecksOption,
  type SortOption,
  type WindowOption,
} from "@/components/ranking-filters";
import { trendLabel } from "@/components/ranking-data";
import { CommanderTable } from "@/components/commander-table";
import type { SortLink } from "@/components/ranking-table";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getI18n()).t.meta.commanders };
}

/** Sorts a header can apply, and the direction a first click uses. */
const sortable: Record<string, "asc" | "desc"> = {
  name: "asc",
  decks: "desc",
  win_rate: "desc",
  top_cut_lift: "desc",
  trend: "desc",
};

/** The minimum decks a reader can ask for: enough to quiet one-deck win rates. */
const minimums = [5, 10, 25, 50, 100, 250];

/** A link within the same pinned run, keeping only the given filters. */
function link(page: CommanderPage, filters: [string, string][] = []) {
  const query = new URLSearchParams([
    ["format", page.score_run.format_name],
    ["score_run_id", page.score_run.score_run_id],
    ...filters,
  ]);
  return `/rankings/commanders?${query}`;
}

/** Replaces some filters and drops the page offset, which no longer applies. */
function relink(
  page: CommanderPage,
  kept: [string, string][],
  changes: Record<string, string | null>,
) {
  const rest = kept.filter(([key]) => !(key in changes) && key !== "offset");
  const set = Object.entries(changes).flatMap(([key, value]) =>
    value === null ? [] : [[key, value] as [string, string]],
  );
  return link(page, [...rest, ...set]);
}

/** One podium place: the commander's cards, its numeral above and its share below. */
function Place({
  page,
  commander,
  numeral,
}: {
  page: CommanderPage;
  commander: RankedCommander;
  numeral: string;
}) {
  const { t, fill, share } = useI18n();
  const first = numeral === "I";
  const pair = commander.commanders.length > 1;
  const rank = fill(t.rankings.rank, {
    rank: commander.rank,
    name: commander.label,
  });
  return (
    <li data-place={numeral} className="podium-commander">
      <span className="podium-place" aria-hidden="true">
        {numeral}
      </span>
      <div className={pair ? "podium-card podium-pair" : "podium-card"}>
        {commander.commanders.map((card) => {
          const href = rankedCardHref(card, page.catalog_snapshot_id);
          const image = card.preview_printing ? (
            <CardImage
              src={card.preview_printing.images[0]?.source_uri ?? null}
              alt={card.name}
              featured={first && !pair}
              interactive
            />
          ) : (
            <div className="podium-placeholder">{card.name}</div>
          );
          return href ? (
            <Link
              key={card.oracle_id}
              href={href}
              aria-label={pair ? card.name : rank}
            >
              {image}
            </Link>
          ) : (
            <span key={card.oracle_id}>{image}</span>
          );
        })}
      </div>
      <p className="podium-stats">
        <span className="sr-only">{rank}. </span>
        <span className="podium-score">
          {share(commander.deck_count, page.score_run.decks)}
        </span>
        <span>{commander.label}</span>
      </p>
    </li>
  );
}

export default async function Commanders({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  // Without JavaScript the filters submit as a GET form, so unset fields arrive
  // as empty values; the API accepts only set ones.
  const query = new URLSearchParams(
    [...queryParams(await searchParams)].filter(([, value]) => value !== ""),
  );
  const i18n = await getI18n();
  const { t, fill, plural, rich, count } = i18n;
  try {
    const page = await api.commanders(query);
    const run = page.score_run;
    const formatName = label(run.format_name);
    const source = run.source === "topdeck" ? "TopDeck" : run.source;
    // Formats whose active run ranks commanders; Commander leads, as on the card rankings.
    const ranked = page.formats.filter((format) => format.commanders > 0);
    const tabs: FormatTab[] = [
      ...designFormats
        .filter(([, format]) => ranked.some((f) => f.format_name === format))
        .map(([tab, format]) => ({
          label: tab,
          format,
          decks: ranked.find((f) => f.format_name === format)!.decks,
        })),
      ...ranked
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
    // A run without commanders, e.g. an older window, can still be opened.
    if (!tabs.some((tab) => tab.format === run.format_name))
      tabs.push({
        label: formatName,
        format: run.format_name,
        decks: run.decks,
      });
    const kept = [...query].filter(([key]) =>
      ["q", "color", "min_decks", "sort", "order", "limit"].includes(key),
    );
    const filtered = kept.some(([key]) =>
      ["q", "color", "min_decks"].includes(key),
    );
    // The most decks any commander leads, counted before filters.
    const ranksCommanders = page.max_deck_count > 0;
    // Minimums up to the most-played commander's decks, so none empties the table.
    const minDecks: MinDecksOption[] = [
      { value: "", label: t.commanders.anyDecks },
      ...minimums
        .filter((decks) => decks <= page.max_deck_count)
        .map((decks) => ({
          value: String(decks),
          label: fill(t.commanders.atLeast, { count: count(decks) }),
        })),
    ];
    const commanderCount =
      [...page.windows, ...page.formats].find(
        (entry) => entry.score_run_id === run.score_run_id,
      )?.commanders ?? page.total;
    const podium =
      page.offset === 0 &&
      page.sort === "decks" &&
      page.order === "desc" &&
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
              sort: key === "decks" ? null : key,
              order: next === first ? null : next,
            }),
            active,
            order: active ? page.order : first,
          },
        ];
      }),
    );
    // The filter menu offers the headers' sorts under their names, the default
    // first, then the places a commander moved.
    const trend = trendLabel(run, i18n);
    const sortOptions: SortOption[] = (
      [
        ["decks", t.rankings.metaShare],
        ["name", t.commanders.commander],
        ["win_rate", t.rankingTable.winRateVsField],
        ["top_cut_lift", t.rankings.topCut],
        [
          "trend",
          trend
            ? fill(t.rankingTable.trendOver, { period: trend })
            : t.rankingTable.trend,
        ],
        ["movement", t.rankings.sortMovement],
      ] as [string, string][]
    ).map(([key, name]) => ({
      value: key === "decks" ? "" : key,
      label: name,
      order: sortable[key] ?? "desc",
    }));
    // Cards and commanders of the same run; colors apply to both.
    const colors = kept.filter(([key]) => key === "color");
    const pinned: [string, string][] = [
      ["format", run.format_name],
      ["score_run_id", run.score_run_id],
    ];
    const kinds: KindTab[] = [
      {
        label: t.commanders.cards,
        href: `/rankings?${new URLSearchParams([...pinned, ...colors])}`,
        current: false,
      },
      {
        label: t.commanders.commanders,
        href: link(page, colors),
        current: true,
      },
    ];
    // Windows of the shown source that rank commanders.
    const latestEnd = page.windows.reduce(
      (latest, window) =>
        window.window_ends_before > latest ? window.window_ends_before : latest,
      "",
    );
    const windows: WindowOption[] = page.windows
      .filter(
        (window) =>
          window.source === run.source &&
          (window.commanders > 0 || window.score_run_id === run.score_run_id),
      )
      .map((window) => ({
        scoreRunId: window.score_run_id,
        label: i18n.windowLabel(
          window.window_starts_on,
          window.window_ends_before,
          latestEnd,
        ),
      }));
    const first = page.offset + 1;
    const last = page.offset + page.items.length;
    const more = Math.min(page.limit + 25, 100);
    const pageLink = (offset: number) =>
      link(page, offset ? [...kept, ["offset", String(offset)]] : kept);
    return (
      <>
        <FormatBar
          tabs={tabs}
          current={run.format_name}
          path="/rankings/commanders"
          compare={false}
        />
        <section className="intro band rankings-intro">
          <div className="intro-inner band-inner">
            <div className="intro-copy">
              <div className="rankings-heading">
                <p className="eyebrow">{t.commanders.eyebrow}</p>
                <h1>{formatName}</h1>
                <p className="format-descriptor">
                  {t.formats.descriptors[
                    run.format_name as keyof Messages["formats"]["descriptors"]
                  ] ?? fill(t.formats.competitiveEvents, { source })}
                </p>
                <p className="lead">{t.commanders.lead}</p>
              </div>
              <dl className="stat-strip">
                <div>
                  <dt>{t.rankings.decklists}</dt>
                  <dd>{count(run.decks)}</dd>
                </div>
                <div>
                  <dt>{t.commanders.count}</dt>
                  <dd>{count(commanderCount)}</dd>
                </div>
                <div>
                  <dt>{t.rankings.events}</dt>
                  <dd>{count(run.events)}</dd>
                </div>
                <div>
                  <dt>{t.rankings.window}</dt>
                  <dd>
                    {i18n.dateWindow(
                      run.window_starts_on,
                      run.window_ends_before,
                    )}
                  </dd>
                </div>
              </dl>
              <p className="freshness">
                <span className="pulse" aria-hidden="true" />
                <span>
                  {rich(t.rankings.updated, {
                    time: (
                      <time
                        dateTime={run.published_at}
                        title={fill(t.rankings.publishedAt, {
                          date: i18n.dateTime(run.published_at),
                        })}
                      >
                        {i18n.ago(run.published_at)}
                      </time>
                    ),
                    source:
                      run.source === "topdeck" ? (
                        <a href="https://topdeck.gg" rel="noreferrer">
                          TopDeck.gg
                        </a>
                      ) : (
                        run.attribution
                      ),
                  })}
                </span>
              </p>
            </div>
            {podium.length === 3 && (
              <section className="podium" aria-label={t.commanders.podium}>
                <span className="podium-ring" aria-hidden="true" />
                <span className="podium-ring dashed" aria-hidden="true" />
                <ol>
                  {[1, 0, 2].map((place) => (
                    <Place
                      key={podium[place].label}
                      page={page}
                      commander={podium[place]}
                      numeral={["I", "II", "III"][place]}
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
          windows={windows}
          kinds={kinds}
          action="/rankings/commanders"
          types={false}
          fields={false}
          minDecks={minDecks}
          sorts={sortOptions}
          search={t.search.commanders}
          perPage={t.commanders.perPage}
          label={t.commanders.filters}
          updating={t.commanders.updating}
        />
        <section
          aria-labelledby="commander-heading"
          className="ranking-results"
        >
          <h2 id="commander-heading" className="sr-only">
            {fill(t.rankings.heading, { format: formatName })}
          </h2>
          {ranksCommanders ? (
            <CommanderTable
              items={page.items}
              run={run}
              sorts={sorts}
              shareLabel={t.rankings.metaShare}
              trendLabel={trend}
              maxDeckCount={page.max_deck_count}
              catalogSnapshotId={page.catalog_snapshot_id}
              clearHref={link(page)}
              footer={
                <>
                  <p role="status">
                    {page.total === 0
                      ? t.commanders.noneMatch
                      : plural(t.commanders.range, page.total, {
                          first,
                          last,
                        })}
                  </p>
                  <div className="pagination-links">
                    {page.offset > 0 && (
                      <Link
                        className="button secondary sm"
                        href={pageLink(Math.max(0, page.offset - page.limit))}
                      >
                        <Icon name="arrow-left" size={14} /> {t.common.previous}
                      </Link>
                    )}
                    {last < page.total &&
                      (page.limit < 100 && page.offset === 0 ? (
                        <Link
                          className="button secondary sm"
                          href={relink(page, kept, { limit: String(more) })}
                          scroll={false}
                        >
                          {fill(t.common.loadMore, {
                            count: more - page.limit,
                          })}
                        </Link>
                      ) : (
                        <Link
                          className="button secondary sm"
                          href={pageLink(last)}
                        >
                          {fill(t.common.next, { count: page.limit })}{" "}
                          <Icon name="arrow-right" size={14} />
                        </Link>
                      ))}
                  </div>
                </>
              }
            />
          ) : (
            <div className="ranking-frame">
              <div className="ranking-empty">
                <h3>{fill(t.commanders.noneTitle, { format: formatName })}</h3>
                <p>{t.commanders.noneBody}</p>
                <Link
                  className="button secondary"
                  href={`/rankings?${new URLSearchParams(pinned)}`}
                >
                  {fill(t.commanders.rankCards, { format: formatName })}
                </Link>
              </div>
            </div>
          )}
          <p className="cohort-note">{t.commanders.note}</p>
        </section>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
