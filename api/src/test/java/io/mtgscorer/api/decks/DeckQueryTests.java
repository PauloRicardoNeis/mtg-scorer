package io.mtgscorer.api.decks;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class DeckQueryTests {
  private static final String RUN = "scores-" + "a".repeat(64);

  @Test
  void withoutParametersTheFirstPageOfTheDefaultFormatIsAsked() {
    assertThat(DeckQuery.parse(Map.of()))
        .isEqualTo(new DeckQuery(null, null, DeckQuery.DEFAULT_LIMIT, 0));
  }

  @Test
  void formatRunAndPagingAreKept() {
    var query =
        DeckQuery.parse(
            Map.of(
                "format", List.of("Old School 93/94"),
                "score_run_id", List.of(RUN),
                "limit", List.of("100"),
                "offset", List.of("83339")));

    assertThat(query).isEqualTo(new DeckQuery("Old School 93/94", RUN, 100, 83339));
  }

  @ParameterizedTest
  @CsvSource({
    "format, -Modern",
    "score_run_id, scores-abc",
    "limit, 0",
    "limit, 101",
    "limit, ten",
    "offset, 1000001",
    "offset, -1",
    "cursor, abc"
  })
  void outOfBoundsValuesAreQueryProblems(String key, String value) {
    assertThatThrownBy(() -> DeckQuery.parse(Map.of(key, List.of(value))))
        .isInstanceOf(CatalogProblem.class)
        .hasFieldOrPropertyWithValue("code", "invalid_query");
  }
}
