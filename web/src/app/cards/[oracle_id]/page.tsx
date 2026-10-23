import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "#i18n";
import { getI18n } from "@/i18n/server";
import {
  DECK_OFFSET,
  DECK_RUN,
  deckParams,
  edition,
  printingParams,
  queryParams,
  type SearchParams,
} from "@/lib/urls";
import { Problem } from "@/components/problem";
import { CardDecks } from "@/components/card-decks";
import { CardImage, CardImages } from "@/components/card-image";
import { Icon } from "@/components/icon";
import { ColorPips, ManaCost, Rarity, SymbolText } from "@/components/mana";
import { redirect } from "next/navigation";

function ManaLine({ value }: { value: string | null }) {
  const { t } = useI18n();
  return (
    <p className="mana">
      <span className="mana-label">{t.card.manaCost}</span>{" "}
      {value ? (
        <ManaCost cost={value} size="lg" />
      ) : (
        <KnownText value={value} />
      )}
    </p>
  );
}

function KnownText({ value }: { value: string | null }) {
  const { t } = useI18n();
  return (
    <span className="rules-text">
      {value === null ? (
        t.card.notSupplied
      ) : value === "" ? (
        t.card.none
      ) : (
        <SymbolText text={value} />
      )}
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
  const { t, fill, colors, count } = await getI18n();
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
    // The hero features the first eligible printing, even on later printing pages.
    const firstQuery = new URLSearchParams(printingQuery);
    firstQuery.set("limit", "1");
    if (query.has("printing_cursor"))
      printingQuery.set("cursor", query.get("printing_cursor")!);
    const [card, printings, first, decks] = await Promise.all([
      api.card(oracle_id, snapshot),
      api.printings(oracle_id, printingQuery),
      query.has("printing_cursor")
        ? api.printings(oracle_id, firstQuery)
        : null,
      // Decks are optional: without them the card page still shows the catalog.
      api.decks(oracle_id, deckParams(query)).catch(() => null),
    ]);
    const featured = (first ?? printings).items[0] ?? null;
    const manaCost = card.mana_cost ?? card.faces[0]?.mana_cost ?? null;
    const typeLine =
      card.type_line ??
      (card.faces
        .map((face) => face.type_line)
        .filter(Boolean)
        .join(" // ") ||
        null);
    const back = new URLSearchParams(query);
    back.delete("printing_cursor");
    back.delete("cursor");
    back.delete(DECK_RUN);
    back.delete(DECK_OFFSET);
    const next = new URLSearchParams(query);
    if (printings.next_cursor)
      next.set("printing_cursor", printings.next_cursor);
    return (
      <>
        <div className="breadcrumbs">
          <Link className="button secondary sm back" href={`/cards?${back}`}>
            <Icon name="arrow-left" size={14} />
            {t.card.back}
          </Link>
          <span className="crumb" aria-hidden="true">
            / {card.name}
          </span>
          <Link className="button ghost sm" href={`/datasets/${snapshot}`}>
            <Icon name="database" size={14} />
            {t.nav.methodology}
          </Link>
        </div>
        <section className="detail-hero" aria-labelledby="card-name">
          <div className="detail-art">
            <CardImage
              featured
              eager
              src={featured?.images[0]?.source_uri ?? null}
              alt={
                featured
                  ? fill(t.images.alt, {
                      name: card.name,
                      edition: edition(featured),
                    })
                  : fill(t.card.noPrintingAlt, { name: card.name })
              }
            />
          </div>
          <div className="detail-copy">
            <p className="eyebrow">
              <ColorPips values={card.color_identity} />
              {card.layout.replaceAll("_", " ")} · {colors(card.color_identity)}
            </p>
            <h1 id="card-name">{card.name}</h1>
            {(manaCost || typeLine) && (
              <p className="detail-type">
                {manaCost && <ManaCost cost={manaCost} size="lg" />}
                {typeLine && <span className="type-line">{typeLine}</span>}
              </p>
            )}
            <dl className="stat-strip">
              <div>
                <dt>{t.card.manaValue}</dt>
                <dd>
                  {card.mana_value === null
                    ? t.common.unknown
                    : count(card.mana_value)}
                </dd>
              </div>
            </dl>
          </div>
        </section>
        <section aria-label={t.card.faces} className="faces">
          {card.faces.length > 0 ? (
            card.faces.map((face) => (
              <article className="face" key={face.face_index}>
                <p className="eyebrow">
                  {fill(t.images.face, { number: face.face_index + 1 })}
                </p>
                <h2>{face.name}</h2>
                <ManaLine value={face.mana_cost} />
                <p className="type-line">
                  {face.type_line ?? t.card.typeNotSupplied}
                </p>
                <div className="rules">
                  <KnownText value={face.oracle_text} />
                </div>
              </article>
            ))
          ) : (
            <article className="face">
              <h2>{t.card.cardText}</h2>
              <ManaLine value={card.mana_cost} />
              <p className="type-line">
                {card.type_line ?? t.card.typeNotSupplied}
              </p>
              <div className="rules">
                <KnownText value={card.oracle_text} />
              </div>
            </article>
          )}
        </section>
        {decks && (
          <CardDecks
            page={decks}
            path={`/cards/${encodeURIComponent(oracle_id)}`}
            query={query}
          />
        )}
        <section className="printings" aria-labelledby="printings-heading">
          <h2 id="printings-heading">{t.card.printingsHeading}</h2>
          <p>{t.card.printingsLead}</p>
          {printings.items.length === 0 ? (
            <div className="state">
              <h3>{t.card.noPrintings}</h3>
              <Link
                className="button secondary sm"
                href={`/cards/${oracle_id}?catalog_snapshot_id=${snapshot}`}
              >
                {t.card.showAllPrintings}
              </Link>
            </div>
          ) : (
            <ul className="printing-list">
              {printings.items.map((printing) => (
                <li key={printing.scryfall_id}>
                  <CardImages name={card.name} printing={printing} />
                  <div className="printing-info">
                    <h3>
                      {printing.set_name}{" "}
                      <span className="badge">
                        {printing.set_code.toUpperCase()}
                      </span>
                    </h3>
                    <p className="printing-meta">
                      <Rarity rarity={printing.rarity} /> · #
                      {printing.collector_number} ·{" "}
                      {printing.language.toUpperCase()}
                    </p>
                    <p className="printing-meta">
                      {printing.games
                        .map(
                          (game) =>
                            t.games[game as keyof typeof t.games] ?? game,
                        )
                        .join(" · ")}{" "}
                      ·{" "}
                      {fill(t.card.released, {
                        date: printing.released_on ?? t.card.dateUnknown,
                      })}
                    </p>
                  </div>
                  <a
                    className="button secondary sm"
                    href={printing.source_uri}
                    rel="noreferrer"
                    target="_blank"
                  >
                    {t.card.source}{" "}
                    <span className="sr-only">
                      {fill(t.card.sourceFor, { set: printing.set_name })}
                    </span>
                    <Icon name="external-link" size={14} />
                  </a>
                </li>
              ))}
            </ul>
          )}
          {printings.next_cursor && (
            <Link
              className="button secondary more"
              href={`/cards/${oracle_id}?${next}`}
            >
              {t.card.morePrintings} <Icon name="arrow-right" size={14} />
            </Link>
          )}
        </section>
        {decks === null && (
          <aside className="method-note">
            <Icon name="info" size={18} />
            <strong>{t.card.noteTitle}</strong>
            <p>{t.card.noteBody}</p>
            <Link href={`/datasets/${snapshot}`}>
              {t.card.inspectMethodology}
            </Link>
          </aside>
        )}
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
