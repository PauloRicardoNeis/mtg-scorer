package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CompareServiceTests {
  private static final String MODERN = "scores-" + "a".repeat(64);
  private static final String LEGACY = "scores-" + "b".repeat(64);
  private static final List<CompareFormat> FORMATS =
      List.of(
          new CompareFormat("Legacy", LEGACY, 2936, 2),
          new CompareFormat("Modern", MODERN, 667, 2));

  @Mock private CompareRepository repository;
  @Mock private RankingRepository rankings;

  private CompareService service() {
    return new CompareService(repository, rankings);
  }

  private static CompareQuery query(String... pairs) {
    Map<String, List<String>> input = new HashMap<>();
    for (int index = 0; index < pairs.length; index += 2)
      input.computeIfAbsent(pairs[index], key -> new java.util.ArrayList<>()).add(pairs[index + 1]);
    return CompareQuery.parse(input);
  }

  @Test
  void theComparedRunsAreCountedAndPaged() {
    var query = query("format", "Modern", "format", "Legacy", "sort", "Modern:share");
    when(repository.formats()).thenReturn(FORMATS);
    when(repository.count(List.of(LEGACY, MODERN), query)).thenReturn(1200L);
    when(repository.page(List.of(LEGACY, MODERN), query)).thenReturn(List.of());
    when(rankings.activeCatalog()).thenReturn("catalog-a");

    var page = service().compare(query);

    assertThat(page.formats()).isEqualTo(FORMATS);
    assertThat(page.available()).isEqualTo(FORMATS);
    assertThat(page.catalog_snapshot_id()).isEqualTo("catalog-a");
    assertThat(page.total()).isEqualTo(1200);
    assertThat((page.sort() + " " + page.order())).isEqualTo("Modern:share desc");
    assertThat(page.every()).isFalse();
    assertThat((page.offset() + "/" + page.limit())).isEqualTo("0/50");
  }

  @Test
  void aColumnOfAFormatThatIsNotComparedFallsBackToTheBestFormat() {
    when(repository.formats()).thenReturn(FORMATS);
    ArgumentCaptor<CompareQuery> used = ArgumentCaptor.forClass(CompareQuery.class);
    when(repository.count(any(), used.capture())).thenReturn(0L);

    var page = service().compare(query("sort", "Vintage:grade", "order", "asc", "every", "true"));

    assertThat((page.sort() + " " + page.order())).isEqualTo("best desc");
    assertThat(used.getValue().sortFormat()).isNull();
    assertThat(used.getValue().every()).isTrue();
  }

  @Test
  void theBestFormatOrderNeedsNoComparedColumn() {
    var query = query();
    when(repository.formats()).thenReturn(FORMATS);

    assertThat(service().compare(query).sort()).isEqualTo("best");
    verify(repository).page(List.of(LEGACY, MODERN), query);
  }

  @Test
  void onlyTheChosenFormatsAreCompared() {
    when(repository.formats()).thenReturn(FORMATS);

    var page = service().compare(query("format", "Modern", "format", "Pioneer"));

    assertThat(page.formats()).extracting(CompareFormat::format_name).containsExactly("Modern");
    assertThat(page.available()).hasSize(2);
    verify(repository).page(List.of(MODERN), query("format", "Modern", "format", "Pioneer"));
  }

  @Test
  void withoutAConstructedScoreThereIsNothingToCompare() {
    when(repository.formats()).thenReturn(FORMATS);

    assertThatThrownBy(() -> service().compare(query("format", "Vintage")))
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> {
              assertThat(problem.status()).isEqualTo(503);
              assertThat(problem.code()).isEqualTo("rankings_unavailable");
            });
    verify(repository, never()).page(any(), any());
  }
}
