import Link from "next/link";
import { useI18n } from "#i18n";
import type { DeckCard } from "@/lib/api";
import { copies, groupCards } from "@/lib/deck-groups";
import { ManaCost } from "./mana";

function Line({
  card,
  catalog,
  fromCard,
}: {
  card: DeckCard;
  catalog: string;
  fromCard: string | null;
}) {
  const { t } = useI18n();
  const from = card.oracle_id === fromCard;
  const query = new URLSearchParams({ catalog_snapshot_id: catalog });
  return (
    <li className={from ? "deck-line from-card" : "deck-line"}>
      <span className="deck-line-copies">{card.copies}</span>
      <span className="deck-line-name">
        {card.in_catalog ? (
          <Link href={`/cards/${encodeURIComponent(card.oracle_id)}?${query}`}>
            {card.name}
          </Link>
        ) : (
          card.name
        )}
        {from && <span className="sr-only"> ({t.deckPage.fromCard})</span>}
      </span>
      {card.mana_cost && <ManaCost cost={card.mana_cost} />}
    </li>
  );
}

/**
 * One zone of a deck, headed by its name and card count: the main deck reads in type groups,
 * the commanders and sideboard as one list. Cards the catalog has link to their pages.
 */
export function DeckZone({
  title,
  cards,
  catalog,
  fromCard = null,
  grouped = false,
}: {
  title: string;
  cards: DeckCard[];
  catalog: string;
  fromCard?: string | null;
  grouped?: boolean;
}) {
  const { t, plural } = useI18n();
  const lines = (members: DeckCard[]) => (
    <ul className="deck-lines">
      {members.map((card) => (
        <Line
          key={card.oracle_id}
          card={card}
          catalog={catalog}
          fromCard={fromCard}
        />
      ))}
    </ul>
  );
  return (
    <section
      className={grouped ? "deck-zone grouped" : "deck-zone"}
      aria-label={title}
    >
      <h2>
        {title}{" "}
        <span className="deck-zone-count">
          {plural(t.deckPage.cardCount, copies(cards))}
        </span>
      </h2>
      {grouped ? (
        <div className="deck-groups">
          {groupCards(cards).map(({ group, cards: members, count }) => (
            <div className="deck-group" key={group}>
              <h3>
                {t.deckPage.groups[group]}{" "}
                <span className="deck-zone-count">{count}</span>
              </h3>
              {lines(members)}
            </div>
          ))}
        </div>
      ) : (
        lines(cards)
      )}
    </section>
  );
}
