package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.sql.ResultSet;
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
class CompareRepositoryTests {
  private static final List<String> RUNS =
      List.of("scores-" + "a".repeat(64), "scores-" + "b".repeat(64));
  private static final UUID BOLT = UUID.fromString("4457ed35-7c10-48c8-9776-456485fdf070");

  @Mock private NamedParameterJdbcTemplate jdbc;
  @Mock private ResultSet row;
  @Captor private ArgumentCaptor<String> sql;
  @Captor private ArgumentCaptor<Map<String, Object>> args;
  @Captor private ArgumentCaptor<RowMapper<CompareFormat>> formatRows;
  @Captor private ArgumentCaptor<RowMapper<ComparedCard>> cardRows;

  private CompareRepository repository;

  @BeforeEach
  void setUp() {
    repository = new CompareRepository(jdbc, JsonMapper.builder().build());
  }

  private static CompareQuery query(String... pairs) {
    Map<String, List<String>> input = new HashMap<>();
    for (int index = 0; index < pairs.length; index += 2)
      input.computeIfAbsent(pairs[index], key -> new java.util.ArrayList<>()).add(pairs[index + 1]);
    return CompareQuery.parse(input);
  }

  @Test
  void formatsAreActiveRunsOfTheMethodWithTheCardsItScored() throws Exception {
    repository.formats("signature-score");
    verify(jdbc).query(sql.capture(), args.capture(), formatRows.capture());
    assertThat(args.getValue()).containsOnly(Map.entry("method", "signature-score"));
    assertThat(sql.getValue())
        .contains("m.method_id=:method")
        .contains("s.output=m.outputs[1] AND s.value IS NOT NULL");
    when(row.getString("format_name")).thenReturn("Modern");
    when(row.getString("score_run_id")).thenReturn(RUNS.getFirst());
    when(row.getInt("decks")).thenReturn(667);
    when(row.getObject("players_per_game", Integer.class)).thenReturn(2);
    when(row.getInt("scored_cards")).thenReturn(0);

    assertThat(formatRows.getValue().mapRow(row, 0))
        .isEqualTo(new CompareFormat("Modern", RUNS.getFirst(), 667, 2, 0));
  }

  @Test
  void anUnfilteredCountBindsOnlyTheRuns() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(939L);

    assertThat(repository.count(RUNS, query())).isEqualTo(939);
    assertThat(args.getValue())
        .containsOnlyKeys("runs", "method", "compared")
        .containsEntry("runs", String.join(",", RUNS))
        .containsEntry("method", "constructed-score")
        .containsEntry("compared", 2);
    assertThat(sql.getValue()).startsWith("SELECT count(*)").doesNotContain(" WHERE strpos");
  }

  @Test
  void cellsAreTheChosenMethodsScoresAndACardWithoutOneIsUnranked() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(5L);

    repository.count(RUNS, query("method", "signature-score"));

    assertThat(args.getValue()).containsEntry("method", "signature-score");
    assertThat(sql.getValue())
        .contains("s.method_id=:method AND s.output='score'")
        .contains("AND s.value IS NOT NULL) cells");
  }

  @Test
  void filtersBindSearchColorsAndEveryFormat() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(1L);

    repository.count(RUNS, query("q", "Bolt", "color", "R", "color", "C", "every", "true"));
    repository.count(RUNS, query("color", "C"));
    repository.count(RUNS, query("color", "W"));

    assertThat(sql.getAllValues().getFirst())
        .contains("strpos(lower(x.name),:q)>0")
        .contains("(c.colors && string_to_array(:anyColors,',') OR c.colors='{}')")
        .contains("x.ranked_in=:compared");
    assertThat(args.getAllValues().getFirst())
        .containsEntry("q", "bolt")
        .containsEntry("anyColors", "R");
    assertThat(sql.getAllValues().get(1)).contains("(c.colors='{}')").doesNotContain("anyColors");
    assertThat(sql.getAllValues().get(2))
        .contains("(c.colors && string_to_array(:anyColors,','))")
        .doesNotContain("c.colors='{}'");
  }

  @Test
  void eachSortOrdersByItsValueThenName() {
    Map<String, Object> bound = new HashMap<>();
    assertThat(CompareRepository.orderBy(query(), bound))
        .isEqualTo("x.best_score DESC NULLS LAST,x.name,x.oracle_id");
    assertThat(CompareRepository.orderBy(query("sort", "count"), bound))
        .isEqualTo("x.ranked_in DESC,x.best_score DESC NULLS LAST,x.name,x.oracle_id");
    assertThat(CompareRepository.orderBy(query("sort", "name", "order", "desc"), bound))
        .isEqualTo("x.name DESC,x.oracle_id");
    assertThat(bound).isEmpty();
    assertThat(CompareRepository.orderBy(query("sort", "Modern:trend", "order", "asc"), bound))
        .isEqualTo("(x.formats->:sortFormat->>:sortKey)::float8 ASC NULLS LAST,x.name,x.oracle_id");
    assertThat(bound).containsEntry("sortFormat", "Modern").containsEntry("sortKey", "share_delta");
  }

  @Test
  void aPageBindsItsWindowAndMapsACard() throws Exception {
    repository.page(RUNS, query("limit", "10", "offset", "20", "sort", "Modern:grade"));
    verify(jdbc).query(sql.capture(), args.capture(), cardRows.capture());
    assertThat(args.getValue())
        .containsEntry("limit", 10)
        .containsEntry("offset", 20)
        .containsEntry("sortKey", "score");
    assertThat(sql.getValue())
        .contains("ORDER BY (x.formats->:sortFormat->>:sortKey)::float8 DESC");
    when(row.getString(1))
        .thenReturn(
            """
            {"oracle_id":"%s","name":"Lightning Bolt","mana_cost":"{R}","type_line":"Instant",
             "color_identity":["R"],"ranked_in":2,"best_format":"Modern","best_score":93.75,
             "formats":{"Modern":{"rank":1,"score":93.75,"win_rate_delta":0.3,"share":0.57,
               "top_cut_lift":2.0,"share_delta":null}}}
            """
                .formatted(BOLT));

    ComparedCard card = cardRows.getValue().mapRow(row, 0);

    assertThat(card.oracle_id()).isEqualTo(BOLT);
    assertThat(card.best_format()).isEqualTo("Modern");
    assertThat(card.formats().get("Modern").rank()).isEqualTo(1);
    assertThat(card.formats().get("Modern").share_delta()).isNull();
  }

  @Test
  void countAndPageShareTheirFilters() {
    repository.page(RUNS, query("every", "true"));
    verify(jdbc)
        .query(anyString(), anyMap(), org.mockito.ArgumentMatchers.<RowMapper<ComparedCard>>any());
  }
}
