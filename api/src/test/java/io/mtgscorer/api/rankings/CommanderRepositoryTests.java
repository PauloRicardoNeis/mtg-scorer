package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.sql.ResultSet;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.HashMap;
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
import tools.jackson.databind.json.JsonMapper;

/** Binding, SQL shape and row mapping; the SQL runs against PostgreSQL in the HTTP tests. */
@ExtendWith(MockitoExtension.class)
class CommanderRepositoryTests {
  private static final String RUN = "scores-" + "a".repeat(64);
  private static final String PREVIOUS = "scores-" + "b".repeat(64);
  private static final UUID KINNAN = UUID.fromString("6a1c4d8e-7f5b-4a0e-9c1d-2b3e4f5a6b7c");

  @Mock private NamedParameterJdbcTemplate jdbc;
  @Mock private ResultSet row;
  @Captor private ArgumentCaptor<String> sql;
  @Captor private ArgumentCaptor<Map<String, Object>> args;
  @Captor private ArgumentCaptor<RowMapper<RankedCommander>> commanderRows;

  private CommanderRepository repository;

  @BeforeEach
  void setUp() {
    repository = new CommanderRepository(jdbc, JsonMapper.builder().build());
  }

  private static CommanderQuery query(String... pairs) {
    Map<String, List<String>> input = new HashMap<>();
    for (int index = 0; index < pairs.length; index += 2)
      input.computeIfAbsent(pairs[index], key -> new ArrayList<>()).add(pairs[index + 1]);
    return CommanderQuery.parse(input);
  }

  @Test
  void onlyArchetypesThatCommandersNameAreRankedByTheirDecks() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(1599L);

    assertThat(repository.count(RUN, null, query())).isEqualTo(1599);
    assertThat(args.getValue()).containsOnlyKeys("run", "previous").containsEntry("run", RUN);
    assertThat(sql.getValue())
        .startsWith("SELECT count(*) FROM")
        .contains("rank() OVER (ORDER BY a.deck_count DESC) ranking")
        .contains("cardinality(a.commanders)>0")
        .contains("prev ON prev.label=r.label")
        .doesNotContain(" WHERE (");
  }

  @Test
  void searchMatchesTheLabelOrAnyCommandersAliasAndColorsTheCombinedIdentity() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(1L);

    repository.count(RUN, null, query("q", "Kinnan", "color", "G", "color", "C"));

    assertThat(args.getValue()).contains(Map.entry("q", "kinnan"), Map.entry("anyColors", "G"));
    assertThat(sql.getValue())
        .contains("strpos(lower(r.label),:q)>0")
        .contains("a.oracle_id=ANY(r.commanders) AND strpos(a.alias_key,:q)>0")
        .contains("(idc.colors && string_to_array(:anyColors,',') OR idc.colors='{}')");
  }

  @Test
  void aMinimumKeepsCommandersWithEnoughDecksOnly() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(40L);

    repository.count(RUN, null, query("min_decks", "50"));

    assertThat(args.getValue()).containsEntry("minDecks", 50);
    // Ranks are taken before the filter, so a kept commander keeps its place.
    assertThat(sql.getValue())
        .contains("rank() OVER (ORDER BY a.deck_count DESC)")
        .contains("WHERE r.deck_count>=:minDecks");
  }

  @Test
  void sortsOrderByStoredValuesWithTheLabelBreakingTies() {
    assertThat(CommanderRepository.orderBy(query()))
        .isEqualTo("r.deck_count DESC NULLS LAST,r.label");
    assertThat(CommanderRepository.orderBy(query("sort", "win_rate", "order", "asc")))
        .isEqualTo("r.win_rate_delta ASC NULLS LAST,r.label");
    assertThat(CommanderRepository.orderBy(query("sort", "movement")))
        .isEqualTo("prev.ranking-r.ranking DESC NULLS LAST,r.label");
    assertThat(CommanderRepository.orderBy(query("sort", "name"))).isEqualTo("r.label ASC");
  }

  @Test
  void thePreviousRunEndedEarlierAndRanksCommanders() {
    var run =
        new ScoreRunSummary(
            RUN,
            "topdeck",
            "EDH",
            LocalDate.of(2025, 10, 1),
            LocalDate.of(2026, 10, 1),
            OffsetDateTime.parse("2026-10-20T00:00:00Z"),
            "TopDeck",
            1200,
            90000,
            83339,
            9000,
            20534,
            null,
            4,
            null,
            null,
            null,
            null,
            null,
            List.of(),
            null);
    when(jdbc.queryForList(sql.capture(), args.capture(), eq(String.class)))
        .thenReturn(List.of(PREVIOUS));

    assertThat(repository.previousRun(run)).isEqualTo(PREVIOUS);
    assertThat(args.getValue())
        .containsEntry("format", "EDH")
        .containsEntry("endsBefore", LocalDate.of(2026, 10, 1));
    assertThat(sql.getValue())
        .contains("r.window_ends_before<:endsBefore")
        .contains("cardinality(a.commanders)>0");
  }

  @Test
  void aPageMapsEachCommanderWithItsCards() throws Exception {
    repository.page(RUN, PREVIOUS, query("limit", "10"));
    verify(jdbc).query(sql.capture(), args.capture(), commanderRows.capture());
    assertThat(args.getValue()).containsEntry("limit", 10).containsEntry("offset", 0);
    assertThat(sql.getValue())
        .contains("unnest(r.commanders) WITH ORDINALITY k(oracle_id,position)")
        .endsWith("ORDER BY r.deck_count DESC NULLS LAST,r.label LIMIT :limit OFFSET :offset");
    when(row.getString(1))
        .thenReturn(
            """
            {"rank":1,"rank_change":2,"label":"Kinnan, Bonder Prodigy",
             "commanders":[{"oracle_id":"%s","name":"Kinnan, Bonder Prodigy","mana_cost":"{G}{U}",
               "type_line":"Legendary Creature — Human Druid","color_identity":["G","U"],
               "preview_printing":null}],
             "colors":["U","G"],"deck_count":4012,"event_count":610,"top_cut_count":800,
             "top_cut_known_decks":3900,"win_rate":0.2731,"win_rate_delta":0.0231,
             "win_rate_ci95":0.0062,"games":19870,"top_cut_lift":1.21,"share_delta":-0.004,
             "series_decks":[300,310,320,330,340,350,330,320,310,300,290,280],
             "core_card_count":71}
            """
                .formatted(KINNAN));

    var commander = commanderRows.getValue().mapRow(row, 0);

    assertThat(commander.rank_change()).isEqualTo(2);
    assertThat(commander.colors()).containsExactly("U", "G");
    assertThat(commander.commanders())
        .extracting(CommanderCard::oracle_id, CommanderCard::preview_printing)
        .containsExactly(org.assertj.core.api.Assertions.tuple(KINNAN, null));
    assertThat(commander.core_card_count()).isEqualTo(71);
  }
}
