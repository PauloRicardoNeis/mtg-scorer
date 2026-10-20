import type { Metadata } from "next";
import Link from "next/link";
import { api, ApiError, type ComparePage } from "@/lib/api";
import { count } from "@/lib/format";
import { OVERALL_FORMAT, designFormats, formatLabel } from "@/lib/formats";
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

export const metadata: Metadata = { title: "MTG Scorer · Compare formats" };

const statOrder = Object.keys(STATS) as CompareStat[];
const summaryOrder = Object.keys(SUMMARIES) as CompareSummary[];
const everyDesignFormat = designFormats.map(([, format]) => format);

// The design's starting points: a format set and the stats to show for each.
const presets: [
  key: string,
  label: string,
  formats: string[],
  stats: CompareStat[],
][] = [
  ["grades", "Grades", everyDesignFormat, ["grade"]],
  ["wr", "Win rates", everyDesignFormat, ["win_rate"]],
  ["play", "Play rates", everyDesignFormat, ["share"]],
  [
    "deep",
    "Deep dive",
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
const ungradedBecause: Record<string, string> = {
  "signature-score": "have no archetype labels",
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
        ? `The ${(gradingLabels[page.method_id] ?? page.method_id).toLowerCase()} grades ${graded.length} of ${page.available.length} formats${because ? `; the others ${because}` : ""}.`
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
        label: OVERALL_FORMAT,
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
              <p className="eyebrow">Compare formats</p>
              <h1>Across formats</h1>
              <p className="lead">
                Pick the formats and stats to show. Each row is a card and each
                column group is a format. A dash means the card isn&rsquo;t
                ranked there.{gradedNote && ` ${gradedNote}`}
              </p>
            </div>
            <div className="compare-presets">
              <p className="pick-label">Start from</p>
              <div className="compare-presets-row">
                <nav className="segmented preset-links" aria-label="Presets">
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
                      {label}
                    </Link>
                  ))}
                </nav>
                {!current && <span className="tag tag-accent">Custom</span>}
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
            (stat) => STATS[stat as CompareStat].chip,
          )}
          summaries={option(
            summaryOrder,
            summaries,
            (s) => SUMMARIES[s as CompareSummary].chip,
          )}
          every={page.every}
          query={new URLSearchParams(state).toString()}
          gradings={COMPARE_GRADINGS.map((id, index) => ({
            value: index === 0 ? "" : id,
            label: gradingLabels[id] ?? id,
            disabled: false,
          }))}
          method={method}
        />
        <section className="compare-results" aria-labelledby="compare-heading">
          <h2 id="compare-heading" className="sr-only">
            Cards across formats
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
                    ? "No cards match"
                    : `${count(first)}–${count(last)} of ${count(page.total)} cards · ${compared.length} ${compared.length === 1 ? "format" : "formats"} · ${compared.length * stats.length + summaries.length} columns`}
                </p>
                <div className="pagination-links">
                  {page.offset > 0 && (
                    <Link
                      className="button secondary sm"
                      href={href({
                        offset: String(Math.max(0, page.offset - page.limit)),
                      })}
                    >
                      <Icon name="arrow-left" size={14} /> Previous
                    </Link>
                  )}
                  {last < page.total &&
                    (page.limit < 200 && page.offset === 0 ? (
                      <Link
                        className="button secondary sm"
                        href={href({ limit: String(more) })}
                        scroll={false}
                      >
                        Load {more - page.limit} more
                      </Link>
                    ) : (
                      <Link
                        className="button secondary sm"
                        href={href({ offset: String(last) })}
                      >
                        Next {page.limit} <Icon name="arrow-right" size={14} />
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
