import type { Metadata } from "next";
import Link from "next/link";
import { api, ApiError, type RankedCard, type RankingPage } from "@/lib/api";
import { queryParams, rankedCardHref, type SearchParams } from "@/lib/urls";
import { useI18n } from "#i18n";
import { getI18n } from "@/i18n/server";
import type { Messages } from "@/i18n/types";
import { Problem } from "@/components/problem";
import { CardImage } from "@/components/card-image";
import { Icon } from "@/components/icon";
import { FormatBar, type FormatTab } from "@/components/format-bar";
import {
  OVERALL_FORMAT,
  designFormats,
  formatLabel as label,
} from "@/lib/formats";
import {
  RankingFilters,
  type GradingOption,
  type KindTab,
  type SortOption,
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

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getI18n()).t.meta.rankings };
}

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

const views: [
  view: string,
  label: Extract<keyof Messages["rankings"], `view${string}`>,
][] = [
  ["all", "viewAll"],
  ["risers", "viewRisers"],
  ["fallers", "viewFallers"],
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
const unavailable: Record<string, "needsArchetypeLabels" | "needsPlaysets"> = {
  "signature-score": "needsArchetypeLabels",
  "hidden-gem-score": "needsPlaysets",
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
  const { t, fill, plural, percent, decimal } = useI18n();
  const href = rankedCardHref(card, page.catalog_snapshot_id);
  const first = numeral === "I";
  const rank = fill(t.rankings.rank, { rank: card.rank, name: card.name });
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
          <Link href={href} aria-label={rank}>
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
        <span className="sr-only">{rank}. </span>
        <span className="podium-score">
          {card.score === null ? "—" : decimal(card.score, 1)}
        </span>
        {signature ? (
          <span>
            {card.archetypes[0]?.label ??
              card.archetype_label ??
              t.rankingData.unlabelled}
          </span>
        ) : overall ? (
          <span>
            {plural(t.compare.formatCount, card.formats?.length ?? 0)}
          </span>
        ) : card.win_rate !== null ? (
          <span>
            {fill(t.rankings.winRate, { value: percent(100 * card.win_rate) })}
          </span>
        ) : (
          <span>{plural(t.rankings.decks, card.deck_count)}</span>
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
  const i18n = await getI18n();
  const { t, fill, plural, rich, count } = i18n;
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
      share: overall
        ? t.rankings.decklists
        : multiplayer
          ? t.rankings.inclusion
          : t.rankings.metaShare,
      cut: t.rankings.topCut,
      trend: overall ? null : trendLabel(run, i18n),
      value: graded ? t.rankings.gradePerDollar : t.rankings.scorePerDollar,
    };
    const { label: methodLabel } = i18n.method(method);
    const decksOf = new Map(page.formats.map((f) => [f.format_name, f.decks]));
    const tabs: FormatTab[] = [
      {
        label: t.formats.overall,
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
      ...[...query].filter(([key]) =>
        ["q", "in", "type", "color", "sort", "order", "view", "limit"].includes(
          key,
        ),
      ),
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
            order: active ? page.order : first,
          },
        ];
      }),
    );
    // The filter menu offers the headers' sorts in column order, then the places
    // a card moved, under the headers' names.
    const sortOptions: SortOption[] = (
      [
        ["score", graded ? t.rankingTable.grade : methodLabel],
        ["name", t.common.card],
        ["price", t.rankingTable.price],
        ["value", labels.value],
        [
          "win_rate",
          overall ? t.rankingTable.vsField : t.rankingTable.winRateVsField,
        ],
        ["decks", labels.share],
        ["top_cut_lift", labels.cut],
        ...(overall
          ? []
          : [
              [
                "trend",
                labels.trend
                  ? fill(t.rankingTable.trendOver, { period: labels.trend })
                  : t.rankingTable.trend,
              ],
              ["movement", t.rankings.sortMovement],
            ]),
      ] as [string, string][]
    ).map(([key, name]) => ({
      value: key === "score" ? "" : key,
      label: name,
      order: sortable[key] ?? "desc",
    }));
    const viewTabs: ViewTab[] = views.map(([view, name]) => ({
      view,
      label: t.rankings[name],
      count: page.view_counts[view as keyof typeof page.view_counts],
      href: relink(page, kept, { view: view === "all" ? null : view }),
      current: page.view === view,
    }));
    // A run whose decks name commanders ranks them too, on their own page; the
    // switch keeps the run and the colors, which apply to both.
    const commanderCount =
      [...page.windows, ...page.formats].find(
        (entry) => entry.score_run_id === run.score_run_id,
      )?.commanders ?? 0;
    const colors = kept.filter(([key]) => key === "color");
    const kinds: KindTab[] =
      commanderCount > 0
        ? [
            {
              label: t.commanders.cards,
              href: link(page, [...chosen, ...colors]),
              current: true,
            },
            {
              label: t.commanders.commanders,
              href: `/rankings/commanders?${new URLSearchParams([
                ["format", run.format_name],
                ["score_run_id", run.score_run_id],
                ...colors,
              ])}`,
              current: false,
            },
          ]
        : [];
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
        label: i18n.windowLabel(
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
    // Format names stay as published, but "Overall" is a word, not a name.
    const formatName = overall ? t.formats.overall : label(run.format_name);
    const leads: Record<string, string> = {
      "constructed-score": multiplayer
        ? t.rankings.leadGradedInclusion
        : t.rankings.leadGraded,
      "signature-score": t.rankings.leadSignature,
      "hidden-gem-score": t.rankings.leadHiddenGem,
      "overall-grade": t.rankings.leadOverall,
      "max-ratio": fill(t.rankings.leadMethod, {
        method: i18n.term(methodLabel),
      }),
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
        const name = i18n.method(candidate).label;
        const why = unavailable[candidate.method_id];
        return {
          value: candidate.method_id === fallback ? "" : candidate.method_id,
          label: empty
            ? `${name} · ${why ? t.rankings[why] : t.rankings.noScores}`
            : name,
          disabled: empty && candidate !== method,
        };
      });
    const fallbackLabel = i18n.method(
      run.methods.find((candidate) => candidate.method_id === fallback)!,
    ).label;
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
                  {overall ? t.rankings.eyebrowOverall : t.rankings.eyebrow}
                </p>
                <h1>{formatName}</h1>
                <p className="format-descriptor">
                  {t.formats.descriptors[
                    run.format_name as keyof Messages["formats"]["descriptors"]
                  ] ?? fill(t.formats.competitiveEvents, { source })}
                </p>
                <p className="lead">
                  {leads[method.method_id] ?? i18n.method(method).description}
                </p>
              </div>
              <dl className="stat-strip">
                <div>
                  <dt>{t.rankings.decklists}</dt>
                  <dd>{count(run.decks)}</dd>
                </div>
                {overall ? (
                  <div>
                    <dt>{t.formats.label}</dt>
                    <dd>{count(run.components!.length)}</dd>
                  </div>
                ) : (
                  <div>
                    <dt>
                      {run.matches === null
                        ? t.rankings.players
                        : t.rankings.matches}
                    </dt>
                    <dd>{count(run.matches ?? run.players)}</dd>
                  </div>
                )}
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
              <section className="podium" aria-label={t.rankings.podium}>
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
          kinds={kinds}
          sorts={sortOptions}
        />
        <section aria-labelledby="ranking-heading" className="ranking-results">
          <h2 id="ranking-heading" className="sr-only">
            {fill(t.rankings.heading, { format: formatName })}
          </h2>
          {unscored ? (
            <div className="ranking-frame">
              <div className="ranking-empty">
                <h3>
                  {fill(t.rankings.unscoredTitle, {
                    method: i18n.term(methodLabel),
                    format: formatName,
                  })}
                </h3>
                <p>
                  {signature
                    ? fill(t.rankings.unscoredSignature, { source })
                    : method.method_id === "hidden-gem-score"
                      ? t.rankings.unscoredHiddenGem
                      : t.rankings.unscoredBody}
                </p>
                <Link className="button secondary" href={link(page)}>
                  {fill(t.rankings.rankBy, {
                    method: i18n.term(fallbackLabel),
                  })}
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
                      ? t.rankings.noneMatch
                      : plural(t.rankings.range, page.total, { first, last })}
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
          )}
          <p className="cohort-note">
            {t.rankings.cohortNote}
            {overall && ` ${t.rankings.overallNote}`}
            {page.prices_updated_at &&
              ` ${fill(t.rankings.pricesNote, {
                date: i18n.dateWithYear(page.prices_updated_at),
              })}`}
          </p>
        </section>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
