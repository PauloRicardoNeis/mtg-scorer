import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { getI18n } from "@/i18n/server";
import { formatLabel } from "@/lib/formats";
import {
  cardDecksHref,
  FROM_CARD,
  queryParams,
  type SearchParams,
} from "@/lib/urls";
import { DeckZone } from "@/components/deck-list";
import { Icon } from "@/components/icon";
import { Problem } from "@/components/problem";

export default async function Deck({
  params,
  searchParams,
}: {
  params: Promise<{ score_run_id: string; position: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { score_run_id, position } = await params;
  const query = queryParams(await searchParams);
  const { t, fill, plural, dateWithYear, dateWindow } = await getI18n();
  const deckQuery = new URLSearchParams();
  if (query.get("catalog_snapshot_id"))
    deckQuery.set("catalog_snapshot_id", query.get("catalog_snapshot_id")!);
  try {
    const deck = await api.deck(score_run_id, position, deckQuery);
    const catalog = deck.catalog_snapshot_id;
    const fromCard = query.get(FROM_CARD);
    const lists = [
      ...(deck.commanders ?? []),
      ...(deck.mainboard ?? []),
      ...(deck.sideboard ?? []),
    ];
    const from = lists.find((card) => card.oracle_id === fromCard) ?? null;
    const title = deck.archetype ?? t.rankingData.unlabelled;
    const event = deck.event.name ?? deck.event.source_event_id;
    const recorded =
      deck.wins !== null && deck.losses !== null && deck.draws !== null;
    return (
      <>
        <div className="breadcrumbs">
          {from ? (
            <Link
              className="button secondary sm back"
              href={cardDecksHref(from.oracle_id, deck.run.score_run_id, query)}
            >
              <Icon name="arrow-left" size={14} />
              {fill(t.deckPage.back, { card: from.name })}
            </Link>
          ) : (
            <Link className="button secondary sm back" href="/cards">
              <Icon name="arrow-left" size={14} />
              {t.card.back}
            </Link>
          )}
          <span className="crumb" aria-hidden="true">
            / {title}
          </span>
        </div>
        <section
          className="detail-intro deck-intro"
          aria-labelledby="deck-name"
        >
          <p className="eyebrow">
            {fill(t.deckPage.eyebrow, {
              format: formatLabel(deck.run.format_name),
              event,
              date: dateWithYear(`${deck.event.occurred_on}T00:00:00Z`),
            })}
          </p>
          <h1 id="deck-name">{title}</h1>
          <p className="deck-result">
            {recorded ? (
              <span title={t.card.deckRecord}>
                {fill(t.card.deckRecordValue, {
                  wins: String(deck.wins),
                  losses: String(deck.losses),
                  draws: String(deck.draws),
                })}
              </span>
            ) : (
              <span className="muted">{t.card.deckNoRecord}</span>
            )}
            {deck.final_rank !== null && (
              <span className="badge">
                {fill(t.card.deckFinish, { rank: deck.final_rank })}
              </span>
            )}
            {deck.made_top_cut && (
              <span className="badge success">{t.rankings.topCut}</span>
            )}
            {deck.event.players !== null && (
              <span className="muted">
                {plural(t.card.deckPlayers, deck.event.players)}
              </span>
            )}
            {deck.event.url && (
              <a href={deck.event.url} rel="noreferrer" target="_blank">
                {t.deckPage.eventResults}{" "}
                <span className="sr-only">{t.card.deckEventOpens}</span>
                <Icon name="external-link" size={14} />
              </a>
            )}
          </p>
        </section>
        {deck.mainboard === null ? (
          <div className="state deck-unlisted">
            <h2>{t.deckPage.noList}</h2>
          </div>
        ) : (
          <div className="deck-zones">
            {deck.commanders && deck.commanders.length > 0 && (
              <DeckZone
                title={plural(t.deckPage.commanders, deck.commanders.length)}
                cards={deck.commanders}
                catalog={catalog}
                fromCard={fromCard}
              />
            )}
            <DeckZone
              title={t.deckPage.mainDeck}
              cards={deck.mainboard}
              catalog={catalog}
              fromCard={fromCard}
              grouped
            />
            {deck.sideboard && deck.sideboard.length > 0 ? (
              <DeckZone
                title={t.deckPage.sideboard}
                cards={deck.sideboard}
                catalog={catalog}
                fromCard={fromCard}
              />
            ) : (
              deck.sideboard === null &&
              !deck.commanders?.length && (
                <p className="muted deck-no-sideboard">
                  {t.deckPage.noSideboard}
                </p>
              )
            )}
          </div>
        )}
        <p className="deck-source muted">
          {fill(t.card.decksWindow, {
            window: dateWindow(
              deck.run.window_starts_on,
              deck.run.window_ends_before,
            ),
          })}
          {" · "}
          {deck.run.attribution}
        </p>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
