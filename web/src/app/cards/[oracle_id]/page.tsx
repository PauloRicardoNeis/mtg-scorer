import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import {
  colors,
  printingParams,
  queryParams,
  type SearchParams,
} from "@/lib/urls";
import { Problem } from "@/components/problem";
import { redirect } from "next/navigation";

function KnownText({ value }: { value: string | null }) {
  return (
    <span className="rules-text">
      {value === null
        ? "Not supplied by the source"
        : value === ""
          ? "None"
          : value}
    </span>
  );
}

export default async function Card({
  params,
  searchParams,
}: {
  params: Promise<{ oracle_id: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { oracle_id } = await params;
  const query = queryParams(await searchParams);
  try {
    if (!query.has("catalog_snapshot_id")) {
      query.set(
        "catalog_snapshot_id",
        (await api.snapshots()).active_catalog_snapshot_id,
      );
      redirect(`/cards/${encodeURIComponent(oracle_id)}?${query}`);
    }
    const snapshot = query.get("catalog_snapshot_id")!;
    const printingQuery = printingParams(query);
    if (query.has("printing_cursor"))
      printingQuery.set("cursor", query.get("printing_cursor")!);
    const [card, printings] = await Promise.all([
      api.card(oracle_id, snapshot),
      api.printings(oracle_id, printingQuery),
    ]);
    const back = new URLSearchParams(query);
    back.delete("printing_cursor");
    back.delete("cursor");
    const next = new URLSearchParams(query);
    if (printings.next_cursor)
      next.set("printing_cursor", printings.next_cursor);
    return (
      <>
        <div className="breadcrumbs">
          <Link href={`/cards?${back}`}>← Back to search</Link>
          <Link href={`/datasets/${snapshot}`}>Dataset &amp; method</Link>
        </div>
        <section className="detail-intro">
          <p className="eyebrow">
            {card.layout.replaceAll("_", " ")} · {colors(card.color_identity)}
          </p>
          <h1>{card.name}</h1>
          <p>
            Mana value: {card.mana_value === null ? "Unknown" : card.mana_value}
          </p>
        </section>
        <section aria-label="Card faces" className="faces">
          {card.faces.length > 0 ? (
            card.faces.map((face) => (
              <article className="face" key={face.face_index}>
                <p className="eyebrow">Face {face.face_index + 1}</p>
                <h2>{face.name}</h2>
                <p className="mana">
                  Mana cost: <KnownText value={face.mana_cost} />
                </p>
                <p>{face.type_line ?? "Type not supplied"}</p>
                <div className="rules">
                  <KnownText value={face.oracle_text} />
                </div>
              </article>
            ))
          ) : (
            <article className="face">
              <h2>Card text</h2>
              <p className="mana">
                Mana cost: <KnownText value={card.mana_cost} />
              </p>
              <p>{card.type_line ?? "Type not supplied"}</p>
              <div className="rules">
                <KnownText value={card.oracle_text} />
              </div>
            </article>
          )}
        </section>
        <section className="printings" aria-labelledby="printings-heading">
          <h2 id="printings-heading">Eligible printings</h2>
          <p>
            Each printing below satisfies your set, rarity and game filters
            together.
          </p>
          {printings.items.length === 0 ? (
            <div className="state">
              <h3>No eligible printings in this pool.</h3>
              <Link
                href={`/cards/${oracle_id}?catalog_snapshot_id=${snapshot}`}
              >
                Show all printings
              </Link>
            </div>
          ) : (
            <ul className="printing-list">
              {printings.items.map((printing) => (
                <li key={printing.scryfall_id}>
                  <div>
                    <h3>
                      {printing.set_name}{" "}
                      <span className="badge">
                        {printing.set_code.toUpperCase()}
                      </span>
                    </h3>
                    <p>
                      {printing.rarity} · #{printing.collector_number} ·{" "}
                      {printing.language.toUpperCase()}
                    </p>
                    <p>
                      {printing.games.join(" · ")} · Released{" "}
                      {printing.released_on ?? "date unknown"}
                    </p>
                  </div>
                  <a
                    href={printing.source_uri}
                    rel="noreferrer"
                    target="_blank"
                  >
                    Scryfall source{" "}
                    <span className="sr-only">
                      for {printing.set_name} (opens new tab)
                    </span>{" "}
                    ↗
                  </a>
                </li>
              ))}
            </ul>
          )}
          {printings.next_cursor && (
            <Link className="button" href={`/cards/${oracle_id}?${next}`}>
              More printings
            </Link>
          )}
        </section>
        <aside className="method-note">
          <strong>Tournament evidence unavailable</strong>
          <p>
            No tournament dataset is attached. No usage count or competitive
            score can be inferred from these printings.
          </p>
          <Link href={`/datasets/${snapshot}`}>
            Inspect source and methodology
          </Link>
        </aside>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
