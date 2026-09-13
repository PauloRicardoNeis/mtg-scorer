import Link from "next/link";
import { redirect } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { colors, queryParams, type SearchParams } from "@/lib/urls";
import { Filters } from "@/components/filters";
import { CopySearch } from "@/components/actions";
import { Problem } from "@/components/problem";
import { CardImages } from "@/components/card-image";

export default async function Cards({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const query = queryParams(await searchParams);
  try {
    const page = await api.cards(query);
    if (!query.has("catalog_snapshot_id")) {
      query.set("catalog_snapshot_id", page.catalog_snapshot_id);
      redirect(`/cards?${query}`);
    }
    const snapshot = await api.snapshot(page.catalog_snapshot_id);
    const detailQuery = new URLSearchParams(query);
    detailQuery.delete("cursor");
    const next = new URLSearchParams(query);
    if (page.next_cursor) next.set("cursor", page.next_cursor);
    return (
      <>
        <section className="intro">
          <div>
            <p className="eyebrow">The card catalog</p>
            <h1>
              Find something
              <br />
              <em>worth building around.</em>
            </h1>
            <p>
              Start with the cards in your pool. Explore names, faces and the
              printings that fit.
            </p>
          </div>
          <aside className="sample-note">
            <span className="badge">Bounded real sample</span>
            <p>
              {snapshot.card_count} cards · {snapshot.printing_count} printings
            </p>
            <p>Source retrieved {snapshot.retrieved_to.slice(0, 10)}</p>
            <Link href={`/datasets/${page.catalog_snapshot_id}`}>
              Inspect this dataset <span aria-hidden="true">↗</span>
            </Link>
          </aside>
        </section>
        <Filters
          key={query.toString()}
          snapshot={snapshot}
          query={query.toString()}
        />
        <section aria-labelledby="results-heading" className="results">
          <div className="results-heading">
            <h2 id="results-heading">Your discovery</h2>
            <p role="status">
              {page.items.length} {page.items.length === 1 ? "card" : "cards"}{" "}
              on this page · Name A–Z
            </p>
          </div>
          {page.items.length === 0 ? (
            <div className="state">
              <h3>No cards match this pool.</h3>
              <p>
                Try another name or broaden your set, rarity and color filters.
              </p>
              <Link
                href={`/cards?catalog_snapshot_id=${page.catalog_snapshot_id}`}
              >
                Clear filters
              </Link>
            </div>
          ) : (
            <ul className="card-grid">
              {page.items.map((card, index) => (
                <li key={card.oracle_id}>
                  <article className="card-tile">
                    <p className="card-index" aria-hidden="true">
                      {String(index + 1).padStart(2, "0")}{" "}
                      <span>{card.layout.replaceAll("_", " ")}</span>
                    </p>
                    <CardImages
                      name={card.name}
                      printing={card.preview_printing}
                      preview
                    />
                    <h3>
                      <Link href={`/cards/${card.oracle_id}?${detailQuery}`}>
                        {card.name}
                      </Link>
                    </h3>
                    <p className="color-label">{colors(card.color_identity)}</p>
                    <div className="tile-bottom">
                      <span>
                        {card.eligible_printing_count} eligible{" "}
                        {card.eligible_printing_count === 1
                          ? "printing"
                          : "printings"}
                      </span>
                      <span aria-hidden="true">↗</span>
                    </div>
                  </article>
                </li>
              ))}
            </ul>
          )}
          <div className="pagination">
            {page.next_cursor ? (
              <Link className="button" href={`/cards?${next}`}>
                Next page <span aria-hidden="true">→</span>
              </Link>
            ) : (
              page.items.length > 0 && <p>End of these results</p>
            )}
            <CopySearch />
          </div>
        </section>
        <aside className="method-note">
          <strong>Catalog facts, with their limits.</strong>
          <p>
            Tournament evidence is not available for this dataset. Pool
            availability does not establish historical eligibility or
            competitive strength.
          </p>
        </aside>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
