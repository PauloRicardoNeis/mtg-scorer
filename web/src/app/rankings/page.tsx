import type { Metadata } from "next";
import Link from "next/link";
import type { CSSProperties } from "react";
import { api, ApiError, type RankedCard, type RankingPage } from "@/lib/api";
import { queryParams, type SearchParams } from "@/lib/urls";
import { count, dateWindow, share } from "@/lib/format";
import { Problem } from "@/components/problem";
import { CardImages } from "@/components/card-image";
import { Icon } from "@/components/icon";
import { ColorDots, ColorFilter, ManaCost } from "@/components/mana";
import { UnderlineTabs } from "@/components/primitives";

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

const cardTypes = [
  ["creature", "Creatures"],
  ["planeswalker", "Planeswalkers"],
  ["instant", "Instants"],
  ["sorcery", "Sorceries"],
  ["artifact", "Artifacts"],
  ["enchantment", "Enchantments"],
  ["land", "Lands"],
];

const sorts = [
  ["score", "Relative volume"],
  ["decks", "Decks"],
  ["top_cuts", "Top cuts"],
  ["name", "Name A–Z"],
];

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
  if (!card.preview_printing || !page.catalog_snapshot_id)
    return <span>{card.name}</span>;
  return (
    <Link
      href={`/cards/${card.oracle_id}?catalog_snapshot_id=${page.catalog_snapshot_id}`}
    >
      {card.name}
    </Link>
  );
}

function TopCuts({ card }: { card: RankedCard }) {
  if (card.top_cut_count === null)
    return <span className="muted">Unknown</span>;
  return (
    <span>
      {count(card.top_cut_count)}
      <small> of {count(card.top_cut_known_decks)} known</small>
    </span>
  );
}

export default async function Rankings({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  // The filter form is a plain GET form, so unset fields arrive as empty values;
  // the API accepts only set ones.
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
              <p className="eyebrow">Constructed card rankings</p>
              <h1>{run.format_name}</h1>
              <p className="mono-label">
                Competitive {run.source === "topdeck" ? "TopDeck" : run.source}{" "}
                events ·{" "}
                {dateWindow(run.window_starts_on, run.window_ends_before)}
              </p>
              <p className="lead">
                Ranked by {method.label.toLowerCase()}: how often each card was
                played, compared with the most-played card. It measures
                popularity in published decklists, not card strength.
              </p>
            </div>
            <aside className="sample-note">
              <span className="tag">Published score run</span>
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
              </dl>
              <p className="credit">
                {run.source === "topdeck" ? (
                  <>
                    Data provided by{" "}
                    <a href="https://topdeck.gg" rel="noreferrer">
                      TopDeck.gg
                    </a>
                  </>
                ) : (
                  run.attribution
                )}
                {" · "}published {run.published_at.slice(0, 10)}
              </p>
            </aside>
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
        <form className="toolbar band" action="/rankings" method="get">
          <div className="toolbar-inner band-inner">
            <input type="hidden" name="format" value={run.format_name} />
            <input type="hidden" name="score_run_id" value={run.score_run_id} />
            <div className="search-field">
              <label htmlFor="q">Card name</label>
              <div className="field">
                <Icon name="search" size={15} />
                <input
                  id="q"
                  name="q"
                  type="search"
                  maxLength={100}
                  defaultValue={query.get("q") ?? ""}
                />
              </div>
            </div>
            <ColorFilter
              label="Colors"
              name="color"
              selected={query.getAll("color")}
            />
            <div className="toolbar-field">
              <label htmlFor="type">Card type</label>
              <span className="select">
                <select
                  id="type"
                  name="type"
                  defaultValue={query.get("type") ?? ""}
                >
                  <option value="">All card types</option>
                  {cardTypes.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </span>
            </div>
            <div className="toolbar-field">
              <label htmlFor="sort">Sort by</label>
              <span className="select">
                <select id="sort" name="sort" defaultValue={sort}>
                  {sorts.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </span>
            </div>
            <div className="filter-actions">
              <button type="submit">Apply</button>
              <Link className="button ghost" href={link(page)}>
                Clear filters
              </Link>
            </div>
          </div>
        </form>
        <section aria-labelledby="ranking-heading" className="results">
          <div className="results-heading">
            <h2 id="ranking-heading">{run.format_name} rankings</h2>
            <p role="status">
              {page.total === 0
                ? "No ranked cards match"
                : `${count(first)}–${count(last)} of ${count(page.total)} ranked cards`}
            </p>
          </div>
          {page.items.length === 0 ? (
            <div className="state">
              <h3>No ranked cards match.</h3>
              <p>Loosen a filter or search a different name.</p>
              <Link className="button secondary sm" href={link(page)}>
                Clear filters
              </Link>
            </div>
          ) : (
            <div className="ranking-table-wrap">
              <table className="ranking-table">
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Card</th>
                    <th scope="col">{method.label}</th>
                    <th scope="col">Decks</th>
                    <th scope="col">Events</th>
                    <th scope="col">Top cuts</th>
                    <th scope="col">Most played in</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((card) => (
                    <tr key={card.oracle_id}>
                      <td className="rank">{card.rank}</td>
                      <th scope="row" className="card-cell">
                        <CardName page={page} card={card} />
                        <span className="card-meta">
                          {card.mana_cost && <ManaCost cost={card.mana_cost} />}
                          {card.type_line ? (
                            <span>{card.type_line}</span>
                          ) : (
                            <span className="muted">Not in this catalog</span>
                          )}
                          {card.color_identity && (
                            <ColorDots values={card.color_identity} />
                          )}
                        </span>
                      </th>
                      <td className="score-cell">
                        {card.score === null ? (
                          <span className="muted">Unknown</span>
                        ) : (
                          <>
                            <span>{card.score.toFixed(1)}</span>
                            <span
                              className="bar"
                              aria-hidden="true"
                              style={
                                {
                                  "--fill": `${Math.max(0, Math.min(100, card.score))}%`,
                                } as CSSProperties
                              }
                            />
                          </>
                        )}
                      </td>
                      <td>
                        {count(card.deck_count)}
                        <small> {share(card.deck_count, run.decks)}</small>
                      </td>
                      <td>{count(card.event_count)}</td>
                      <td>
                        <TopCuts card={card} />
                      </td>
                      <td>
                        {card.archetype_label ? (
                          <span>
                            {card.archetype_label}
                            <small>
                              {" "}
                              {count(card.archetype_deck_count)} of{" "}
                              {count(card.labelled_deck_count)}
                            </small>
                          </span>
                        ) : (
                          <span className="muted">Unlabelled</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pagination">
            {page.offset > 0 && (
              <Link
                className="button secondary"
                href={pageLink(Math.max(0, page.offset - page.limit))}
              >
                <Icon name="arrow-left" size={14} /> Previous
              </Link>
            )}
            {last < page.total && (
              <Link className="button secondary" href={pageLink(last)}>
                Next {page.limit} <Icon name="arrow-right" size={14} />
              </Link>
            )}
          </div>
        </section>
        <aside className="method-note">
          <Icon name="info" size={18} />
          <strong>
            {method.label}, {method.method_version}.
          </strong>
          <p>
            {method.description} Counts come from published decklists at
            competitive events with at least half their lists published; basic
            lands are not ranked. A top cut counts only where the result is
            known. Ranks keep their place when you filter.
          </p>
        </aside>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
