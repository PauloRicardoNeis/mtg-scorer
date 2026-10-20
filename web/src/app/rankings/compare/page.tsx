import type { Metadata } from "next";
import Link from "next/link";
import { api, ApiError, type ComparePage } from "@/lib/api";
import { OVERALL_FORMAT, designFormats, formatLabel } from "@/lib/formats";
import { getI18n } from "@/i18n/server";
import type { Messages } from "@/i18n/types";
import { queryParams, type SearchParams } from "@/lib/urls";
import { CompareFilters, type PickOption } from "@/components/compare-filters";
import {
  CompareTable,
  STATS,
  SUMMARIES,
  type CompareSort,
  type CompareStat,
  type CompareSummary,
} from "@/components/compare-table";
import { FormatBar, type FormatTab } from "@/components/format-bar";
import { Icon } from "@/components/icon";
import { Problem } from "@/components/problem";
import { COMPARE_GRADINGS } from "@/components/ranking-data";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getI18n()).t.meta.compare };
}

const statOrder = Object.keys(STATS) as CompareStat[];
const summaryOrder = Object.keys(SUMMARIES) as CompareSummary[];
const everyDesignFormat = designFormats.map(([, format]) => format);

// The design's starting points: a format set and the stats to show for each.
const presets: [
  key: string,
  label: Extract<keyof Messages["compare"], `preset${string}`>,
  formats: string[],
  stats: CompareStat[],
][] = [
  ["grades", "presetGrades", everyDesignFormat, ["grade"]],
  ["wr", "presetWinRates", everyDesignFormat, ["win_rate"]],
  ["play", "presetPlayRates", everyDesignFormat, ["share"]],
  [
    "deep",
    "presetDeepDive",
    ["Modern", "Legacy", "Pauper"],
    ["grade", "win_rate", "share", "top_cut_lift", "trend"],
  ],
];

/** The comparison's gradings, named as the rankings page's menu names them. */
const gradingLabels: Record<string, string> = {
  "constructed-score": "Constructed score",
  "signature-score": "Signature score",
};

/** Why a grading leaves formats out, where it can say. */
const ungradedBecause: Record<string, "unlabelledFormats"> = {
  "signature-score": "unlabelledFormats",
};

function same(a: string[], b: string[]) {
  return a.length === b.length && a.every((value) => b.includes(value));
}

