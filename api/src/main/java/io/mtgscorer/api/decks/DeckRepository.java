package io.mtgscorer.api.decks;

import static io.mtgscorer.api.decks.DeckModels.*;

import io.mtgscorer.api.catalog.CatalogSql;
import java.sql.Array;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

/**
 * Bound queries over published decks. A card stores its decks as positions into its run's decks,
 * newest event first, so a page is a range of that list joined to the decks it names.
 */
@Repository
class DeckRepository {
  private final NamedParameterJdbcTemplate jdbc;

  DeckRepository(NamedParameterJdbcTemplate jdbc) {
    this.jdbc = jdbc;
  }

  /** Active runs listing the card's decks; runs from before deck lists list none. */
  List<DeckFormat> formats(UUID card) {
    return jdbc.query(
        """
        SELECT a.format_name,a.source,a.score_run_id,c.deck_count
        FROM scores.active_score_run a
        JOIN scores.published_score_run_card c
          ON c.score_run_id=a.score_run_id AND c.oracle_id=:card
        WHERE c.deck_positions IS NOT NULL
        ORDER BY c.deck_count DESC,a.format_name,a.source
        """,
        Map.of("card", card),
        (row, index) ->
            new DeckFormat(
                row.getString("format_name"),
                row.getString("source"),
                row.getString("score_run_id"),
                row.getInt("deck_count")));
  }

  Optional<DeckRun> run(String scoreRun) {
    return jdbc
        .query(
            """
            SELECT score_run_id,source,format_name,window_starts_on,window_ends_before,attribution
            FROM scores.published_score_run WHERE score_run_id=:run
            """,
            Map.of("run", scoreRun),
            (row, index) ->
                new DeckRun(
                    row.getString("score_run_id"),
                    row.getString("source"),
                    row.getString("format_name"),
                    row.getObject("window_starts_on", LocalDate.class),
                    row.getObject("window_ends_before", LocalDate.class),
                    row.getString("attribution")))
        .stream()
        .findFirst();
  }

  /** The card's decks in the run; 0 when the run lists none for it. */
  long count(String scoreRun, UUID card) {
    return jdbc
        .queryForList(
            "SELECT deck_count FROM scores.published_score_run_card"
                + " WHERE score_run_id=:run AND oracle_id=:card AND deck_positions IS NOT NULL",
            Map.of("run", scoreRun, "card", card),
            Long.class)
        .stream()
        .findFirst()
        .orElse(0L);
  }

  /** One range of the card's decks, in the run's order, with the copies each plays. */
  List<CardDeck> page(String scoreRun, UUID card, int offset, int limit) {
    return jdbc.query(
        """
        SELECT d.position,d.source_deck_id,d.source_event_id,d.event_name,d.event_url,
          d.occurred_on,d.players,d.archetype_label,k.copies,d.final_rank,d.made_top_cut,
          d.record_wins,d.record_losses,d.record_draws
        FROM scores.published_score_run_card c
        CROSS JOIN LATERAL unnest(c.deck_positions,c.deck_copies)
          WITH ORDINALITY k(position,copies,n)
        JOIN scores.published_score_run_deck d
          ON d.score_run_id=c.score_run_id AND d.position=k.position
        WHERE c.score_run_id=:run AND c.oracle_id=:card AND k.n>:offset AND k.n<=:last
        ORDER BY k.n
        """,
        Map.of("run", scoreRun, "card", card, "offset", offset, "last", (long) offset + limit),
        (row, index) -> deck(row));
  }

  /**
   * A deck without its list: {@code commanders} is null when the deck carries no list, and {@code
   * sided} says whether its source reported the whole sideboard.
   */
  record DeckHeader(
      int position,
      String source_deck_id,
      DeckEvent event,
      String archetype,
      Integer final_rank,
      Boolean made_top_cut,
      Integer wins,
      Integer losses,
      Integer draws,
      List<UUID> commanders,
      boolean sided) {}

  /** One card of a deck's list, in its main deck or sideboard. */
  record ListedCard(boolean sideboard, DeckCard card) {}

