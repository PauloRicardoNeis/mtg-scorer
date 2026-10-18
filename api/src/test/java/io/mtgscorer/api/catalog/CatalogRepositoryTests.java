package io.mtgscorer.api.catalog;

import static io.mtgscorer.api.catalog.CatalogModels.*;
import static io.mtgscorer.api.catalog.QueryParams.cards;
import static io.mtgscorer.api.catalog.QueryParams.printings;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.error.CatalogProblem;
import java.sql.Array;
import java.sql.ResultSet;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
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

/**
 * Parameter binding and row mapping only; the SQL itself runs against PostgreSQL in the end-to-end
 * HTTP tests.
 */
@ExtendWith(MockitoExtension.class)
class CatalogRepositoryTests {
  private static final String CARD = "00000000-0000-4000-8000-000000000001";
  private static final UUID CARD_ID = UUID.fromString(CARD);
  private static final String PRINTING = "10000000-0000-4000-8000-000000000001";

  /** A printing as the PRINTING_JSON projection renders it. */
  private static final String PRINTING_JSON =
      """
      {"scryfall_id":"%s","set_code":"m11","set_name":"Magic 2011","collector_number":"149",
       "rarity":"common","released_on":"2010-07-16","language":"en","games":["paper","mtgo"],
       "source_uri":"https://scryfall.com/card/m11/149",
       "images":[{"face_index":null,"source_uri":"https://cards.scryfall.io/large/front/a.jpg",
                  "artist":"Christopher Moeller"}]}
      """
          .formatted(PRINTING);

  private static final Printing PRINTING_ROW =
      new Printing(
          UUID.fromString(PRINTING),
          "m11",
          "Magic 2011",
          "149",
          "common",
          LocalDate.of(2010, 7, 16),
          "en",
          List.of("paper", "mtgo"),
          "https://scryfall.com/card/m11/149",
          List.of(
              new PrintingImage(
                  null, "https://cards.scryfall.io/large/front/a.jpg", "Christopher Moeller")));

  @Mock private NamedParameterJdbcTemplate jdbc;
  @Mock private ResultSet row;
  @Captor private ArgumentCaptor<Map<String, Object>> args;
  @Captor private ArgumentCaptor<RowMapper<CatalogRepository.CardRow>> cardRows;
  @Captor private ArgumentCaptor<RowMapper<Printing>> printingRows;

  private CatalogRepository repository;

  @BeforeEach
  void setUp() {
    repository = new CatalogRepository(jdbc, JsonMapper.builder().build());
  }

  @Test
  void anUnfilteredSearchBindsOnlyTheSnapshotAndALookaheadLimit() {
    repository.search("catalog-a", cards("limit", "10"), null);

    verify(jdbc).query(anyString(), args.capture(), cardRows.capture());
    assertThat(args.getValue())
        .containsOnly(Map.entry("snapshot", "catalog-a"), Map.entry("limit", 11));
  }

  @Test
  void aFilteredContinuationBindsEveryFilterAndTheCursorKey() {
    var query =
        cards(
            "q",
            "Lightning",
            "set",
            "m11",
            "rarity",
            "common",
            "game",
            "paper",
            "color_identity",
            "RU",
            "color",
            "W",
            "color",
            "R",
            "color",
            "C",
            "type",
            "creature");
    var cursor =
        new CursorCodec.Cursor(
            1, "cards", "catalog-a", "hash", "name_asc", 24, List.of("bolt", CARD));

    repository.search("catalog-a", query, cursor);

    verify(jdbc).query(anyString(), args.capture(), cardRows.capture());
    assertThat(args.getValue())
        .containsOnlyKeys(
            "snapshot",
            "limit",
            "q",
            "sets",
            "rarities",
            "game",
            "colors",
            "anyColors",
            "typePattern",
            "lastName",
            "lastId")
        .contains(
            Map.entry("q", "lightning"),
            Map.entry("sets", List.of("m11")),
            Map.entry("rarities", List.of("common")),
            Map.entry("game", "paper"),
            Map.entry("colors", "U,R"),
            // Colorless is matched separately; only chromatic colors bind as an array.
            Map.entry("anyColors", "W,R"),
            Map.entry("lastName", "bolt"),
            Map.entry("lastId", CARD),
            Map.entry("limit", 25));
  }