export default async function Compare({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = new URLSearchParams(
    [...queryParams(await searchParams)].filter(([, value]) => value !== ""),
  );
  // Without "picked", the page starts from the Grades preset.
  const picked = params.has("picked");
  const chosenStats = statOrder.filter((stat) =>
    params.getAll("stat").includes(stat),
  );
  const stats: CompareStat[] =
    picked && chosenStats.length ? chosenStats : ["grade"];
  const summaries: CompareSummary[] = picked
    ? summaryOrder.filter((summary) =>
        params.getAll("summary").includes(summary),
      )
    : ["best", "count"];
  // Empty for the default grading; a grading the comparison lacks is dropped.
  const requested = params.get("method") ?? "";
  const method = COMPARE_GRADINGS.indexOf(requested) > 0 ? requested : "";
  const chosenFormats = params.getAll("format");
  const wanted = chosenFormats.length ? chosenFormats : everyDesignFormat;
  const query = new URLSearchParams(wanted.map((format) => ["format", format]));
  if (method) query.set("method", method);
  for (const key of ["q", "every", "sort", "order", "limit", "offset"])
    if (params.get(key)) query.set(key, params.get(key)!);
  for (const color of params.getAll("color")) query.append("color", color);
  const { t, fill, plural, method: methodText, term } = await getI18n();
  // English names come from the menu; other languages translate them by id.
  const gradingName = (id: string) =>
    methodText({
      method_id: id,
      label: gradingLabels[id] ?? id,
      description: "",
    }).label;
  try {
    let page: ComparePage;
    try {
      page = await api.compare(query);
    } catch (error) {
      // None of the chosen formats has this grading: compare every format that does.
      if (
        !method ||
        !(error instanceof ApiError) ||
        error.code !== "rankings_unavailable"
      )
        throw error;
      query.delete("format");
      page = await api.compare(query);
    }
    const compared = page.formats.map((format) => format.format_name);
    // An API from before scored_cards omits it; that counts as graded.
    const graded = page.available.filter((f) => f.scored_cards !== 0);
    const because = ungradedBecause[page.method_id];
    // Formats the grading left out, e.g. a signature score without archetype labels.
    const gradedNote =
      graded.length < page.available.length
        ? [
            plural(t.compare.gradedFormats, page.available.length, {
              method: term(gradingName(page.method_id)),
              graded: graded.length,
            }),
            ...(because ? [t.compare[because]] : []),
          ].join(" ")
        : null;
    const grading: [string, string][] = method ? [["method", method]] : [];
    // Every link keeps the reader's choices and drops the offset, which no longer applies.
    const state: [string, string][] = [
      ["picked", "1"],
      ...grading,
      ...compared.map((format) => ["format", format] as [string, string]),
      ...stats.map((stat) => ["stat", stat] as [string, string]),
      ...summaries.map((summary) => ["summary", summary] as [string, string]),
      ...(["q", "every", "sort", "order", "limit"] as const).flatMap((key) =>
        params.get(key) ? [[key, params.get(key)!] as [string, string]] : [],
      ),
      ...params
        .getAll("color")
        .map((color) => ["color", color] as [string, string]),
    ];
    const href = (changes: Record<string, string | null>) => {
      const next = new URLSearchParams(
        state.filter(([key]) => !(key in changes)),
      );
      for (const [key, value] of Object.entries(changes))
        if (value !== null) next.set(key, value);
      return `/rankings/compare?${next}`;
    };
    const sorts = (key: string): CompareSort => {
      const first = key === "name" ? "asc" : "desc";
      const active = page.sort === key;
      const next = active ? (page.order === "desc" ? "asc" : "desc") : first;
      return {
        href: href({
          sort: key === "best" ? null : key,
          order: next === first ? null : next,
        }),
        active,
        order: active ? (page.order as "asc" | "desc") : first,
      };
    };
    const option = (
      values: string[],
      chosen: string[],
      label: (value: string) => string,
    ) =>
      values.map((value): PickOption => ({
        value,
        label: label(value),
        checked: chosen.includes(value),
      }));
    const current = presets.find(
      ([, , formats, presetStats]) =>
        same(
          formats.filter((f) => graded.some((a) => a.format_name === f)),
          compared,
        ) && same(presetStats, stats),
    )?.[0];
    const tabs: FormatTab[] = [
      {
        label: t.formats.overall,
        format: OVERALL_FORMAT,
        // An API from before active_formats omits it; the tab then waits for data.
        decks:
          page.active_formats?.find((f) => f.format_name === OVERALL_FORMAT)
            ?.decks ?? null,
        overall: true,
      },
      ...designFormats.map(([label, format]) => ({
        label,
        format,
        decks:
          page.available.find((f) => f.format_name === format)?.decks ?? null,
      })),
      ...page.available
        .filter((f) => !everyDesignFormat.includes(f.format_name))
        .map((f) => ({
          label: f.format_name,
          format: f.format_name,
          decks: f.decks,
        })),
    ];
    const first = page.offset + 1;
    const last = page.offset + page.items.length;
    const more = Math.min(page.limit + 50, 200);
    return (
      <>
        <FormatBar
          tabs={tabs}
          current={null}
          comparing
          query={new URLSearchParams(grading).toString()}
          compareQuery={new URLSearchParams(grading).toString()}
        />
        <section className="intro band compare-intro">
          <div className="compare-intro-inner band-inner">
            <div className="compare-heading">
              <p className="eyebrow">{t.compare.eyebrow}</p>
              <h1>{t.compare.title}</h1>
              <p className="lead">
                {t.compare.lead}
                {gradedNote && ` ${gradedNote}`}
              </p>
            </div>
            <div className="compare-presets">
              <p className="pick-label">{t.compare.startFrom}</p>
              <div className="compare-presets-row">
                <nav
                  className="segmented preset-links"
                  aria-label={t.compare.presets}
                >
                  {presets.map(([key, label, formats, presetStats]) => (
                    <Link
                      key={key}
                      href={`/rankings/compare?${new URLSearchParams([
                        ["picked", "1"],
                        ...grading,
                        ...formats.map((format) => ["format", format]),
                        ...presetStats.map((stat) => ["stat", stat]),
                        ["summary", "best"],
                        ["summary", "count"],
                      ])}`}
                      aria-current={current === key ? "page" : undefined}
                    >
                      {t.compare[label]}
                    </Link>
                  ))}
                </nav>
                {!current && (
                  <span className="tag tag-accent">{t.compare.custom}</span>
                )}
              </div>
            </div>
          </div>
        </section>
        <CompareFilters
          formats={option(
            graded.map((f) => f.format_name),
            compared,
            formatLabel,
          )}
          stats={option(
            statOrder,
            stats,
            (stat) => t.compare.statChips[stat as CompareStat],
          )}
          summaries={option(
            summaryOrder,
            summaries,
            (s) => t.compare.summaryChips[s as CompareSummary],
          )}
          every={page.every}
          query={new URLSearchParams(state).toString()}
          gradings={COMPARE_GRADINGS.map((id, index) => ({
            value: index === 0 ? "" : id,
            label: gradingName(id),
            disabled: false,
          }))}
          method={method}
        />
        <section className="compare-results" aria-labelledby="compare-heading">
          <h2 id="compare-heading" className="sr-only">
            {t.compare.heading}
          </h2>
          <CompareTable
            page={page}
            stats={stats}
            summaries={summaries}
            sorts={sorts}
            footer={
              <>
                <p role="status">
                  {page.total === 0
                    ? t.compare.noneMatch
                    : [
                        plural(t.compare.range, page.total, { first, last }),
                        plural(t.compare.formatCount, compared.length),
                        plural(
                          t.compare.columnCount,
                          compared.length * stats.length + summaries.length,
                        ),
                      ].join(" · ")}
                </p>
                <div className="pagination-links">
                  {page.offset > 0 && (
                    <Link
                      className="button secondary sm"
                      href={href({
                        offset: String(Math.max(0, page.offset - page.limit)),
                      })}
                    >
                      <Icon name="arrow-left" size={14} /> {t.common.previous}
                    </Link>
                  )}
                  {last < page.total &&
                    (page.limit < 200 && page.offset === 0 ? (
                      <Link
                        className="button secondary sm"
                        href={href({ limit: String(more) })}
                        scroll={false}
                      >
                        {fill(t.common.loadMore, { count: more - page.limit })}
                      </Link>
                    ) : (
                      <Link
                        className="button secondary sm"
                        href={href({ offset: String(last) })}
                      >
                        {fill(t.common.next, { count: page.limit })}{" "}
                        <Icon name="arrow-right" size={14} />
                      </Link>
                    ))}
                </div>
              </>
            }
          />
        </section>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
