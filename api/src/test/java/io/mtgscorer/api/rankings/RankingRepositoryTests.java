package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.catalog.CatalogModels.Printing;
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
  private static final String PREVIOUS = "scores-" + "b".repeat(64);
  private static final UUID BOLT = UUID.fromString("4457ed35-7c10-48c8-9776-456485fdf070");

  @Mock private NamedParameterJdbcTemplate jdbc;
  @Mock private ResultSet row;
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
  void activeFormatsMapEachActiveRunWithItsDecks() throws Exception {
    repository.activeFormats();
    verify(jdbc).query(anyString(), eq(Map.of()), formatRows.capture());
    when(row.getString("format_name")).thenReturn("Modern");
    when(row.getString("source")).thenReturn("topdeck");
    when(row.getString("score_run_id")).thenReturn(RUN);
    when(row.getInt("decks")).thenReturn(231);
    when(row.getObject("players_per_game", Integer.class)).thenReturn(2);

    assertThat(formatRows.getValue().mapRow(row, 0))
        .isEqualTo(new RankedFormat("Modern", "topdeck", RUN, 231, 2));
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
             "events":12,"players":249,"decks":231,"top_cut_decks":67,"scored_cards":608,
             "matches":1798,"players_per_game":2,"field_win_rate":0.499,"field_top_cut_rate":0.2479,
             "series_starts_on":"2025-09-06","series_period_days":30,
             "series_decks":[0,0,0,0,0,0,5,0,0,0,0,0],
             "methods":[{"method_id":"max-ratio","method_version":"max-ratio-v1","label":"Relative volume",
               "description":"Count ÷ max.","outputs":["max_ratio"]}]}
            """
                .formatted(RUN));
    var summary = runRows.getValue().mapRow(row, 0);

    assertThat(summary.window_starts_on()).isEqualTo(LocalDate.of(2026, 3, 1));
    assertThat(summary.published_at())
        .isEqualTo(OffsetDateTime.parse("2026-10-19T01:02:03.456789Z"));
    assertThat(summary.decks()).isEqualTo(231);
    assertThat(summary.scored_cards()).isEqualTo(608);
    assertThat(summary.matches()).isEqualTo(1798);
    assertThat(summary.series_starts_on()).isEqualTo(LocalDate.of(2025, 9, 6));
    assertThat(summary.series_decks()).hasSize(12);
    assertThat(summary.methods())
        .extracting(ScoreMethod::outputs)
        .containsExactly(List.of("max_ratio"));
  }

  @Test
  void aRunWithoutPerformanceDataLeavesItUnknown() throws Exception {
    repository.run(RUN);
    verify(jdbc).query(anyString(), eq(Map.of("run", RUN)), runRows.capture());
    when(row.getString(1))
        .thenReturn(
            """
            {"score_run_id":"%s","source":"topdeck","format_name":"Modern",
             "window_starts_on":"2026-03-01","window_ends_before":"2026-09-01",
             "published_at":"2026-10-19T01:02:03Z","attribution":"TopDeck",
             "events":12,"players":249,"decks":231,"top_cut_decks":67,"scored_cards":608,
             "matches":null,"players_per_game":null,"field_win_rate":null,"field_top_cut_rate":null,
             "series_starts_on":null,"series_period_days":null,"series_decks":null,"methods":[]}
            """
                .formatted(RUN));

    var summary = runRows.getValue().mapRow(row, 0);

    assertThat(summary.matches()).isNull();
    assertThat(summary.field_win_rate()).isNull();
    assertThat(summary.series_decks()).isNull();
  }

  @Test
  void windowsListOneRunPerSourceAndWindowWithTheActiveOneMarked() throws Exception {
    @SuppressWarnings("unchecked")
    ArgumentCaptor<RowMapper<RunWindow>> windowRows = ArgumentCaptor.forClass(RowMapper.class);
    repository.windows("Modern");
    verify(jdbc).query(sql.capture(), eq(Map.of("format", "Modern")), windowRows.capture());
    assertThat(sql.getValue())
        .contains("DISTINCT ON (r.source,r.window_starts_on,r.window_ends_before)")
        .contains("ORDER BY window_ends_before DESC");
    when(row.getString("score_run_id")).thenReturn(RUN);
    when(row.getString("source")).thenReturn("topdeck");
    when(row.getObject("window_starts_on", LocalDate.class)).thenReturn(LocalDate.of(2026, 3, 1));
    when(row.getObject("window_ends_before", LocalDate.class)).thenReturn(LocalDate.of(2026, 9, 1));
    when(row.getInt("decks")).thenReturn(231);
    when(row.getBoolean("active")).thenReturn(true);

    assertThat(windowRows.getValue().mapRow(row, 0))
        .isEqualTo(
            new RunWindow(
                RUN, "topdeck", LocalDate.of(2026, 3, 1), LocalDate.of(2026, 9, 1), 231, true));
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
  void thePreviousRunEndedEarlierInTheSameSourceAndFormatAndHasTheMethod() {
    var run =
        new ScoreRunSummary(
            RUN,
            "topdeck",
            "Modern",
            LocalDate.of(2026, 3, 1),
            LocalDate.of(2026, 9, 1),
            OffsetDateTime.parse("2026-10-19T00:00:00Z"),
            "TopDeck",
            12,
            249,
            231,
            67,
            608,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            List.of());
    when(jdbc.queryForList(sql.capture(), args.capture(), eq(String.class)))
        .thenReturn(List.of(PREVIOUS))
        .thenReturn(List.of());

    assertThat(repository.previousRun(run, "constructed-score")).isEqualTo(PREVIOUS);
    assertThat(repository.previousRun(run, "constructed-score")).isNull();
    assertThat(args.getValue())
        .containsEntry("source", "topdeck")
        .containsEntry("format", "Modern")
        .containsEntry("endsBefore", LocalDate.of(2026, 9, 1))
        .containsEntry("method", "constructed-score");
    assertThat(sql.getValue()).contains("r.window_ends_before<:endsBefore");
  }

  @Test
  void anUnfilteredCountBindsOnlyTheRunsMethodAndOutput() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(608L);

    assertThat(repository.count(RUN, null, "max-ratio", "max_ratio", query())).isEqualTo(608);
    assertThat(args.getValue())
        .containsOnlyKeys("run", "previous", "method", "output")
        .containsEntry("run", RUN)
        .containsEntry("method", "max-ratio")
        .containsEntry("output", "max_ratio");
    assertThat(sql.getValue()).startsWith("SELECT count(*) FROM").doesNotContain(" WHERE strpos");
  }

  @Test
  void filtersBindSearchTypeAndAnyChromaticOrColorlessColor() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(1L);

    repository.count(
        RUN,
        null,
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

    repository.count(RUN, null, "max-ratio", "max_ratio", query("color", "C"));

    assertThat(args.getValue()).doesNotContainKey("anyColors");
    assertThat(sql.getValue()).contains("(c.colors='{}')");
  }

  @Test
  void chromaticColorsAloneExcludeColorlessCards() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(0L);

    repository.count(RUN, null, "max-ratio", "max_ratio", query("color", "U", "color", "W"));

    assertThat(args.getValue()).contains(Map.entry("anyColors", "W,U"));
    assertThat(sql.getValue())
        .contains("(c.colors && string_to_array(:anyColors,','))")
        .doesNotContain("c.colors='{}'");
  }

  @Test
  void risersAndFallersKeepCardsThatGainedOrLostPlaces() {
    when(jdbc.queryForObject(sql.capture(), args.capture(), eq(Long.class))).thenReturn(0L);

    repository.count(RUN, PREVIOUS, "max-ratio", "max_ratio", query("view", "risers"));
    repository.count(RUN, PREVIOUS, "max-ratio", "max_ratio", query("view", "fallers"));

    assertThat(sql.getAllValues().get(0)).contains("WHERE prev.ranking>r.ranking");
    assertThat(sql.getAllValues().get(1)).contains("WHERE prev.ranking<r.ranking");
    assertThat(args.getValue()).containsEntry("previous", PREVIOUS);
  }

  @Test
  void viewCountsIgnoreTheSelectedView() throws Exception {
    repository.viewCounts(RUN, PREVIOUS, "max-ratio", "max_ratio", query("view", "risers"));

    @SuppressWarnings("unchecked")
    ArgumentCaptor<RowMapper<ViewCounts>> counts = ArgumentCaptor.forClass(RowMapper.class);
    verify(jdbc).queryForObject(sql.capture(), anyMap(), counts.capture());
    assertThat(sql.getValue())
        .contains("count(*) FILTER (WHERE prev.ranking>r.ranking) risers")
        .doesNotContain("WHERE prev.ranking>r.ranking AND")
        .doesNotEndWith("prev.ranking>r.ranking");
    when(row.getLong("total")).thenReturn(8L);
    when(row.getLong("risers")).thenReturn(2L);
    when(row.getLong("fallers")).thenReturn(1L);
    assertThat(counts.getValue().mapRow(row, 0)).isEqualTo(new ViewCounts(8, 2, 1));
  }

  @Test
  void eachSortOrdersByItsStoredValueThenName() {
    for (var expected :
        Map.of(
                "score", "r.score DESC NULLS LAST,r.name,r.oracle_id",
                "decks", "r.deck_count DESC NULLS LAST,r.name,r.oracle_id",
                "win_rate", "r.win_rate DESC NULLS LAST,r.name,r.oracle_id",
                "top_cut_lift", "r.top_cut_lift DESC NULLS LAST,r.name,r.oracle_id",
                "trend", "r.share_delta DESC NULLS LAST,r.name,r.oracle_id",
                "movement", "prev.ranking-r.ranking DESC NULLS LAST,r.name,r.oracle_id",
                "name", "r.name ASC,r.oracle_id")
            .entrySet())
      assertThat(RankingRepository.orderBy(query("sort", expected.getKey())))
          .as(expected.getKey())
          .isEqualTo(expected.getValue());
    assertThat(RankingRepository.orderBy(query("sort", "win_rate", "order", "asc")))
        .isEqualTo("r.win_rate ASC NULLS LAST,r.name,r.oracle_id");
    assertThat(RankingRepository.orderBy(query("sort", "name", "order", "desc")))
        .isEqualTo("r.name DESC,r.oracle_id");
  }

  @Test
  void aPageBindsItsWindowAndMapsACatalogCard() throws Exception {
    repository.page(RUN, null, "max-ratio", "max_ratio", query("limit", "10", "offset", "20"));
    verify(jdbc).query(sql.capture(), args.capture(), cardRows.capture());
    assertThat(args.getValue()).contains(Map.entry("limit", 10), Map.entry("offset", 20));
    assertThat(sql.getValue()).contains("ORDER BY r.score DESC NULLS LAST");
    when(row.getString(1))
        .thenReturn(
            """
            {"rank":1,"rank_change":3,"oracle_id":"%s","name":"Lightning Bolt","score":100.0,
             "deck_count":20,"event_count":5,"top_cut_count":3,"top_cut_known_decks":10,
             "archetype_label":"Burn","archetype_deck_count":8,"labelled_deck_count":20,
             "win_rate":0.55,"win_rate_delta":0.05,"win_rate_ci95":0.04,"games":120,
             "top_cut_lift":1.2,"share_delta":0.01,"avg_copies":4.0,
             "series_decks":[0,0,0,0,0,0,3,0,0,0,0,0],
             "archetypes":[{"label":"Burn","deck_count":8,"colors":["R"]}],"archetype_count":2,
             "mana_cost":"{R}","type_line":"Instant","color_identity":["R"],
             "preview_printing":{"scryfall_id":"10000000-0000-4000-8000-000000000001","set_code":"m11",
               "set_name":"Magic 2011","collector_number":"149","rarity":"common",
               "released_on":"2010-07-16","language":"en","games":["paper"],
               "source_uri":"https://scryfall.com/card/m11/149","images":[]}}
            """
                .formatted(BOLT));

    RankedCard card = cardRows.getValue().mapRow(row, 0);

    assertThat(card.rank()).isEqualTo(1);
    assertThat(card.rank_change()).isEqualTo(3);
    assertThat(card.oracle_id()).isEqualTo(BOLT);
    assertThat(card.score()).isEqualTo(100.0);
    assertThat(card.top_cut_count()).isEqualTo(3);
    assertThat(card.archetypes()).containsExactly(new ArchetypeShare("Burn", 8, List.of("R")));
    assertThat(card.color_identity()).containsExactly("R");
    assertThat(card.preview_printing()).extracting(Printing::set_code).isEqualTo("m11");
  }

  @Test
  void aCardOutsideTheCatalogHasNoDetailsAndUnknownsStayNull() throws Exception {
    repository.page(RUN, null, "max-ratio", "max_ratio", query());
    verify(jdbc).query(anyString(), anyMap(), cardRows.capture());
    when(row.getString(1))
        .thenReturn(
            """
            {"rank":4,"rank_change":null,"oracle_id":"%s","name":"Lightning Bolt","score":null,
             "deck_count":20,"event_count":5,"top_cut_count":null,"top_cut_known_decks":0,
             "archetype_label":null,"archetype_deck_count":0,"labelled_deck_count":0,
             "win_rate":null,"win_rate_delta":null,"win_rate_ci95":null,"games":null,
             "top_cut_lift":null,"share_delta":null,"avg_copies":null,"series_decks":null,
             "archetypes":[],"archetype_count":null,"mana_cost":null,"type_line":null,
             "color_identity":null,"preview_printing":null}
            """
                .formatted(BOLT));

    RankedCard card = cardRows.getValue().mapRow(row, 0);

    assertThat(card.rank_change()).isNull();
    assertThat(card.top_cut_count()).isNull();
    assertThat(card.win_rate()).isNull();
    assertThat(card.archetypes()).isEmpty();
    assertThat(card.color_identity()).isNull();
    assertThat(card.preview_printing()).isNull();
  }

  @Test
  void aRunWithoutScoredCardsHasNoLeadingDeckCount() {
    when(jdbc.queryForObject(anyString(), eq(Map.of("run", RUN)), eq(Integer.class)))
        .thenReturn(null)
        .thenReturn(91);

    assertThat(repository.maxDeckCount(RUN)).isZero();
    assertThat(repository.maxDeckCount(RUN)).isEqualTo(91);
  }
}
