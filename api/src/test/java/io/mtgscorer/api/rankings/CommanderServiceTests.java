package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.error.CatalogProblem;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CommanderServiceTests {
  private static final String EDH = "scores-" + "e".repeat(64);
  private static final String MODERN = "scores-" + "a".repeat(64);
  private static final List<RankedFormat> FORMATS =
      List.of(
          new RankedFormat("EDH", "topdeck", EDH, 83339, 4, 1599),
          new RankedFormat("Modern", "topdeck", MODERN, 667, 2, 0));

  @Mock private CommanderRepository repository;
  @Mock private RankingRepository rankings;

  private CommanderService service() {
    return new CommanderService(repository, rankings);
  }

  private static ScoreRunSummary run(String id, String format) {
    return new ScoreRunSummary(
        id,
        "topdeck",
        format,
        LocalDate.of(2025, 10, 1),
        LocalDate.of(2026, 10, 1),
        OffsetDateTime.parse("2026-10-20T00:00:00Z"),
        "TopDeck",
        1200,
        90000,
        83339,
        9000,
        20534,
        null,
        4,
        null,
        null,
        null,
        null,
        null,
        List.of(),
        null);
  }

  @Test
  void withoutAFormatTheCommanderFormatIsRanked() {
    var query = CommanderQuery.parse(Map.of());
    var edh = run(EDH, "EDH");
    when(rankings.activeFormats()).thenReturn(FORMATS);
    when(rankings.run(EDH)).thenReturn(Optional.of(edh));
    when(rankings.activeCatalog()).thenReturn("catalog-a");
    when(rankings.windows("EDH")).thenReturn(List.of());
    when(repository.previousRun(edh)).thenReturn(null);
    when(repository.count(EDH, null, query)).thenReturn(1599L);
    when(repository.maxDeckCount(EDH)).thenReturn(4012);
    when(repository.page(EDH, null, query)).thenReturn(List.of());

    var page = service().commanders(query);

    assertThat(page.score_run().format_name()).isEqualTo("EDH");
    assertThat(page.total()).isEqualTo(1599);
    assertThat(page.max_deck_count()).isEqualTo(4012);
    assertThat(page.sort()).isEqualTo("decks");
    assertThat(page.formats()).isEqualTo(FORMATS);
  }

  @Test
  void aFormatWithoutCommandersListsNoneInsteadOfFailing() {
    var query = CommanderQuery.parse(Map.of("format", List.of("Modern")));
    var modern = run(MODERN, "Modern");
    when(rankings.activeFormats()).thenReturn(FORMATS);
    when(rankings.run(MODERN)).thenReturn(Optional.of(modern));
    when(repository.count(MODERN, null, query)).thenReturn(0L);
    when(repository.page(MODERN, null, query)).thenReturn(List.of());

    var page = service().commanders(query);

    assertThat(page.total()).isZero();
    assertThat(page.items()).isEmpty();
  }

  @Test
  void aPinnedRunMustBelongToTheFormat() {
    when(rankings.activeFormats()).thenReturn(FORMATS);
    when(rankings.run(MODERN)).thenReturn(Optional.of(run(MODERN, "Modern")));
    var query =
        CommanderQuery.parse(Map.of("format", List.of("EDH"), "score_run_id", List.of(MODERN)));

    assertThatThrownBy(() -> service().commanders(query))
        .isInstanceOf(CatalogProblem.class)
        .hasFieldOrPropertyWithValue("code", "invalid_query");
  }

  @Test
  void aFormatWithoutAnActiveRunIsUnavailable() {
    when(rankings.activeFormats()).thenReturn(FORMATS);
    var query = CommanderQuery.parse(Map.of("format", List.of("Oathbreaker")));

    assertThatThrownBy(() -> service().commanders(query))
        .isInstanceOf(CatalogProblem.class)
        .hasFieldOrPropertyWithValue("code", "rankings_unavailable");
  }
}