  /** One deck of a published run; empty when the run has no deck at that position. */
  Optional<DeckHeader> deck(String scoreRun, int position) {
    return jdbc
        .query(
            """
            SELECT d.position,d.source_deck_id,d.source_event_id,d.event_name,d.event_url,
              d.occurred_on,d.players,d.archetype_label,d.final_rank,d.made_top_cut,
              d.record_wins,d.record_losses,d.record_draws,d.commanders,d.sideboard IS NOT NULL sided
            FROM scores.published_score_run_deck d WHERE d.score_run_id=:run AND d.position=:position
            """,
            Map.of("run", scoreRun, "position", position),
            (row, index) -> {
              Array commanders = row.getArray("commanders");
              return new DeckHeader(
                  row.getInt("position"),
                  row.getString("source_deck_id"),
                  event(row),
                  row.getString("archetype_label"),
                  row.getObject("final_rank", Integer.class),
                  row.getObject("made_top_cut", Boolean.class),
                  row.getObject("record_wins", Integer.class),
                  row.getObject("record_losses", Integer.class),
                  row.getObject("record_draws", Integer.class),
                  commanders == null ? null : List.of((UUID[]) commanders.getArray()),
                  row.getBoolean("sided"));
            })
        .stream()
        .findFirst();
  }

  /**
   * A deck's main deck and sideboard by name, with the details the catalog shown has. A main deck
   * card is named as the run names it when the catalog does not have it, a sideboard card as the
   * source did.
   */
  List<ListedCard> cards(String scoreRun, int position, String catalogSnapshot) {
    return jdbc.query(
        """
        SELECT k.side,k.oracle_id,coalesce(c.name,k.name) name,k.copies,shown.mana_cost,
          shown.type_line,c.mana_value,c.oracle_id IS NOT NULL in_catalog
        FROM scores.published_score_run_deck d
        CROSS JOIN LATERAL (
          SELECT false side,m.oracle_id,sc.name,m.copies
          FROM unnest(d.mainboard,d.mainboard_copies) m(oracle_id,copies)
          JOIN scores.published_score_run_card sc
            ON sc.score_run_id=d.score_run_id AND sc.oracle_id=m.oracle_id
          UNION ALL
          SELECT true,s.oracle_id,s.name,s.copies
          FROM unnest(d.sideboard,d.sideboard_names,d.sideboard_copies) s(oracle_id,name,copies)
        ) k
        LEFT JOIN catalog.published_catalog_card c
          ON c.catalog_snapshot_id=:snapshot AND c.oracle_id=k.oracle_id
        """
            + " LEFT JOIN LATERAL "
            + CatalogSql.SHOWN
            + " shown ON true WHERE d.score_run_id=:run AND d.position=:position"
            + " ORDER BY k.side,coalesce(c.name,k.name),k.oracle_id",
        Map.of("run", scoreRun, "position", position, "snapshot", catalogSnapshot),
        (row, index) ->
            new ListedCard(
                row.getBoolean("side"),
                new DeckCard(
                    row.getObject("oracle_id", UUID.class),
                    row.getString("name"),
                    row.getInt("copies"),
                    row.getString("mana_cost"),
                    row.getString("type_line"),
                    row.getObject("mana_value", Double.class),
                    row.getBoolean("in_catalog"))));
  }

  private static DeckEvent event(ResultSet row) throws SQLException {
    return new DeckEvent(
        row.getString("source_event_id"),
        row.getString("event_name"),
        row.getString("event_url"),
        row.getObject("occurred_on", LocalDate.class),
        row.getObject("players", Integer.class));
  }

  private static CardDeck deck(ResultSet row) throws SQLException {
    return new CardDeck(
        row.getInt("position"),
        row.getString("source_deck_id"),
        event(row),
        row.getString("archetype_label"),
        row.getInt("copies"),
        row.getObject("final_rank", Integer.class),
        row.getObject("made_top_cut", Boolean.class),
        row.getObject("record_wins", Integer.class),
        row.getObject("record_losses", Integer.class),
        row.getObject("record_draws", Integer.class));
  }
}
