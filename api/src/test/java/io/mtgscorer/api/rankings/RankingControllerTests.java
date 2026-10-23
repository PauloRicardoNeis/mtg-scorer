package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.mtgscorer.api.error.CatalogExceptionHandler;
import io.mtgscorer.api.error.CatalogProblem;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

@ExtendWith(MockitoExtension.class)
class RankingControllerTests {
  private static final String RUN = "scores-" + "a".repeat(64);

  @Mock private RankingService rankings;
  @Mock private CompareService compare;
  @Mock private CommanderService commanders;
  private MockMvc mvc;

  @BeforeEach
  void setUp() {
    mvc =
        MockMvcBuilders.standaloneSetup(new RankingController(rankings, compare, commanders))
            .setControllerAdvice(new CatalogExceptionHandler())
            .build();
  }

  @Test
  void theQueryStringIsParsedStrictlyAndThePageIsReturned() throws Exception {
    ArgumentCaptor<RankingQuery> query = ArgumentCaptor.forClass(RankingQuery.class);
    var run =
        new ScoreRunSummary(
            RUN,
            "topdeck",
            "Modern",
            LocalDate.of(2026, 3, 1),
            LocalDate.of(2026, 9, 1),
            OffsetDateTime.parse("2026-10-19T00:00:00Z"),
            "Data provided by TopDeck.gg (https://topdeck.gg)",
            12,
            249,
            231,
            67,
            0,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            List.of(),
            null);
    when(rankings.rankings(query.capture()))
        .thenReturn(
            new RankingPage(
                run,
                "max-ratio",
                "max_ratio",
                List.of(),
                null,
                0,
                0,
                25,
                "score",
                "desc",
                "all",
                new ViewCounts(0, 0, 0),
                null,
                0,
                List.of(),
                null,
                List.of()));

    mvc.perform(get("/api/v1/rankings").param("color", "R").param("color", "C"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.score_run.format_name").value("Modern"))
        .andExpect(jsonPath("$.method_id").value("max-ratio"));

    assertThat(query.getValue().colors()).containsExactly("R", "C");
  }

  @Test
  void anUnknownParameterIsAProblemBeforeTheServiceRuns() throws Exception {
    mvc.perform(get("/api/v1/rankings").param("grade", "A"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("invalid_query"));

    verifyNoInteractions(rankings);
  }

  @Test
  void unavailableRankingsKeepTheirStableCode() throws Exception {
    when(rankings.rankings(org.mockito.ArgumentMatchers.any()))
        .thenThrow(new CatalogProblem(503, "rankings_unavailable", "Not yet."));

    mvc.perform(get("/api/v1/rankings"))
        .andExpect(status().isServiceUnavailable())
        .andExpect(jsonPath("$.code").value("rankings_unavailable"));
  }

  @Test
  void theCompareQueryIsParsedStrictlyAndThePageIsReturned() throws Exception {
    ArgumentCaptor<CompareQuery> query = ArgumentCaptor.forClass(CompareQuery.class);
    when(compare.compare(query.capture()))
        .thenReturn(
            new ComparePage(
                "signature-score",
                List.of(new CompareFormat("Modern", RUN, 667, 2, 120)),
                List.of(new CompareFormat("Modern", RUN, 667, 2, 120)),
                List.of(new RankedFormat("Overall", "topdeck", RUN, 92506, null, 0)),
                null,
                0,
                0,
                50,
                "best",
                "desc",
                true,
                List.of()));

    mvc.perform(
            get("/api/v1/rankings/compare")
                .param("format", "Modern")
                .param("format", "Legacy")
                .param("method", "signature-score")
                .param("every", "true"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.method_id").value("signature-score"))
        .andExpect(jsonPath("$.formats[0].format_name").value("Modern"))
        .andExpect(jsonPath("$.formats[0].scored_cards").value(120))
        .andExpect(jsonPath("$.every").value(true));

    assertThat(query.getValue().formats()).containsExactly("Modern", "Legacy");
    assertThat(query.getValue().method()).isEqualTo("signature-score");
  }

  @Test
  void theCommanderQueryIsParsedStrictlyAndThePageIsReturned() throws Exception {
    ArgumentCaptor<CommanderQuery> query = ArgumentCaptor.forClass(CommanderQuery.class);
    when(commanders.commanders(query.capture()))
        .thenReturn(
            new CommanderPage(
                null,
                List.of(),
                null,
                0,
                0,
                25,
                "win_rate",
                "desc",
                null,
                0,
                List.of(),
                List.of()));

    mvc.perform(
            get("/api/v1/rankings/commanders")
                .param("format", "Duel Commander")
                .param("sort", "win_rate"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.sort").value("win_rate"));
    mvc.perform(get("/api/v1/rankings/commanders").param("method", "max-ratio"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("invalid_query"));

    assertThat(query.getValue().format()).isEqualTo("Duel Commander");
  }

  @Test
  void anUnknownCompareParameterIsAProblemBeforeTheServiceRuns() throws Exception {
    mvc.perform(get("/api/v1/rankings/compare").param("view", "risers"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("invalid_query"));
    mvc.perform(get("/api/v1/rankings/compare").param("method", "max-ratio"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("invalid_query"));

    verifyNoInteractions(compare);
  }
}
