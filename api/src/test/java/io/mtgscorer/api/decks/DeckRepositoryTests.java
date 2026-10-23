package io.mtgscorer.api.decks;

import static io.mtgscorer.api.decks.DeckModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.decks.DeckRepository.DeckHeader;
import io.mtgscorer.api.decks.DeckRepository.ListedCard;
import java.sql.Array;
import java.sql.ResultSet;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;

/** Binding, SQL shape and row mapping; the SQL runs against PostgreSQL in the HTTP tests. */
@ExtendWith(MockitoExtension.class)
class DeckRepositoryTests {
  private static final String RUN = "scores-" + "a".repeat(64);
  private static final UUID BOLT = UUID.fromString("4457ed35-7c10-48c8-9776-456485fdf070");

  @Mock private NamedParameterJdbcTemplate jdbc;
  @Mock private ResultSet row;
  @Captor private ArgumentCaptor<String> sql;
  @Captor private ArgumentCaptor<Map<String, Object>> args;
  @Captor private ArgumentCaptor<RowMapper<DeckFormat>> formatRows;
  @Captor private ArgumentCaptor<RowMapper<DeckRun>> runRows;
  @Captor private ArgumentCaptor<RowMapper<CardDeck>> deckRows;
  @Captor private ArgumentCaptor<RowMapper<DeckHeader>> headerRows;
  @Captor private ArgumentCaptor<RowMapper<ListedCard>> cardRows;
  @Mock private Array commanders;

  private DeckRepository repository;

  @BeforeEach
  void setUp() {
    repository = new DeckRepository(jdbc);
  }

  @Test
  void formatsAreActiveRunsListingTheCardsDecksMostFirst() throws Exception {
    repository.formats(BOLT);
    verify(jdbc).query(sql.capture(), eq(Map.of("card", BOLT)), formatRows.capture());
    assertThat(sql.getValue())
        .contains("FROM scores.active_score_run a")
        .contains("WHERE c.deck_positions IS NOT NULL")
        .contains("ORDER BY c.deck_count DESC");
    when(row.getString("format_name")).thenReturn("Modern");
    when(row.getString("source")).thenReturn("topdeck");
    when(row.getString("score_run_id")).thenReturn(RUN);
    when(row.getInt("deck_count")).thenReturn(412);

    assertThat(formatRows.getValue().mapRow(row, 0))
        .isEqualTo(new DeckFormat("Modern", "topdeck", RUN, 412));
  }

  @Test
  void aRunIsReadFromThePublishedRuns() throws Exception {
    when(jdbc.query(sql.capture(), eq(Map.of("run", RUN)), runRows.capture()))
        .thenReturn(List.of());

    assertThat(repository.run(RUN)).isEmpty();
    assertThat(sql.getValue()).contains("FROM scores.published_score_run WHERE");
    when(row.getString("score_run_id")).thenReturn(RUN);
    when(row.getString("source")).thenReturn("topdeck");
    when(row.getString("format_name")).thenReturn("Modern");
    when(row.getObject("window_starts_on", LocalDate.class)).thenReturn(LocalDate.of(2024, 1, 1));
    when(row.getObject("window_ends_before", LocalDate.class))
        .thenReturn(LocalDate.of(2026, 10, 1));
    when(row.getString("attribution")).thenReturn("TopDeck");

    assertThat(runRows.getValue().mapRow(row, 0))
        .isEqualTo(
            new DeckRun(
                RUN,
                "topdeck",
                "Modern",
                LocalDate.of(2024, 1, 1),
                LocalDate.of(2026, 10, 1),
                "TopDeck"));
  }

  @Test
  void aCardWithoutDeckListsInTheRunCountsNone() {
    when(jdbc.queryForList(sql.capture(), args.capture(), eq(Long.class)))
        .thenReturn(List.of(412L))
        .thenReturn(List.of());

    assertThat(repository.count(RUN, BOLT)).isEqualTo(412);
    assertThat(repository.count(RUN, BOLT)).isZero();
    assertThat(args.getValue()).containsEntry("run", RUN).containsEntry("card", BOLT);
    assertThat(sql.getValue()).contains("deck_positions IS NOT NULL");
  }

