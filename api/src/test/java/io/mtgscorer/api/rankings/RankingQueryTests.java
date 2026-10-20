package io.mtgscorer.api.rankings;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class RankingQueryTests {
  private static final String RUN = "scores-" + "a".repeat(64);

  @Test
  void anEmptyQueryLeavesFormatAndMethodToTheServiceAndUsesDefaults() {
    var query = RankingQuery.parse(Map.of());

    assertThat(query.format()).isNull();
    assertThat(query.method()).isNull();
    assertThat(query.q()).isNull();
    assertThat(query.type()).isNull();
    assertThat(query.colors()).isEmpty();
    assertThat(query.sort()).isEqualTo("score");
    assertThat(query.order()).isEqualTo("desc");
    assertThat(query.view()).isEqualTo("all");
    assertThat(query.limit()).isEqualTo(RankingQuery.DEFAULT_LIMIT);
    assertThat(query.offset()).isZero();
    assertThat(query.scoreRun()).isNull();
  }

  @Test
  void everyParameterIsParsedAndNormalized() {
    var query =
        RankingQuery.parse(
            Map.of(
                "format", List.of("Modern"),
                "method", List.of("max-ratio"),
                "q", List.of(" ＢＯＬＴ "),
                "type", List.of("instant"),
                "color", List.of("C", "R", "W", "R"),
                "sort", List.of("top_cuts"),
                "order", List.of("asc"),
                "limit", List.of("100"),
                "offset", List.of("10000"),
                "score_run_id", List.of(RUN)));

    assertThat(query)
        .isEqualTo(
            new RankingQuery(
                "Modern",
                "max-ratio",
                "bolt",
                "instant",
                List.of("W", "R", "C"),
                "top_cuts",
                "asc",
                "all",
                100,
                10000,
                RUN));
  }

  @Test
  void nameSortsAToZByDefaultAndEveryOtherSortHighestFirst() {
    assertThat(RankingQuery.parse(Map.of("sort", List.of("name"))).order()).isEqualTo("asc");
    for (String sort : List.of("win_rate", "top_cut_lift", "trend", "movement"))
      assertThat(RankingQuery.parse(Map.of("sort", List.of(sort))).order()).isEqualTo("desc");
  }

  @Test
  void aViewKeepsRisersOrFallers() {
    assertThat(RankingQuery.parse(Map.of("view", List.of("fallers"))).view()).isEqualTo("fallers");
  }

  @Test
  void blankSearchTextIsNoSearch() {
    assertThat(RankingQuery.parse(Map.of("q", List.of("   "))).q()).isNull();
  }

  @Test
  void formatsMayContainTopDecksSpacesSlashesAndDigits() {
    for (String format : List.of("Pauper EDH", "Old School 93/94", "7pt Highlander"))
      assertThat(RankingQuery.parse(Map.of("format", List.of(format))).format()).isEqualTo(format);
  }

  @Test
  void rejectsEveryOutOfBoundsOrUnknownValue() {
    for (var input :
        List.<Map<String, List<String>>>of(
            Map.of("grade", List.of("A")),
            Map.of("format", List.of("Modern", "Legacy")),
            Map.of("format", List.of(" Modern")),
            Map.of("format", List.of("Modern;drop")),
            Map.of("format", List.of("M".repeat(41))),
            Map.of("method", List.of("Max-Ratio")),
            Map.of("q", List.of("x".repeat(101))),
            Map.of("type", List.of("battle")),
            Map.of("color", List.of("X")),
            Map.of("color", List.of("W", "U", "B", "R", "G", "C", "W")),
            Map.of("sort", List.of("grade")),
            Map.of("order", List.of("up")),
            Map.of("view", List.of("new")),
            Map.of("limit", List.of("0")),
            Map.of("limit", List.of("101")),
            Map.of("limit", List.of("ten")),
            Map.of("offset", List.of("-1")),
            Map.of("offset", List.of("10001")),
            Map.of("offset", List.of("123456")),
            Map.of("score_run_id", List.of("scores-short")))) {
      assertThatThrownBy(() -> RankingQuery.parse(input))
          .as(input.toString())
          .isInstanceOfSatisfying(
              CatalogProblem.class,
              problem -> {
                assertThat(problem.status()).isEqualTo(400);
                assertThat(problem.code()).isEqualTo("invalid_query");
              });
    }
  }
}
