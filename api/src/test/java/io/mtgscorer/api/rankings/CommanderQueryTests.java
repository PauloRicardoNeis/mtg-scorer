package io.mtgscorer.api.rankings;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class CommanderQueryTests {
  private static final String RUN = "scores-" + "a".repeat(64);

  @Test
  void anEmptyQueryRanksByDecksAndLeavesTheFormatToTheService() {
    var query = CommanderQuery.parse(Map.of());

    assertThat(query)
        .isEqualTo(
            new CommanderQuery(
                null, null, List.of(), 1, "decks", "desc", RankingQuery.DEFAULT_LIMIT, 0, null));
  }

  @Test
  void everyParameterIsParsedWithTheCardRankingsBounds() {
    var query =
        CommanderQuery.parse(
            Map.of(
                "format", List.of("Duel Commander"),
                "q", List.of(" ＫＩＮＮＡＮ "),
                "color", List.of("G", "U"),
                "min_decks", List.of("25"),
                "sort", List.of("movement"),
                "order", List.of("asc"),
                "limit", List.of("50"),
                "offset", List.of("25"),
                "score_run_id", List.of(RUN)));

    assertThat(query)
        .isEqualTo(
            new CommanderQuery(
                "Duel Commander", "kinnan", List.of("U", "G"), 25, "movement", "asc", 50, 25, RUN));
  }

  @Test
  void nameReadsAToZUnlessAnOrderIsGiven() {
    assertThat(CommanderQuery.parse(Map.of("sort", List.of("name"))).order()).isEqualTo("asc");
    assertThat(
            CommanderQuery.parse(Map.of("sort", List.of("name"), "order", List.of("desc"))).order())
        .isEqualTo("desc");
  }

  @Test
  void cardOnlyParametersAndSortsAreRejected() {
    for (var input :
        List.of(
            Map.of("method", List.of("max-ratio")),
            Map.of("type", List.of("creature")),
            Map.of("view", List.of("risers")),
            Map.of("sort", List.of("score")),
            Map.of("sort", List.of("price")),
            Map.of("order", List.of("up")),
            Map.of("limit", List.of("101")),
            Map.of("sort", List.of("decks", "name")),
            Map.of("min_decks", List.of("0")),
            Map.of("min_decks", List.of("100001")),
            Map.of("min_decks", List.of("ten")),
            Map.of("min_decks", List.of("5", "10"))))
      assertThatThrownBy(() -> CommanderQuery.parse(input))
          .isInstanceOf(CatalogProblem.class)
          .hasFieldOrPropertyWithValue("code", "invalid_query");
  }
}
