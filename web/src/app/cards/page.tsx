import Link from "next/link";
import { redirect } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { queryParams, type SearchParams } from "@/lib/urls";
import { getI18n } from "@/i18n/server";
import { Filters } from "@/components/filters";
import { CopySearch } from "@/components/actions";
import { Problem } from "@/components/problem";
import { CardImages } from "@/components/card-image";
import { Icon } from "@/components/icon";
import { ColorPips, ManaCost } from "@/components/mana";

export default async function Cards({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const query = queryParams(await searchParams);
  const { t, plural, colors, count } = await getI18n();
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
        <section className="intro band">
          <div className="intro-inner band-inner">
            <div className="intro-copy">
              <p className="eyebrow">{t.cards.eyebrow}</p>
              <h1>
                {t.cards.title}
                <br />
                <em>{t.cards.titleEmphasis}</em>
              </h1>
              <p className="lead">{t.cards.lead}</p>
            </div>
            <aside className="sample-note">
              <span className="tag">
                {snapshot.selection.kind === "bulk"
                  ? t.cards.sourceBulk
                  : t.cards.sourceSample}
              </span>
              <dl className="stat-strip">
                <div>
                  <dt>{t.cards.statCards}</dt>
                  <dd>{count(snapshot.card_count)}</dd>
                </div>
                <div>
                  <dt>{t.cards.statPrintings}</dt>
                  <dd>{count(snapshot.printing_count)}</dd>
                </div>
                <div>
                  <dt>{t.cards.statRetrieved}</dt>
                  <dd>{snapshot.retrieved_to.slice(0, 10)}</dd>
                </div>
              </dl>
              <Link
                className="inline-link"
                href={`/datasets/${page.catalog_snapshot_id}`}
              >
                {t.cards.inspectDataset}{" "}
                <Icon name="arrow-up-right" size={14} />
              </Link>
            </aside>
          </div>
        </section>
        <Filters
          key={query.toString()}
          snapshot={snapshot}
          query={query.toString()}
        />
        <section aria-labelledby="results-heading" className="results">
          <div className="results-heading">
            <h2 id="results-heading">{t.cards.resultsHeading}</h2>
            <p role="status">{plural(t.cards.onThisPage, page.items.length)}</p>
          </div>
          {page.items.length === 0 ? (
            <div className="state">
              <h3>{t.cards.emptyTitle}</h3>
              <p>{t.cards.emptyBody}</p>
              <Link
                className="button secondary sm"
                href={`/cards?catalog_snapshot_id=${page.catalog_snapshot_id}`}
              >
                {t.common.clearFilters}
              </Link>
            </div>
          ) : (
            <ul className="card-grid">
              {page.items.map((card, index) => (
                <li key={card.oracle_id}>
                  <article className="card-tile">
                    <p className="card-index" aria-hidden="true">
                      {String(index + 1).padStart(2, "0")}{" "}
                      <span className="tag">
                        {card.layout.replaceAll("_", " ")}
                      </span>
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
                    {(card.mana_cost || card.type_line) && (
                      <p className="tile-type">
                        {card.mana_cost && <ManaCost cost={card.mana_cost} />}
                        {card.type_line && <span>{card.type_line}</span>}
                      </p>
                    )}
                    <p className="color-label">
                      <ColorPips values={card.color_identity} />
                      {colors(card.color_identity)}
                    </p>
                    <div className="tile-bottom">
                      <span>
                        {plural(
                          t.cards.eligiblePrintings,
                          card.eligible_printing_count,
                        )}
                      </span>
                      <Icon name="arrow-up-right" size={14} />
                    </div>
                  </article>
                </li>
              ))}
            </ul>
          )}
          <div className="pagination">
            {page.next_cursor ? (
              <Link className="button secondary" href={`/cards?${next}`}>
                {t.cards.nextPage} <Icon name="arrow-right" size={14} />
              </Link>
            ) : (
              page.items.length > 0 && <p className="end-note">{t.cards.end}</p>
            )}
            <CopySearch />
          </div>
        </section>
        <aside className="method-note">
          <Icon name="info" size={18} />
          <strong>{t.cards.noteTitle}</strong>
          <p>{t.cards.noteBody}</p>
        </aside>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
