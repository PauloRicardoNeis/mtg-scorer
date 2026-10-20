package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.catalog.CatalogModels.Printing;
import java.sql.Array;
import java.sql.ResultSet;
import java.time.LocalDate;
import java.time.OffsetDateTime;
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
class RankingRepositoryTests {
  private static final String RUN = "scores-" + "a".repeat(64);
  private static final UUID BOLT = UUID.fromString("4457ed35-7c10-48c8-9776-456485fdf070");

  @Mock private NamedParameterJdbcTemplate jdbc;
  @Mock private ResultSet row;
  @Mock private Array colors;
  @Captor private ArgumentCaptor<String> sql;
  @Captor private ArgumentCaptor<Map<String, Object>> args;
  @Captor private ArgumentCaptor<RowMapper<RankedCard>> cardRows;
  @Captor private ArgumentCaptor<RowMapper<RankedFormat>> formatRows;
  @Captor private ArgumentCaptor<RowMapper<ScoreRunSummary>> runRows;

  private RankingRepository repository;

  @BeforeEach
  void setUp() {
    repository = new RankingRepository(jdbc, JsonMapper.builder().build());
  }

  private static RankingQuery query(String... pairs) {
    Map<String, List<String>> input = new HashMap<>();
    for (int index = 0; index < pairs.length; index += 2)
      input.computeIfAbsent(pairs[index], key -> new java.util.ArrayList<>()).add(pairs[index + 1]);
    return RankingQuery.parse(input);
  }

  @Test
  void activeFormatsMapEachActiveRun() throws Exception {
    repository.activeFormats();
    verify(jdbc).query(anyString(), eq(Map.of()), formatRows.capture());
    when(row.getString("format_name")).thenReturn("Modern");
    when(row.getString("source")).thenReturn("topdeck");
    when(row.getString("score_run_id")).thenReturn(RUN);

    assertThat(formatRows.getValue().mapRow(row, 0))
        .isEqualTo(new RankedFormat("Modern", "topdeck", RUN));
  }

  @Test
  void aRunSummaryIsReadFromItsPublishedJson() throws Exception {
    when(jdbc.query(anyString(), eq(Map.of("run", RUN)), runRows.capture())).thenReturn(List.of());

    assertThat(repository.run(RUN)).isEmpty();
    when(row.getString(1))
        .thenReturn(
            """
            {"score_run_id":"%s","source":"topdeck","format_name":"Modern",
             "window_starts_on":"2026-03-01","window_ends_before":"2026-09-01",
             "published_at":"2026-10-19T01:02:03.456789+00:00","attribution":"Data provided by TopDeck.gg",
             "events":12,"players":249,"decks":231,"top_cut_decks":67,
             "methods":[{"method_id":"max-ratio","method_version":"max-ratio-v1","label":"Relative volume",
               "description":"Count ÷ max.","outputs":["max_ratio"]}]}
            """
                .formatted(RUN));
    var summary = runRows.getValue().mapRow(row, 0);

    assertThat(summary.window_starts_on()).isEqualTo(LocalDate.of(2026, 3, 1));
    assertThat(summary.published_at())
        .isEqualTo(OffsetDateTime.parse("2026-10-19T01:02:03.456789Z"));
    assertThat(summary.decks()).isEqualTo(231);
    assertThat(summary.methods())
        .extracting(ScoreMethod::outputs)
        .containsExactly(List.of("max_ratio"));
  }

  @Test
  void theActiveCatalogIsOptional() {
    when(jdbc.queryForList(anyString(), eq(Map.of()), eq(String.class)))
        .thenReturn(List.of("catalog-a"))
        .thenReturn(List.of());

    assertThat(repository.activeCatalog()).isEqualTo("catalog-a");
    assertThat(repository.activeCatalog()).isNull();
  }

  @Test
  void anUnfilteredCountBindsOnlyTheRunMethodAndOutput() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(608L);

