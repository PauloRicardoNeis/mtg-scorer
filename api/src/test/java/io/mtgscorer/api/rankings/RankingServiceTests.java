package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.error.CatalogProblem;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RankingServiceTests {
  private static final String MODERN = "scores-" + "a".repeat(64);
  private static final String PIONEER = "scores-" + "b".repeat(64);
  private static final ScoreMethod VOLUME =
      new ScoreMethod(
          "max-ratio", "max-ratio-v1", "Relative volume", "Count ÷ max.", List.of("max_ratio"));
  private static final ScoreMethod CONSTRUCTED =
      new ScoreMethod(
          "constructed-score",
          "constructed-score-v1",
          "Constructed score",
          "Blend.",
          List.of("score"));
  private static final ScoreMethod FOUNDATION =
      new ScoreMethod(
          "foundation", "foundation-v2", "Staple", "Weighted.", List.of("staple", "evidence"));
  private static final List<RankedFormat> FORMATS =
      List.of(
          new RankedFormat("Modern", "topdeck", MODERN, 231, 2),
          new RankedFormat("Pioneer", "topdeck", PIONEER, 120, 2));

  @Mock private RankingRepository repository;

  private RankingService service() {
    return new RankingService(repository);
  }

  private static ScoreRunSummary run(String id, String format, ScoreMethod... methods) {
    return new ScoreRunSummary(
        id,
        "topdeck",
        format,
        LocalDate.of(2026, 3, 1),
        LocalDate.of(2026, 9, 1),
        OffsetDateTime.parse("2026-10-19T00:00:00Z"),
        "Data provided by TopDeck.gg (https://topdeck.gg)",
        12,
        249,
        231,
        67,
        608,
        1798,
        2,
        0.499,
        0.2479,
        LocalDate.of(2025, 9, 6),
        30,
        List.of(0, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0),
        List.of(methods));
  }

  private static RankedCard card() {
    return new RankedCard(
        1,
        2,
        UUID.fromString("4457ed35-7c10-48c8-9776-456485fdf070"),
        "Lightning Bolt",
        100.0,
        20,
        5,
        3,
        10,
        "Burn",
        8,
        20,
        0.55,
        0.05,
        0.04,
        120,
        1.2,
        0.01,
        4.0,
        List.of(0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0),
        List.of(new ArchetypeShare("Burn", 8, List.of("R"))),
        2,
        "{R}",
        "Instant",
        List.of("R"),
        null);
  }

  private static RankingQuery query(String... pairs) {
    Map<String, List<String>> input = new java.util.HashMap<>();
    for (int index = 0; index < pairs.length; index += 2)
      input.put(pairs[index], List.of(pairs[index + 1]));
    return RankingQuery.parse(input);
  }

  @Test
  void withoutAFormatTheActiveModernRunIsRankedByTheConstructedScore() {
    String previous = "scores-" + "d".repeat(64);
    var query = query("limit", "10");
    var run = run(MODERN, "Modern", CONSTRUCTED, FOUNDATION, VOLUME);
    var counts = new ViewCounts(608, 40, 35);
    when(repository.activeFormats()).thenReturn(FORMATS);
    when(repository.run(MODERN)).thenReturn(Optional.of(run));
    when(repository.previousRun(run, "constructed-score")).thenReturn(previous);
    when(repository.count(MODERN, previous, "constructed-score", "score", query)).thenReturn(608L);
    when(repository.viewCounts(MODERN, previous, "constructed-score", "score", query))
        .thenReturn(counts);
    when(repository.maxDeckCount(MODERN)).thenReturn(91);
    var windows =
        List.of(
            new RunWindow(
                MODERN, "topdeck", LocalDate.of(2026, 3, 1), LocalDate.of(2026, 9, 1), 231, true));
    when(repository.windows("Modern")).thenReturn(windows);
    when(repository.page(MODERN, previous, "constructed-score", "score", query))
        .thenReturn(List.of(card()));
    when(repository.activeCatalog()).thenReturn("catalog-a");

    var page = service().rankings(query);

    assertThat(page.score_run().score_run_id()).isEqualTo(MODERN);
    assertThat(page.method_id()).isEqualTo("constructed-score");
    assertThat(page.output()).isEqualTo("score");
    assertThat(page.previous_score_run_id()).isEqualTo(previous);
    assertThat(page.view_counts()).isEqualTo(counts);
    assertThat(page.max_deck_count()).isEqualTo(91);
    assertThat(page.windows()).isEqualTo(windows);
    assertThat((page.sort() + " " + page.order() + " " + page.view())).isEqualTo("score desc all");
    assertThat(page.formats()).isEqualTo(FORMATS);
    assertThat(page.catalog_snapshot_id()).isEqualTo("catalog-a");
    assertThat(page.total()).isEqualTo(608);
    assertThat(page.offset()).isZero();
    assertThat(page.limit()).isEqualTo(10);
    assertThat(page.items()).containsExactly(card());
  }

  @Test
  void anExplicitFormatAndMethodSelectThatRunAndTheMethodsFirstOutput() {
    var query = query("format", "Pioneer", "method", "foundation");
    when(repository.activeFormats()).thenReturn(FORMATS);
    when(repository.run(PIONEER))
        .thenReturn(Optional.of(run(PIONEER, "Pioneer", FOUNDATION, VOLUME)));

    var page = service().rankings(query);

    assertThat(page.method_id()).isEqualTo("foundation");
    assertThat(page.output()).isEqualTo("staple");
    verify(repository).count(PIONEER, null, "foundation", "staple", query);
  }

  @Test
  void aFormatWithoutAnActiveRunIsUnavailable() {
    when(repository.activeFormats()).thenReturn(FORMATS);

    assertThatThrownBy(() -> service().rankings(query("format", "Vintage")))
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> {
              assertThat(problem.status()).isEqualTo(503);
              assertThat(problem.code()).isEqualTo("rankings_unavailable");
            });
    verify(repository, never()).run(anyString());
  }

  @Test
  void aPinnedRunIsUsedEvenAfterTheActiveRunMovesOn() {
    String older = "scores-" + "c".repeat(64);
    var query = query("score_run_id", older);
    when(repository.activeFormats()).thenReturn(FORMATS);
    when(repository.run(older)).thenReturn(Optional.of(run(older, "Modern", VOLUME)));

    assertThat(service().rankings(query).score_run().score_run_id()).isEqualTo(older);
  }

  @Test
  void aPinnedRunMayRepeatItsOwnFormat() {
    var query = query("score_run_id", PIONEER, "format", "Pioneer");
    when(repository.activeFormats()).thenReturn(FORMATS);
    when(repository.run(PIONEER)).thenReturn(Optional.of(run(PIONEER, "Pioneer", VOLUME)));

    assertThat(service().rankings(query).score_run().format_name()).isEqualTo("Pioneer");
  }

  @Test
  void aPinnedRunForAnotherFormatIsRejected() {
    when(repository.activeFormats()).thenReturn(FORMATS);
    when(repository.run(PIONEER)).thenReturn(Optional.of(run(PIONEER, "Pioneer", VOLUME)));

    assertThatThrownBy(() -> service().rankings(query("score_run_id", PIONEER, "format", "Modern")))
        .isInstanceOfSatisfying(
            CatalogProblem.class, problem -> assertThat(problem.status()).isEqualTo(400));
  }

  @Test
  void anUnknownPinnedRunIsNotFound() {
    when(repository.activeFormats()).thenReturn(FORMATS);
    when(repository.run(MODERN)).thenReturn(Optional.empty());

    assertThatThrownBy(() -> service().rankings(query("score_run_id", MODERN)))
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> {
              assertThat(problem.status()).isEqualTo(404);
              assertThat(problem.code()).isEqualTo("score_run_not_found");
            });
  }

  @Test
  void withoutTheConstructedScoreTheDefaultFallsBackToMaxRatio() {
    when(repository.activeFormats()).thenReturn(FORMATS);
    when(repository.run(MODERN)).thenReturn(Optional.of(run(MODERN, "Modern", FOUNDATION, VOLUME)));

    assertThat(service().rankings(query()).method_id()).isEqualTo("max-ratio");
  }

  @Test
  void withoutAPreferredMethodTheDefaultFallsBackToTheRunsFirstMethod() {
    when(repository.activeFormats()).thenReturn(FORMATS);
    when(repository.run(MODERN)).thenReturn(Optional.of(run(MODERN, "Modern", FOUNDATION)));

    assertThat(service().rankings(query()).method_id()).isEqualTo("foundation");
  }

  @Test
  void anExplicitMethodTheRunLacksIsRejected() {
    when(repository.activeFormats()).thenReturn(FORMATS);
    when(repository.run(MODERN)).thenReturn(Optional.of(run(MODERN, "Modern", VOLUME)));

    assertThatThrownBy(() -> service().rankings(query("method", "elo")))
        .isInstanceOfSatisfying(
            CatalogProblem.class, problem -> assertThat(problem.status()).isEqualTo(400));
    verify(repository, never()).count(anyString(), any(), anyString(), anyString(), any());
  }
}