  @Test
  void aPageIsARangeOfTheCardsDecksWithTheCopiesEachPlays() throws Exception {
    repository.page(RUN, BOLT, 40, 20);
    verify(jdbc).query(sql.capture(), args.capture(), deckRows.capture());
    assertThat(args.getValue())
        .containsEntry("offset", 40)
        .containsEntry("last", 60L)
        .containsEntry("card", BOLT);
    assertThat(sql.getValue())
        .contains("unnest(c.deck_positions,c.deck_copies)")
        .contains("WITH ORDINALITY k(position,copies,n)")
        .contains("k.n>:offset AND k.n<=:last")
        .endsWith("ORDER BY k.n\n");
    when(row.getInt("position")).thenReturn(41);
    when(row.getString("source_deck_id")).thenReturn("synthetic-open#2");
    when(row.getString("source_event_id")).thenReturn("synthetic-open");
    when(row.getString("event_name")).thenReturn("Synthetic open");
    when(row.getString("event_url")).thenReturn("https://topdeck.gg/event/synthetic-open");
    when(row.getObject("occurred_on", LocalDate.class)).thenReturn(LocalDate.of(2026, 4, 11));
    when(row.getObject("players", Integer.class)).thenReturn(4);
    when(row.getString("archetype_label")).thenReturn("Izzet Tempo");
    when(row.getInt("copies")).thenReturn(4);
    when(row.getObject("final_rank", Integer.class)).thenReturn(null);
    when(row.getObject("made_top_cut", Boolean.class)).thenReturn(true);
    when(row.getObject("record_wins", Integer.class)).thenReturn(2);
    when(row.getObject("record_losses", Integer.class)).thenReturn(1);
    when(row.getObject("record_draws", Integer.class)).thenReturn(0);

    assertThat(deckRows.getValue().mapRow(row, 0))
        .isEqualTo(
            new CardDeck(
                41,
                "synthetic-open#2",
                new DeckEvent(
                    "synthetic-open",
                    "Synthetic open",
                    "https://topdeck.gg/event/synthetic-open",
                    LocalDate.of(2026, 4, 11),
                    4),
                "Izzet Tempo",
                4,
                null,
                true,
                2,
                1,
                0));
  }

  private void stubEvent() throws Exception {
    when(row.getString("source_event_id")).thenReturn("edh-open");
    when(row.getString("event_name")).thenReturn("EDH Open");
    when(row.getString("event_url")).thenReturn(null);
    when(row.getObject("occurred_on", LocalDate.class)).thenReturn(LocalDate.of(2026, 9, 1));
    when(row.getObject("players", Integer.class)).thenReturn(null);
  }

  @Test
  void aDeckIsReadWithItsCommandersOrWithoutAList() throws Exception {
    when(jdbc.query(sql.capture(), args.capture(), headerRows.capture())).thenReturn(List.of());

    assertThat(repository.deck(RUN, 7)).isEmpty();
    assertThat(args.getValue()).containsEntry("run", RUN).containsEntry("position", 7);
    assertThat(sql.getValue())
        .contains("d.commanders,d.sideboard IS NOT NULL sided")
        .contains("WHERE d.score_run_id=:run AND d.position=:position");
    stubEvent();
    when(row.getInt("position")).thenReturn(7);
    when(row.getString("source_deck_id")).thenReturn("edh-open#8");
    when(row.getString("archetype_label")).thenReturn("Kinnan, Bonder Prodigy");
    when(row.getObject("final_rank", Integer.class)).thenReturn(8);
    when(row.getObject("made_top_cut", Boolean.class)).thenReturn(null);
    when(row.getBoolean("sided")).thenReturn(false);
    when(row.getArray("commanders")).thenReturn(commanders).thenReturn(null);
    when(commanders.getArray()).thenReturn(new UUID[] {BOLT});

    DeckHeader listed = headerRows.getValue().mapRow(row, 0);
    assertThat(listed.commanders()).containsExactly(BOLT);
    assertThat(listed.event().name()).isEqualTo("EDH Open");
    assertThat(List.of(listed.position(), listed.final_rank())).containsExactly(7, 8);
    assertThat(headerRows.getValue().mapRow(row, 1).commanders()).isNull();
  }

  @Test
  void aDecksCardsComeWithTheCatalogsDetailsMainDeckFirst() throws Exception {
    repository.cards(RUN, 7, "catalog-a");
    verify(jdbc).query(sql.capture(), args.capture(), cardRows.capture());
    assertThat(args.getValue())
        .containsEntry("snapshot", "catalog-a")
        .containsEntry("position", 7)
        .containsEntry("run", RUN);
    assertThat(sql.getValue())
        .contains("FROM unnest(d.mainboard,d.mainboard_copies) m(oracle_id,copies)")
        .contains("unnest(d.sideboard,d.sideboard_names,d.sideboard_copies)")
        .contains("LEFT JOIN LATERAL (SELECT coalesce(c.mana_cost")
        .contains("ORDER BY k.side,coalesce(c.name,k.name),k.oracle_id");
    when(row.getBoolean("side")).thenReturn(true);
    when(row.getObject("oracle_id", UUID.class)).thenReturn(BOLT);
    when(row.getString("name")).thenReturn("Lightning Bolt");
    when(row.getInt("copies")).thenReturn(2);
    when(row.getString("mana_cost")).thenReturn("{R}");
    when(row.getString("type_line")).thenReturn("Instant");
    when(row.getObject("mana_value", Double.class)).thenReturn(1.0);
    when(row.getBoolean("in_catalog")).thenReturn(true);

    assertThat(cardRows.getValue().mapRow(row, 0))
        .isEqualTo(
            new ListedCard(
                true, new DeckCard(BOLT, "Lightning Bolt", 2, "{R}", "Instant", 1.0, true)));
  }
}