  @Test
  void colorlessFiltersBindNoChromaticColors() {
    repository.search("catalog-a", cards("color_identity", "C", "color", "C"), null);

    verify(jdbc).query(anyString(), args.capture(), cardRows.capture());
    // An empty array: only cards with no color identity at all are contained in it.
    assertThat(args.getValue()).containsEntry("colors", "").doesNotContainKey("anyColors");
  }

  @Test
  void chromaticColorFiltersBindInWubrgOrder() {
    repository.search("catalog-a", cards("color", "R", "color", "U"), null);

    verify(jdbc).query(anyString(), args.capture(), cardRows.capture());
    assertThat(args.getValue()).containsEntry("anyColors", "U,R").doesNotContainKey("colors");
  }

  @Test
  void typePatternMatchesTheTypeBeforeSubtypesOnAnyFace() {
    assertThat(typeMatches("creature", "Legendary Creature — Elf Druid")).isTrue();
    assertThat(typeMatches("creature", "Artifact Creature — Golem")).isTrue();
    assertThat(typeMatches("creature", "Instant — Arcane // Creature — Spirit")).isTrue();
    assertThat(typeMatches("creature", "Enchantment — Aura")).isFalse();
    assertThat(typeMatches("creature", "Enchantment — Creature Aura")).isFalse();
    assertThat(typeMatches("creature", "Legendary Creatureling")).isFalse();
    assertThat(typeMatches("artifact", "Artifact Creature — Golem")).isTrue();
    assertThat(typeMatches("land", "Basic Land — Island")).isTrue();
    assertThat(typeMatches("land", "Sorcery // Land")).isTrue();
    assertThat(typeMatches("land", "Snow Creature — Island Spirit")).isFalse();
    assertThat(typeMatches("planeswalker", "Legendary Planeswalker — Jace")).isTrue();
  }

  @Test
  void searchRowsMapTheSummaryAndPreviewPrinting() throws Exception {
    repository.search("catalog-a", cards(), null);
    verify(jdbc).query(anyString(), args.capture(), cardRows.capture());
    Array identity = mock(Array.class);
    when(identity.getArray()).thenReturn(new String[] {"R"});
    stubCardRow(identity);

    var mapped = cardRows.getValue().mapRow(row, 0);

    assertThat(mapped.nameKey()).isEqualTo("lightning bolt");
    assertThat(mapped.summary())
        .isEqualTo(
            new CardSummary(
                CARD_ID,
                "Lightning Bolt",
                "normal",
                "{R}",
                "Instant",
                List.of("R"),
                3,
                PRINTING_ROW));
  }

  @Test
  void anUnknownColorIdentityStaysUnknown() throws Exception {
    repository.search("catalog-a", cards(), null);
    verify(jdbc).query(anyString(), args.capture(), cardRows.capture());
    stubCardRow(null);

    assertThat(cardRows.getValue().mapRow(row, 0).summary().color_identity()).isNull();
  }

  @Test
  void detailMapsTheCardWithItsFaces() throws Exception {
    when(row.getString(1))
        .thenReturn(
            """
            {"catalog_snapshot_id":"catalog-a","oracle_id":"%s","name":"Fire // Ice",
             "layout":"split","mana_cost":"{1}{R} // {1}{U}","mana_value":4.0,"oracle_text":null,
             "type_line":"Instant // Instant","colors":["U","R"],"color_identity":["U","R"],
             "faces":[
               {"face_index":0,"name":"Fire","mana_cost":"{1}{R}","oracle_text":"Fire deals 2 damage.",
                "type_line":"Instant","colors":["R"]},
               {"face_index":1,"name":"Ice","mana_cost":"{1}{U}","oracle_text":"Tap target permanent.",
                "type_line":"Instant","colors":null}]}
            """
                .formatted(CARD));
    when(jdbc.query(anyString(), anyMap(), any(RowMapper.class)))
        .thenAnswer(call -> List.of(call.<RowMapper<?>>getArgument(2).mapRow(row, 0)));

    var detail = repository.detail("catalog-a", CARD_ID);

    assertThat(detail)
        .isEqualTo(
            new CardDetail(
                "catalog-a",
                CARD_ID,
                "Fire // Ice",
                "split",
                "{1}{R} // {1}{U}",
                4.0,
                null,
                "Instant // Instant",
                List.of("U", "R"),
                List.of("U", "R"),
                List.of(
                    new Face(0, "Fire", "{1}{R}", "Fire deals 2 damage.", "Instant", List.of("R")),
                    new Face(1, "Ice", "{1}{U}", "Tap target permanent.", "Instant", null))));
  }

