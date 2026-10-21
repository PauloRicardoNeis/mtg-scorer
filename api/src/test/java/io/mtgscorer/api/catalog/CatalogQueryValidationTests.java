package io.mtgscorer.api.catalog;

import static io.mtgscorer.api.catalog.QueryParams.cards;
import static io.mtgscorer.api.catalog.QueryParams.printings;
import static io.mtgscorer.api.catalog.QueryParams.repeated;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.IntStream;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
import org.junit.jupiter.api.Test;

class CatalogQueryValidationTests {

  @Test
  void anEmptyCardSearchUsesTheDefaults() {
    assertThat(cards())
        .isEqualTo(
            new CatalogQuery(
                null,
                "all",
                List.of(),
                List.of(),
                null,
                null,
                List.of(),
                null,
                "name_asc",
                24,
                null,
                null));
  }

  @Test
  void printingListsSortByScryfallIdAndAcceptOnlyPoolFilters() {
    assertThat(
            printings(
                "set",
                "m11",
                "rarity",
                "rare",
                "game",
                "arena",
                "limit",
                "10",
                "catalog_snapshot_id",
                "catalog-abc",
                "cursor",
                "opaque"))
        .isEqualTo(
            new CatalogQuery(
                null,
                "all",
                List.of("m11"),
                List.of("rare"),
                "arena",
                null,
                List.of(),
                null,
                "original_first",
                10,
                "catalog-abc",
                "opaque"));
    for (String name : List.of("q", "in", "color_identity", "color", "type", "sort"))
      assertInvalidQuery(() -> printings(name, "x"), "Unknown query parameter.");
  }

  @Test
  void searchLooksInTheWholeCardUnlessAPartIsNamed() {
    for (String in : CatalogQuery.SEARCH_IN) assertThat(cards("in", in).in()).isEqualTo(in);
    for (String in : List.of("Name", "oracle", "flavor", ""))
      assertInvalidQuery(() -> cards("in", in), "Invalid search field.");
  }

  @Test
  void searchTextIsBoundedAsSentAndBlankTextIsNoFilter() {
    assertThat(cards("q", "a".repeat(100)).q()).hasSize(100);
    assertInvalidQuery(() -> cards("q", "a".repeat(101)), "Search text exceeds 100 characters.");
    assertThat(cards("q", "  Lightning \t BOLT ").q()).isEqualTo("lightning bolt");
    assertThat(cards("q", "").q()).isNull();
    assertThat(cards("q", " \t\n ").q()).isNull();
  }

  @Test
  void setCodesAreShortLowercaseAlphanumericsAndBounded() {
    for (String code : List.of("M11", "m", "abcdefghi", "m-1", "m 1", ""))
      assertInvalidQuery(() -> cards("set", code), "Invalid set code.");
    assertThat(cards("set", "abcdefgh", "set", "ab").sets()).containsExactly("ab", "abcdefgh");

    List<String> codes = IntStream.range(0, 33).mapToObj(i -> "s%02d".formatted(i)).toList();
    assertThat(cards(repeated("set", codes.subList(0, 32))).sets()).hasSize(32);
    assertInvalidQuery(() -> cards(repeated("set", codes)), "Too many set filters.");
  }

  @Test
  void raritiesAreCanonicalAndTheBoundCountsRepeats() {
    assertThat(cards("rarity", "rare", "rarity", "common", "rarity", "rare").rarities())
        .containsExactly("common", "rare");
    assertThat(cards(repeated("rarity", List.copyOf(CatalogQuery.RARITIES))).rarities())
        .containsExactlyInAnyOrderElementsOf(CatalogQuery.RARITIES);
    assertInvalidQuery(() -> cards("rarity", "Rare"), "Invalid rarity.");
    assertInvalidQuery(
        () ->
            cards(
                repeated(
                    "rarity", List.of("rare", "rare", "rare", "rare", "rare", "rare", "rare"))),
        "Too many rarity filters.");
  }

  @Test
  void gameIsOneOfTheSupportedGames() {
    for (String game : CatalogQuery.GAMES) assertThat(cards("game", game).game()).isEqualTo(game);
    for (String game : List.of("Paper", "tabletop", ""))
      assertInvalidQuery(() -> cards("game", game), "Invalid game.");
  }

