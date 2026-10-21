package io.mtgscorer.api.rankings;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class CompareQueryTests {
  @Test
  void anEmptyQueryComparesEveryFormatByTheBestScore() {
    var query = CompareQuery.parse(Map.of());

    assertThat(query.formats()).isEmpty();
    assertThat(query.method()).isEqualTo("constructed-score");
    assertThat(query.q()).isNull();
    assertThat(query.in()).isEqualTo("all");
    assertThat(query.colors()).isEmpty();
    assertThat(query.every()).isFalse();
    assertThat((query.sort() + " " + query.order())).isEqualTo("best desc");
    assertThat(query.sortFormat()).isNull();
    assertThat(query.limit()).isEqualTo(CompareQuery.DEFAULT_LIMIT);
    assertThat(query.offset()).isZero();
  }

  @Test
  void everyParameterIsParsedAndNormalized() {
    var query =
        CompareQuery.parse(
            Map.of(
                "format", List.of("Modern", "Old School 93/94", "Modern"),
                "method", List.of("signature-score"),
                "q", List.of(" ＢＯＬＴ "),
                "in", List.of("type"),
                "color", List.of("C", "R"),
                "every", List.of("true"),
                "sort", List.of("Old School 93/94:win_rate"),
                "order", List.of("asc"),
                "limit", List.of("200"),
                "offset", List.of("50")));

    assertThat(query)
        .isEqualTo(
            new CompareQuery(
                List.of("Modern", "Old School 93/94"),
                "signature-score",
                "bolt",
                "type",
                List.of("R", "C"),
                true,
                "Old School 93/94:win_rate",
                "Old School 93/94",
                "win_rate",
                "asc",
                200,
                50));
  }

  @Test
  void nameSortsAToZAndTheOtherSortsHighestFirst() {
    assertThat(CompareQuery.parse(Map.of("sort", List.of("name"))).order()).isEqualTo("asc");
    assertThat(CompareQuery.parse(Map.of("sort", List.of("count"))).order()).isEqualTo("desc");
    assertThat(CompareQuery.parse(Map.of("every", List.of("false"))).every()).isFalse();
  }

  @Test
  void blankSearchTextIsNoSearch() {
    assertThat(CompareQuery.parse(Map.of("q", List.of("   "))).q()).isNull();
  }

  @Test
  void rejectsEveryOutOfBoundsOrUnknownValue() {
    for (var input :
        List.<Map<String, List<String>>>of(
            Map.of("grade", List.of("A")),
            Map.of("q", List.of("bolt", "fire")),
            Map.of("format", List.of(" Modern")),
            Map.of(
                "format",
                List.of(
                    "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "B1", "B2", "B3", "B4")),
            Map.of("q", List.of("x".repeat(101))),
            Map.of("in", List.of("name", "text")),
            Map.of("in", List.of("oracle")),
            // Only graded percentiles compare across formats.
            Map.of("method", List.of("max-ratio")),
            Map.of("method", List.of("Signature-Score")),
            Map.of("method", List.of("")),
            Map.of("method", List.of("constructed-score", "signature-score")),
            Map.of("color", List.of("X")),
            Map.of("color", List.of("W", "U", "B", "R", "G", "C", "W")),
            Map.of("every", List.of("yes")),
            Map.of("sort", List.of("grade")),
            Map.of("sort", List.of(":grade")),
            Map.of("sort", List.of("Modern:elo")),
            Map.of("sort", List.of(" Modern:grade")),
            Map.of("order", List.of("up")),
            Map.of("limit", List.of("0")),
            Map.of("limit", List.of("201")),
            Map.of("limit", List.of("ten")),
            Map.of("offset", List.of("10001")))) {
      assertThatThrownBy(() -> CompareQuery.parse(input))
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
