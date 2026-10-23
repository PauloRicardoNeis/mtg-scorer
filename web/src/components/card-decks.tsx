import Link from "next/link";
import { useI18n } from "#i18n";
import type { CardDeck, CardDeckPage } from "@/lib/api";
import { formatLabel } from "@/lib/formats";
import { DECK_OFFSET, DECK_RUN, deckPageHref } from "@/lib/urls";
import { Icon } from "./icon";
import { UnderlineTabs } from "./primitives";

/** A link back to this card's page showing one run's decks from an offset, at the list. */
function deckHref(
  path: string,
  query: URLSearchParams,
  run: string,
  offset = 0,
): string {
  const next = new URLSearchParams(query);
  next.set(DECK_RUN, run);
  if (offset > 0) next.set(DECK_OFFSET, String(offset));
  else next.delete(DECK_OFFSET);
  return `${path}?${next}#decks`;
}

function Result({ deck }: { deck: CardDeck }) {
  const { t, fill } = useI18n();
  return (
    <p className="deck-result">
      {deck.wins !== null && deck.losses !== null && deck.draws !== null ? (
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
    </p>
  );
}

function Deck({ deck, href }: { deck: CardDeck; href: string }) {
  const { t, fill, plural, dateWithYear } = useI18n();
  const name = deck.event.name ?? deck.event.source_event_id;
  const archetype = deck.archetype ?? t.rankingData.unlabelled;
  return (
    <li>
      <div className="deck-event">
        <h3>
          {deck.event.url ? (
            <a href={deck.event.url} rel="noreferrer" target="_blank">
              {name} <span className="sr-only">{t.card.deckEventOpens}</span>
              <Icon name="external-link" size={14} />
            </a>
          ) : (
            name
          )}
        </h3>
        <p className="printing-meta">
          {dateWithYear(`${deck.event.occurred_on}T00:00:00Z`)}
          {deck.event.players !== null &&
            ` · ${plural(t.card.deckPlayers, deck.event.players)}`}
        </p>
      </div>
      <p className="deck-archetype">
        <Link
          href={href}
          aria-label={fill(t.card.deckOpen, { archetype, event: name })}
        >
          {archetype}
        </Link>
        <span
          className="deck-copies"
          title={plural(t.card.deckCopiesLabel, deck.copies)}
        >
          <span aria-hidden="true">
            {fill(t.card.deckCopies, { count: deck.copies })}
          </span>
          <span className="sr-only">
            {plural(t.card.deckCopiesLabel, deck.copies)}
          </span>
        </span>
      </p>
      <Result deck={deck} />
    </li>
  );
}

/**
 * The tournament decks behind a card's counts: a tab per format whose active run lists
 * them, then one run's decks, newest event first, a page at a time.
 */
export function CardDecks({
  page,
  path,
  query,
}: {
  page: CardDeckPage;
  path: string;
  query: URLSearchParams;
}) {
  const { t, fill, plural, count, dateWindow } = useI18n();
  const { run, items, total, offset, limit } = page;
  return (
    <section className="card-decks" id="decks" aria-labelledby="decks-heading">
      <h2 id="decks-heading">{t.card.decksHeading}</h2>
      <p>{t.card.decksLead}</p>
      {page.formats.length > 0 && (
        <UnderlineTabs
          label={t.card.decksFormats}
          items={page.formats.map((format) => ({
            href: deckHref(path, query, format.score_run_id),
            label: formatLabel(format.format_name),
            count: count(format.deck_count),
            current: format.score_run_id === run?.score_run_id,
          }))}
        />
      )}
      {run === null || items.length === 0 ? (
        <div className="state">
          <h3>{run === null ? t.card.decksNone : t.card.decksNoneHere}</h3>
          <p>{t.card.decksNoneBody}</p>
        </div>
      ) : (
        <>
          <p className="deck-summary">
            {plural(t.card.decksRange, total, {
              first: count(offset + 1),
              last: count(offset + items.length),
            })}
            {" · "}
            {fill(t.card.decksWindow, {
              window: dateWindow(run.window_starts_on, run.window_ends_before),
            })}
            {" · "}
            {run.attribution}
          </p>
          <ol className="printing-list deck-list">
            {items.map((deck) => (
              <Deck
                key={deck.position}
                deck={deck}
                href={deckPageHref(
                  run.score_run_id,
                  deck.position,
                  page.oracle_id,
                  query,
                )}
              />
            ))}
          </ol>
        </>
      )}
      {run !== null && (offset > 0 || offset + limit < total) && (
        <nav className="deck-pages" aria-label={t.card.decksPages}>
          {offset > 0 && (
            <Link
              className="button secondary sm"
              href={deckHref(
                path,
                query,
                run.score_run_id,
                Math.max(0, offset - limit),
              )}
            >
              <Icon name="arrow-left" size={14} /> {t.card.previousDecks}
            </Link>
          )}
          {offset + limit < total && (
            <Link
              className="button secondary sm"
              href={deckHref(path, query, run.score_run_id, offset + limit)}
            >
              {t.card.moreDecks} <Icon name="arrow-right" size={14} />
            </Link>
          )}
        </nav>
      )}
    </section>
  );
}