  @Test
  void colorIdentityIsColorlessOrDistinctColorsInWubrgOrder() {
    assertThat(cards("color_identity", "C").colorIdentity()).isEqualTo("C");
    assertThat(cards("color_identity", "GRBUW").colorIdentity()).isEqualTo("WUBRG");
    assertThat(cards("color_identity", "GW").colorIdentity()).isEqualTo("WG");
    for (String identity : List.of("", "c", "w", "CW", "WC", "X", "WW", "WUBRGW"))
      assertInvalidQuery(() -> cards("color_identity", identity), "Invalid color identity.");
  }

  @Test
  void colorsAreCanonicalAndBounded() {
    assertThat(cards("color", "G", "color", "U", "color", "C", "color", "U").colors())
        .containsExactly("U", "G", "C");
    assertInvalidQuery(() -> cards("color", "w"), "Invalid color.");
    assertInvalidQuery(
        () -> cards(repeated("color", List.of("W", "U", "B", "R", "G", "C", "W"))),
        "Too many color filters.");
  }

  @Test
  void typeIsOneOfTheSupportedCardTypes() {
    for (String type : CatalogQuery.TYPES) assertThat(cards("type", type).type()).isEqualTo(type);
    assertInvalidQuery(() -> cards("type", "tribal"), "Invalid card type.");
  }

  @Test
  void nameIsTheOnlyCardSort() {
    assertThat(cards("sort", "name_asc").sort()).isEqualTo("name_asc");
    assertInvalidQuery(() -> cards("sort", "name_desc"), "Invalid sort.");
  }

  @Test
  void limitIsADecimalBetweenOneAndOneHundred() {
    assertThat(cards("limit", "1").limit()).isEqualTo(1);
    assertThat(cards("limit", "100").limit()).isEqualTo(100);
    assertThat(cards("limit", "007").limit()).isEqualTo(7);
    for (String limit : List.of("0", "101", "999", "1000", "-1", "+5", "ten", "", " 5", "1.5"))
      assertInvalidQuery(() -> cards("limit", limit), "Limit must be between 1 and 100.");
  }

  @Test
  void snapshotIdsAreBoundedLowercaseSlugs() {
    String longest = "c" + "-".repeat(95);
    assertThat(cards("catalog_snapshot_id", longest).snapshot()).isEqualTo(longest);
    assertThat(cards("catalog_snapshot_id", "catalog-0f3a").snapshot()).isEqualTo("catalog-0f3a");
    for (String snapshot :
        List.of("", "-catalog", "Catalog", "catalog_1", "catalog/1", longest + "-"))
      assertInvalidQuery(() -> cards("catalog_snapshot_id", snapshot), "Invalid snapshot ID.");
  }

  @Test
  void onlyFilterListsMayRepeat() {
    for (String name :
        List.of(
            "q",
            "in",
            "game",
            "color_identity",
            "type",
            "sort",
            "limit",
            "catalog_snapshot_id",
            "cursor"))
      assertInvalidQuery(() -> cards(name, "x", name, "y"), "Duplicate scalar parameter.");
    // Unknown names are reported before duplicates.
    assertInvalidQuery(() -> cards("q", "a", "q", "b", "score", "1"), "Unknown query parameter.");
  }

  @Test
  void validateKeysTreatsAnEmptyScalarAsAmbiguousButAnEmptyListAsNoFilter() {
    assertInvalidQuery(
        () -> CatalogQuery.validateKeys(Map.of("q", List.of()), CatalogQuery.CARD_PARAMETERS),
        "Duplicate scalar parameter.");
    assertThatCode(
            () -> CatalogQuery.validateKeys(Map.of("set", List.of()), CatalogQuery.CARD_PARAMETERS))
        .doesNotThrowAnyException();
    assertInvalidQuery(
        () ->
            CatalogQuery.validateKeys(Map.of("q", List.of("bolt")), Set.of("catalog_snapshot_id")),
        "Unknown query parameter.");
  }

  private static void assertInvalidQuery(ThrowingCallable call, String detail) {
    assertThatThrownBy(call)
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> {
              assertThat(problem.status()).isEqualTo(400);
              assertThat(problem.code()).isEqualTo("invalid_query");
              assertThat(problem.getMessage()).isEqualTo(detail);
            });
  }
}
