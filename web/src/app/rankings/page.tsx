import type { Metadata } from "next";
import Link from "next/link";
import { api, ApiError, type RankedCard, type RankingPage } from "@/lib/api";
import { queryParams, rankedCardHref, type SearchParams } from "@/lib/urls";
import {
  ago,
  count,
  dateWindow,
  dateWithYear,
  percent,
  windowLabel,
} from "@/lib/format";
import { Problem } from "@/components/problem";
import { CardImage } from "@/components/card-image";
import { Icon } from "@/components/icon";
import { FormatBar, type FormatTab } from "@/components/format-bar";
import {
  OVERALL_FORMAT,
  descriptors,
  designFormats,
  formatLabel as label,
} from "@/lib/formats";
import {
  RankingFilters,
  type GradingOption,
  type SourceTab,
  type ViewTab,
  type WindowOption,
} from "@/components/ranking-filters";
import {
  COMPARE_GRADINGS,
  GRADINGS,
  GradeRing,
  defaultMethod,
  isGraded,
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
  price: "desc",
  value: "desc",
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

/** Why a method could not score a run, shown beside it in the grading menu. */
const unavailable: Record<string, string> = {
  "signature-score": "needs archetype labels",
};

/**
 * One podium place: the card, its numeral above and its grade on the card's edge.
 * Under the signature score the place names the card's home archetype; overall,
 * how many formats grade the card.
 */
function Place({
  page,
  card,
  numeral,
  graded,
  signature,
  overall,
}: {
  page: RankingPage;
  card: RankedCard;
  numeral: string;
  graded: boolean;
  signature: boolean;
  overall: boolean;
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
        {signature ? (
          <span>
            {card.archetypes[0]?.label ?? card.archetype_label ?? "Unlabelled"}
          </span>
        ) : overall ? (
          <span>
            {card.formats?.length ?? 0}{" "}
            {card.formats?.length === 1 ? "format" : "formats"}
          </span>
        ) : card.win_rate !== null ? (
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
    const graded = isGraded(method.method_id);
    const signature = method.method_id === "signature-score";
    // The overall run combines every format's run, which its components name.
    const overall = Boolean(run.components);
    // A method that scored no card here, e.g. signature without archetype labels.
    const unscored = method.scored_cards === 0;
    const fallback = defaultMethod(run);
    // The grading follows every link, and other formats, unless it is the default.
    const chosen: [string, string][] =
      method.method_id === fallback ? [] : [["method", method.method_id]];
    // The comparison follows a grading it offers, unless that is its default.
    const compareChosen: [string, string][] =
      COMPARE_GRADINGS.indexOf(method.method_id) > 0
        ? [["method", method.method_id]]
        : [];
    const multiplayer = (run.players_per_game ?? 2) > 2;
    const labels = {
      share: overall ? "Decklists" : multiplayer ? "Inclusion" : "Meta share",
      cut: "Top cut",
      trend: overall ? null : trendLabel(run),
      value: graded ? "Grade per $" : "Score per $",
    };
    const decksOf = new Map(page.formats.map((f) => [f.format_name, f.decks]));
    const tabs: FormatTab[] = [
      {
        label: OVERALL_FORMAT,
        format: OVERALL_FORMAT,
        decks: decksOf.get(OVERALL_FORMAT) ?? null,
        overall: true,
      },
      ...designFormats.map(([tab, format]) => ({
        label: tab,
        format,
        decks: decksOf.get(format) ?? null,
      })),
      ...page.formats
        .filter(
          (f) =>
            f.format_name !== OVERALL_FORMAT &&
            !designFormats.some(([, format]) => format === f.format_name),
        )
        .map((f) => ({
          label: f.format_name,
          format: f.format_name,
          decks: f.decks,
        }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    ];
    const kept = [
      ...chosen,
      ...([...query].filter(([key]) =>
        ["q", "type", "color", "sort", "order", "view", "limit"].includes(key),
      ) as [string, string][]),
    ];
    const filtered = kept.some(([key]) => ["q", "type", "color"].includes(key));
    const podium =
      page.offset === 0 &&
      page.sort === "score" &&
      page.order === "desc" &&
      page.view === "all" &&
      !filtered &&
      !unscored
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
        href: `/rankings?${new URLSearchParams([["format", run.format_name], ["score_run_id", window.score_run_id], ...chosen])}`,
        current: name === run.source,
      };
    });
    const first = page.offset + 1;
    const last = page.offset + page.items.length;
    const more = Math.min(page.limit + 25, 100);
    const pageLink = (offset: number) =>
      link(page, offset ? [...kept, ["offset", String(offset)]] : kept);
    const source = run.source === "topdeck" ? "TopDeck" : run.source;
    const leads: Record<string, string> = {
      "constructed-score": `Every card scored by how the decks that play it perform in tournaments: win rate against the field, top-cut conversion and ${labels.share.toLowerCase()}.`,
      "signature-score":
        "Every card scored by how much it belongs to one strategy: how few archetypes play it, how much more often its home archetype plays it than other decks do, and how those decks perform. Staples played everywhere rank low.",
      "overall-grade":
        "One grade per card from its constructed grade in every format that ranks it. Formats count by how many decklists back them, and a card proven across many formats outranks one that is strong in a single format.",
      "max-ratio": `Ranked by ${method.label.toLowerCase()}: how often each card was played, compared with the most-played card. It measures popularity in published decklists, not card strength.`,
    };
    // The selected method is offered even when it is not one of the menu's gradings.
    const gradings: GradingOption[] = run.methods
      .filter(
        (candidate) =>
          GRADINGS.includes(candidate.method_id) || candidate === method,
      )
      .sort(
        (a, b) =>
          (GRADINGS.indexOf(a.method_id) + 1 || GRADINGS.length + 1) -
          (GRADINGS.indexOf(b.method_id) + 1 || GRADINGS.length + 1),
      )
      .map((candidate) => {
        // An API from before scored_cards omits it; that counts as scored.
        const empty = candidate.scored_cards === 0;
        return {
          value: candidate.method_id === fallback ? "" : candidate.method_id,
          label: empty
            ? `${candidate.label} · ${unavailable[candidate.method_id] ?? "no scores"}`
            : candidate.label,
          disabled: empty && candidate !== method,
        };
      });
    const fallbackLabel = run.methods.find(
      (candidate) => candidate.method_id === fallback,
    )!.label;
    return (
      <>
        <FormatBar
          tabs={tabs}
          current={run.format_name}
          query={new URLSearchParams(chosen).toString()}
          compareQuery={new URLSearchParams(compareChosen).toString()}
        />
        <section className="intro band rankings-intro">
          <div className="intro-inner band-inner">
            <div className="intro-copy">
              <div className="rankings-heading">
                <p className="eyebrow">
                  {overall
                    ? "Overall card rankings"
                    : "Constructed card rankings"}
                </p>
                <h1>{label(run.format_name)}</h1>
                <p className="format-descriptor">
                  {descriptors[run.format_name] ??
                    `Competitive ${source} events`}
                </p>
                <p className="lead">
                  {leads[method.method_id] ?? method.description}
                </p>
              </div>
              <dl className="stat-strip">
                <div>
                  <dt>Decklists</dt>
                  <dd>{count(run.decks)}</dd>
                </div>
                {overall ? (
                  <div>
                    <dt>Formats</dt>
                    <dd>{count(run.components!.length)}</dd>
                  </div>
                ) : (
                  <div>
                    <dt>{run.matches === null ? "Players" : "Matches"}</dt>
                    <dd>{count(run.matches ?? run.players)}</dd>
                  </div>
                )}
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
                      signature={signature}
                      overall={overall}
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
          clearHref={link(page, chosen)}
          views={viewTabs}
          windows={windows}
          sources={sources}
          gradings={gradings}
          method={chosen[0]?.[1] ?? ""}
        />
        <section aria-labelledby="ranking-heading" className="ranking-results">
          <h2 id="ranking-heading" className="sr-only">
            {label(run.format_name)} rankings
          </h2>
          {unscored ? (
            <div className="ranking-frame">
              <div className="ranking-empty">
                <h3>
                  No {method.label.toLowerCase()} for {label(run.format_name)}.
                </h3>
                <p>
                  {signature
                    ? `It needs archetype labels, and ${source} decklists for this format don't carry any.`
                    : "This method could not score any card in this window."}
                </p>
                <Link className="button secondary" href={link(page)}>
                  Rank by {fallbackLabel.toLowerCase()}
                </Link>
              </div>
            </div>
          ) : (
            <RankingTable
              items={page.items}
              run={run}
              method={method}
              graded={graded}
              labels={labels}
              sorts={sorts}
              maxDeckCount={page.max_deck_count}
              catalogSnapshotId={page.catalog_snapshot_id}
              pricesUpdatedAt={page.prices_updated_at}
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
                          Next {page.limit}{" "}
                          <Icon name="arrow-right" size={14} />
                        </Link>
                      ))}
                  </div>
                </>
              }
            />
          )}
          <p className="cohort-note">
            Counts come from published decklists at competitive events with at
            least half their lists published; basic lands are not ranked. A top
            cut counts only where the result is known, and win rates come from
            reported match records. Ranks keep their place when you filter.
            {overall &&
              " The overall grade combines each format's constructed grade. Win rates are not pooled across formats, since one-on-one and four-player games differ: vs field is each format's gap to its own field, weighted by games."}
            {page.prices_updated_at &&
              ` Prices are TCGplayer market estimates via Scryfall for each card's cheapest playable paper printing, as of ${dateWithYear(page.prices_updated_at)}.`}
          </p>
        </section>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