    assertThat(repository.count(RUN, "max-ratio", "max_ratio", query())).isEqualTo(608);
    assertThat(args.getValue())
        .containsOnly(
            Map.entry("run", RUN),
            Map.entry("method", "max-ratio"),
            Map.entry("output", "max_ratio"));
    assertThat(sql.getValue()).startsWith("SELECT count(*) FROM").doesNotContain(" WHERE strpos");
  }

  @Test
  void filtersBindSearchTypeAndAnyChromaticOrColorlessColor() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(1L);

    repository.count(
        RUN,
        "max-ratio",
        "max_ratio",
        query("q", "Bolt", "type", "instant", "color", "R", "color", "C"));

    assertThat(args.getValue())
        .contains(
            Map.entry("q", "bolt"),
            Map.entry("anyColors", "R"),
            Map.entry("typePattern", "(^|//)[^—/]*\\mInstant\\M"));
    assertThat(sql.getValue())
        .contains("strpos(lower(r.name),:q)>0")
        .contains("shown.type_line ~ :typePattern")
        .contains("(c.colors && string_to_array(:anyColors,',') OR c.colors='{}')");
  }

  @Test
  void colorlessAloneNeedsNoChromaticColors() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(0L);

    repository.count(RUN, "max-ratio", "max_ratio", query("color", "C"));

    assertThat(args.getValue()).doesNotContainKey("anyColors");
    assertThat(sql.getValue()).contains("(c.colors='{}')");
  }

  @Test
  void chromaticColorsAloneExcludeColorlessCards() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(0L);

    repository.count(RUN, "max-ratio", "max_ratio", query("color", "U", "color", "W"));

    assertThat(args.getValue()).contains(Map.entry("anyColors", "W,U"));
    assertThat(sql.getValue())
        .contains("(c.colors && string_to_array(:anyColors,','))")
        .doesNotContain("c.colors='{}'");
  }

  @Test
  void eachSortOrdersByItsStoredValueThenName() {
    for (var expected :
        Map.of(
                "score", "ORDER BY r.score DESC NULLS LAST,r.name",
                "decks", "ORDER BY r.deck_count DESC,r.name",
                "top_cuts", "ORDER BY r.top_cut_count DESC NULLS LAST,r.name",
                "name", "ORDER BY r.name,r.oracle_id")
            .entrySet()) {
      repository.page(RUN, "max-ratio", "max_ratio", query("sort", expected.getKey()));
    }
    verify(jdbc, org.mockito.Mockito.times(4)).query(sql.capture(), anyMap(), cardRows.capture());
    assertThat(sql.getAllValues())
        .anySatisfy(text -> assertThat(text).contains("ORDER BY r.score DESC NULLS LAST,r.name"))
        .anySatisfy(text -> assertThat(text).contains("ORDER BY r.deck_count DESC,r.name"))
        .anySatisfy(
            text -> assertThat(text).contains("ORDER BY r.top_cut_count DESC NULLS LAST,r.name"))
        .anySatisfy(text -> assertThat(text).contains("ORDER BY r.name,r.oracle_id LIMIT"));
  }

  @Test
  void aPageBindsItsWindowAndMapsACatalogCard() throws Exception {
    repository.page(RUN, "max-ratio", "max_ratio", query("limit", "10", "offset", "20"));
    verify(jdbc).query(sql.capture(), args.capture(), cardRows.capture());
    assertThat(args.getValue()).contains(Map.entry("limit", 10), Map.entry("offset", 20));
    stubCard();
    when(row.getArray("color_identity")).thenReturn(colors);
    when(colors.getArray()).thenReturn(new String[] {"R"});
    when(row.getString("printing"))
        .thenReturn(
            """
            {"scryfall_id":"10000000-0000-4000-8000-000000000001","set_code":"m11","set_name":"Magic 2011",
             "collector_number":"149","rarity":"common","released_on":"2010-07-16","language":"en",
             "games":["paper"],"source_uri":"https://scryfall.com/card/m11/149","images":[]}
            """);

    RankedCard card = cardRows.getValue().mapRow(row, 0);

    assertThat(card.rank()).isEqualTo(1);
    assertThat(card.oracle_id()).isEqualTo(BOLT);
    assertThat(card.score()).isEqualTo(100.0);
    assertThat(card.top_cut_count()).isEqualTo(3);
    assertThat(card.color_identity()).containsExactly("R");
    assertThat(card.preview_printing()).extracting(Printing::set_code).isEqualTo("m11");
  }

  @Test
  void aCardOutsideTheCatalogHasNoDetailsAndUnknownsStayNull() throws Exception {
    repository.page(RUN, "max-ratio", "max_ratio", query());
    verify(jdbc).query(anyString(), anyMap(), cardRows.capture());
    stubCard();
    when(row.getObject("top_cut_count", Integer.class)).thenReturn(null);
    when(row.getString("archetype_label")).thenReturn(null);
    when(row.getArray("color_identity")).thenReturn(null);
    when(row.getString("printing")).thenReturn(null);

    RankedCard card = cardRows.getValue().mapRow(row, 0);

    assertThat(card.top_cut_count()).isNull();
    assertThat(card.archetype_label()).isNull();
    assertThat(card.color_identity()).isNull();
    assertThat(card.preview_printing()).isNull();
  }

  private void stubCard() throws Exception {
    when(row.getLong("ranking")).thenReturn(1L);
    when(row.getObject("oracle_id", UUID.class)).thenReturn(BOLT);
    when(row.getString("name")).thenReturn("Lightning Bolt");
    when(row.getObject("score", Double.class)).thenReturn(100.0);
    when(row.getInt("deck_count")).thenReturn(20);
    when(row.getInt("event_count")).thenReturn(5);
    org.mockito.Mockito.lenient().when(row.getObject("top_cut_count", Integer.class)).thenReturn(3);
    when(row.getInt("top_cut_known_decks")).thenReturn(10);
    org.mockito.Mockito.lenient().when(row.getString("archetype_label")).thenReturn("Burn");
    when(row.getInt("archetype_deck_count")).thenReturn(8);
    when(row.getInt("labelled_deck_count")).thenReturn(20);
    when(row.getString("mana_cost")).thenReturn("{R}");
    when(row.getString("type_line")).thenReturn("Instant");
  }
}
