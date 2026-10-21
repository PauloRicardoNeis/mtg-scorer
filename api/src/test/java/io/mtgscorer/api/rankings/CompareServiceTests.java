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
  private static final String PAUPER = "scores-" + "c".repeat(64);
  private static final List<CompareFormat> FORMATS =
      List.of(
          new CompareFormat("Legacy", LEGACY, 2936, 2, 300),
          new CompareFormat("Modern", MODERN, 667, 2, 200));

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
    when(repository.formats("constructed-score")).thenReturn(FORMATS);
    when(repository.count(List.of(LEGACY, MODERN), query)).thenReturn(1200L);
    when(repository.page(List.of(LEGACY, MODERN), query)).thenReturn(List.of());
    when(rankings.activeCatalog()).thenReturn("catalog-a");
    var overall = List.of(new RankedFormat("Overall", "topdeck", MODERN, 92506, null, 0));
    when(rankings.activeFormats()).thenReturn(overall);

    var page = service().compare(query);

    assertThat(page.method_id()).isEqualTo("constructed-score");
    assertThat(page.formats()).isEqualTo(FORMATS);
    assertThat(page.available()).isEqualTo(FORMATS);
    // The format bar lists every active run, including those the comparison leaves out.
    assertThat(page.active_formats()).isEqualTo(overall);
    assertThat(page.catalog_snapshot_id()).isEqualTo("catalog-a");
    assertThat(page.total()).isEqualTo(1200);
    assertThat((page.sort() + " " + page.order())).isEqualTo("Modern:share desc");
    assertThat(page.every()).isFalse();
    assertThat((page.offset() + "/" + page.limit())).isEqualTo("0/50");
  }

  @Test
  void aColumnOfAFormatThatIsNotComparedFallsBackToTheBestFormat() {
    when(repository.formats("constructed-score")).thenReturn(FORMATS);
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
    when(repository.formats("constructed-score")).thenReturn(FORMATS);

    assertThat(service().compare(query).sort()).isEqualTo("best");
    verify(repository).page(List.of(LEGACY, MODERN), query);
  }

  @Test
  void onlyTheChosenFormatsAreCompared() {
    when(repository.formats("constructed-score")).thenReturn(FORMATS);

    var page = service().compare(query("format", "Modern", "format", "Pioneer"));

    assertThat(page.formats()).extracting(CompareFormat::format_name).containsExactly("Modern");
    assertThat(page.available()).hasSize(2);
    verify(repository).page(List.of(MODERN), query("format", "Modern", "format", "Pioneer"));
  }

  @Test
  void aFormatTheMethodScoredNoCardInIsAvailableButNotCompared() {
    // Pauper has no archetype labels, so the signature score could not rank its cards.
    var unlabelled = new CompareFormat("Pauper", PAUPER, 900, 2, 0);
    List<CompareFormat> signature = List.of(FORMATS.getFirst(), FORMATS.getLast(), unlabelled);
    when(repository.formats("signature-score")).thenReturn(signature);
    var query = query("method", "signature-score");

    var page = service().compare(query);

    assertThat(page.method_id()).isEqualTo("signature-score");
    assertThat(page.formats()).isEqualTo(FORMATS);
    assertThat(page.available()).isEqualTo(signature);
    verify(repository).page(List.of(LEGACY, MODERN), query);
    assertThatThrownBy(
            () -> service().compare(query("method", "signature-score", "format", "Pauper")))
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> {
              assertThat(problem.status()).isEqualTo(503);
              assertThat(problem.getMessage()).contains("signature-score");
            });
  }

  @Test
  void aSortFallbackKeepsTheChosenMethod() {
    when(repository.formats("signature-score")).thenReturn(FORMATS);
    ArgumentCaptor<CompareQuery> used = ArgumentCaptor.forClass(CompareQuery.class);
    when(repository.count(any(), used.capture())).thenReturn(0L);

    service().compare(query("method", "signature-score", "sort", "Vintage:share"));

    assertThat(used.getValue().method()).isEqualTo("signature-score");
    assertThat(used.getValue().sort()).isEqualTo("best");
  }

  @Test
  void withoutAConstructedScoreThereIsNothingToCompare() {
    when(repository.formats("constructed-score")).thenReturn(FORMATS);

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
