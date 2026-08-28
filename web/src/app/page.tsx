import { CardScores, CardSort, CatalogFilters, searchCards } from "@/lib/catalog";
import { connection } from "next/server";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const SORT_OPTIONS: Array<{ value: CardSort; label: string }> = [
  { value: "BUILDAROUND", label: "Build-around" },
  { value: "STAPLE", label: "Staple" },
  { value: "EVIDENCE", label: "Evidence" },
  { value: "DISTINCTIVENESS", label: "Distinctiveness" },
];

export default async function Home({ searchParams }: { searchParams: SearchParams }) {
  await connection();
  const rawParams = await searchParams;
  const filters: CatalogFilters = {
    query: single(rawParams.query),
    set: single(rawParams.set),
    rarity: single(rawParams.rarity),
    sort: parseSort(single(rawParams.sort)),
  };

  let result: Awaited<ReturnType<typeof searchCards>> | null = null;
  let error: string | null = null;
  try {
    result = await searchCards(filters);
  } catch (cause) {
    error = cause instanceof Error ? cause.message : "The API could not be reached.";
  }

  return (
    <main>
      <header className="hero shell">
        <div className="eyebrow">MTG SCORER / FORGE DISCOVERY</div>
        <div className="hero-grid">
          <h1>Find the card that makes a deck inevitable.</h1>
          <p>
            Separate ubiquitous power from strategic identity. Every result carries its
            evidence, model, and data lineage instead of collapsing history into one opaque
            number.
          </p>
        </div>
      </header>

      <section className="workbench shell" aria-labelledby="discovery-title">
        <div className="section-heading">
          <div>
            <span className="section-number">01</span>
            <h2 id="discovery-title">Discovery surface</h2>
          </div>
          <span className="status">{result ? `${result.total} candidates` : "API offline"}</span>
        </div>

        <form className="filters" method="get">
          <label className="field field-wide">
            <span>Card name</span>
            <input name="query" defaultValue={filters.query} placeholder="Search Oracle cards" />
          </label>
          <label className="field">
            <span>Set</span>
            <input name="set" defaultValue={filters.set} placeholder="e.g. eng" />
          </label>
          <label className="field">
            <span>Rarity</span>
            <select name="rarity" defaultValue={filters.rarity}>
              <option value="">Any rarity</option>
              <option value="common">Common</option>
              <option value="uncommon">Uncommon</option>
              <option value="rare">Rare</option>
              <option value="mythic">Mythic</option>
            </select>
          </label>
          <label className="field">
            <span>Order by</span>
            <select name="sort" defaultValue={filters.sort}>
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit">Recalculate view</button>
        </form>

        {result?.catalogKind === "DEMONSTRATION" && (
          <aside className="notice">
            <strong>Contract demonstration.</strong> These observations are synthetic. They test
            the complete Python → Java → React path; they are not tournament claims.
          </aside>
        )}

        {error && (
          <aside className="error-state">
            <strong>The discovery API is unavailable.</strong>
            <span>{error}</span>
            <code>cd api &amp;&amp; mvn spring-boot:run</code>
          </aside>
        )}

        {result && (
          <div className="card-list">
            {result.cards.map((card, index) => (
              <article className="card-row" key={card.oracleId}>
                <div className="rank">{String(index + 1).padStart(2, "0")}</div>
                <div className="identity">
                  <div className="card-title-line">
                    <h3>{card.name}</h3>
                    <div className="colors" aria-label={`Colors: ${card.colors.join(", ") || "colorless"}`}>
                      {card.colors.length ? card.colors.map((color) => <i key={color}>{color}</i>) : <i>C</i>}
                    </div>
                  </div>
                  <div className="printings">
                    {card.printings.map((printing) => (
                      <span key={`${printing.setCode}-${printing.rarity}`}>
                        {printing.setCode.toUpperCase()} · {printing.rarity}
                      </span>
                    ))}
                  </div>
                  <ul className="reasons">
                    {card.reasons.map((reason) => <li key={reason}>{reason}</li>)}
                  </ul>
                </div>
                <ScorePanel scores={card.scores} />
              </article>
            ))}
            {!result.cards.length && (
              <div className="empty-state">No cards inhabit this part of the score surface.</div>
            )}
          </div>
        )}
      </section>

      {result && (
        <footer className="lineage shell">
          <div>
            <span>Dataset</span>
            <code>{result.snapshot.datasetSnapshotId}</code>
          </div>
          <div>
            <span>Feature pipeline</span>
            <code>{result.snapshot.featurePipelineVersion}</code>
          </div>
          <div>
            <span>Score model</span>
            <code>{result.snapshot.scoreModelVersion}</code>
          </div>
        </footer>
      )}
    </main>
  );
}

function ScorePanel({ scores }: { scores: CardScores }) {
  const scoreItems = [
    { label: "Staple", value: scores.staple },
    { label: "Build-around", value: scores.buildaroundSignal },
    { label: "Evidence", value: scores.evidence },
  ];

  return (
    <div className="score-panel">
      {scoreItems.map((score) => (
        <div className="score" key={score.label}>
          <div><span>{score.label}</span><strong>{score.value.toFixed(1)}</strong></div>
          <div className="track"><i style={{ width: `${score.value}%` }} /></div>
        </div>
      ))}
      <div className={`delta ${scores.distinctivenessDelta >= 0 ? "positive" : "negative"}`}>
        <span>Distinctiveness</span>
        <strong>{scores.distinctivenessDelta > 0 ? "+" : ""}{scores.distinctivenessDelta.toFixed(1)}</strong>
      </div>
    </div>
  );
}

function single(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function parseSort(value: string): CardSort {
  return SORT_OPTIONS.some((option) => option.value === value)
    ? (value as CardSort)
    : "BUILDAROUND";
}