  @Test
  void aCardOutsideTheSnapshotIsNotFound() {
    assertCardNotFound(() -> repository.detail("catalog-a", CARD_ID));
  }

  @Test
  void printingsRequireTheCardBeforeListing() {
    when(jdbc.queryForObject(anyString(), anyMap(), eq(Integer.class))).thenReturn(0);

    assertCardNotFound(() -> repository.printings("catalog-a", CARD_ID, printings(), null));
    verify(jdbc, never()).query(anyString(), anyMap(), any(RowMapper.class));
  }

  @Test
  void aFirstPrintingPageBindsOnlyTheCardAndALookaheadLimit() {
    when(jdbc.queryForObject(anyString(), anyMap(), eq(Integer.class))).thenReturn(1);

    repository.printings("catalog-a", CARD_ID, printings(), null);

    verify(jdbc).query(anyString(), args.capture(), printingRows.capture());
    assertThat(args.getValue())
        .containsOnly(
            Map.entry("snapshot", "catalog-a"),
            Map.entry("oracle", CARD_ID),
            Map.entry("limit", 25));
  }

  @Test
  void printingsBindThePoolFiltersAndTheLastScryfallId() throws Exception {
    when(jdbc.queryForObject(anyString(), anyMap(), eq(Integer.class))).thenReturn(1);
    var query = printings("set", "m11", "rarity", "rare", "game", "arena", "limit", "5");
    var cursor =
        new CursorCodec.Cursor(
            1, "printings:" + CARD, "catalog-a", "hash", "scryfall_id_asc", 5, List.of(PRINTING));

    repository.printings("catalog-a", CARD_ID, query, cursor);

    verify(jdbc).query(anyString(), args.capture(), printingRows.capture());
    assertThat(args.getValue())
        .containsOnly(
            Map.entry("snapshot", "catalog-a"),
            Map.entry("oracle", CARD_ID),
            Map.entry("limit", 6),
            Map.entry("sets", List.of("m11")),
            Map.entry("rarities", List.of("rare")),
            Map.entry("game", "arena"),
            Map.entry("lastId", PRINTING));
    when(row.getString(1)).thenReturn(PRINTING_JSON);
    assertThat(printingRows.getValue().mapRow(row, 0)).isEqualTo(PRINTING_ROW);
  }

  private boolean typeMatches(String type, String typeLine) {
    repository.search("catalog-a", cards("type", type), null);
    verify(jdbc, atLeastOnce()).query(anyString(), args.capture(), cardRows.capture());
    String pattern = (String) args.getValue().get("typePattern");
    // PostgreSQL's \m and \M are the start and end of a word.
    return Pattern.compile(pattern.replace("\\m", "\\b(?=\\w)").replace("\\M", "\\b(?<=\\w)"))
        .matcher(typeLine)
        .find();
  }

  private void stubCardRow(Array identity) throws Exception {
    when(row.getObject("oracle_id", UUID.class)).thenReturn(CARD_ID);
    when(row.getString("name")).thenReturn("Lightning Bolt");
    when(row.getString("layout")).thenReturn("normal");
    when(row.getString("mana_cost")).thenReturn("{R}");
    when(row.getString("type_line")).thenReturn("Instant");
    when(row.getArray("color_identity")).thenReturn(identity);
    when(row.getLong("n")).thenReturn(3L);
    when(row.getString("printing")).thenReturn(PRINTING_JSON);
    when(row.getString("name_key")).thenReturn("lightning bolt");
  }

  private static void assertCardNotFound(ThrowingCallable call) {
    assertThatThrownBy(call)
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> {
              assertThat(problem.status()).isEqualTo(404);
              assertThat(problem.code()).isEqualTo("card_not_found");
            });
  }
}
