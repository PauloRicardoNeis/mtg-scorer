package io.mtgscorer.api.catalog;

import static io.mtgscorer.api.catalog.CatalogModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.mtgscorer.api.error.CatalogExceptionHandler;
import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.CannotGetJdbcConnectionException;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

@ExtendWith(MockitoExtension.class)
class CatalogControllerTests {
  private static final String CARD = "00000000-0000-4000-8000-000000000001";
  private static final UUID CARD_ID = UUID.fromString(CARD);

  @Mock private CatalogService catalog;
  private MockMvc mvc;

  @BeforeEach
  void setUp() {
    mvc =
        MockMvcBuilders.standaloneSetup(new CatalogController(catalog))
            .setControllerAdvice(new CatalogExceptionHandler())
            .build();
  }

  @Test
  void searchParsesRepeatedFiltersFromTheQueryString() throws Exception {
    ArgumentCaptor<CatalogQuery> query = ArgumentCaptor.forClass(CatalogQuery.class);
    when(catalog.search(query.capture()))
        .thenReturn(
            new CardPage(
                "catalog-a",
                List.of(
                    new CardSummary(
                        CARD_ID,
                        "Lightning Bolt",
                        "normal",
                        "{R}",
                        "Instant",
                        List.of("R"),
                        2,
                        null)),
                "next"));

    mvc.perform(
            get("/api/v1/cards")
                .queryParam("q", "Lightning  BOLT")
                .queryParam("set", "m11", "2x2")
                .queryParam("limit", "5"))
        .andExpect(status().isOk())
        .andExpect(content().contentType("application/json"))
        .andExpect(jsonPath("$.catalog_snapshot_id").value("catalog-a"))
        .andExpect(jsonPath("$.items[0].oracle_id").value(CARD))
        .andExpect(jsonPath("$.items[0].eligible_printing_count").value(2))
        .andExpect(jsonPath("$.next_cursor").value("next"));

    assertThat(query.getValue().q()).isEqualTo("lightning bolt");
    assertThat(query.getValue().sets()).containsExactly("2x2", "m11");
    assertThat(query.getValue().limit()).isEqualTo(5);
    assertThat(query.getValue().sort()).isEqualTo("name_asc");
  }

  @Test
  void invalidSearchesAreProblemDetailsWithoutReachingTheService() throws Exception {
    mvc.perform(get("/api/v1/cards").queryParam("score", "100"))
        .andExpect(status().isBadRequest())
        .andExpect(content().contentType("application/problem+json"))
        .andExpect(jsonPath("$.status").value(400))
        .andExpect(jsonPath("$.code").value("invalid_query"))
        .andExpect(jsonPath("$.detail").value("Unknown query parameter."))
        .andExpect(jsonPath("$.instance").value("/api/v1/cards"))
        .andExpect(jsonPath("$.request_id").isNotEmpty());
    mvc.perform(get("/api/v1/cards").queryParam("limit", "1", "2"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.detail").value("Duplicate scalar parameter."));

    verifyNoInteractions(catalog);
  }

  @Test
  void detailAcceptsOnlyTheSnapshotParameter() throws Exception {
    when(catalog.detail(eq(CARD), any()))
        .thenReturn(
            new CardDetail(
                "catalog-a",
                CARD_ID,
                "Lightning Bolt",
                "normal",
                "{R}",
                1.0,
                "Deal 3.",
                "Instant",
                List.of("R"),
                List.of("R"),
                List.of(new Face(0, "Lightning Bolt", "{R}", "Deal 3.", "Instant", List.of("R")))));

    mvc.perform(
            get("/api/v1/cards/{oracle_id}", CARD).queryParam("catalog_snapshot_id", "catalog-a"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.faces[0].name").value("Lightning Bolt"));
    mvc.perform(get("/api/v1/cards/{oracle_id}", CARD)).andExpect(status().isOk());
    verify(catalog).detail(CARD, "catalog-a");
    verify(catalog).detail(CARD, null);

    mvc.perform(get("/api/v1/cards/{oracle_id}", CARD).queryParam("q", "bolt"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.detail").value("Unknown query parameter."));
    mvc.perform(
            get("/api/v1/cards/{oracle_id}", CARD)
                .queryParam("catalog_snapshot_id", "catalog-a", "catalog-b"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.detail").value("Duplicate scalar parameter."));
  }

  @Test
  void printingsParseThePoolFiltersWithTheirOwnSort() throws Exception {
    ArgumentCaptor<CatalogQuery> query = ArgumentCaptor.forClass(CatalogQuery.class);
    when(catalog.printings(eq(CARD), query.capture()))
        .thenReturn(new PrintingPage("catalog-a", CARD_ID, List.of(), null));

    mvc.perform(
            get("/api/v1/cards/{oracle_id}/printings", CARD)
                .queryParam("set", "m11")
                .queryParam("game", "arena"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.oracle_id").value(CARD))
        .andExpect(jsonPath("$.items").isEmpty());
    assertThat(query.getValue().sets()).containsExactly("m11");
    assertThat(query.getValue().game()).isEqualTo("arena");
    assertThat(query.getValue().sort()).isEqualTo("scryfall_id_asc");

    mvc.perform(get("/api/v1/cards/{oracle_id}/printings", CARD).queryParam("type", "land"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("invalid_query"));
  }

  @Test
  void serviceProblemsAndDatabaseFailuresBecomeProblemDetails() throws Exception {
    when(catalog.detail(CARD, null))
        .thenThrow(new CatalogProblem(404, "card_not_found", "Card not found in this catalog."));
    when(catalog.search(any()))
        .thenThrow(new CannotGetJdbcConnectionException("sensitive connection detail"));

    mvc.perform(get("/api/v1/cards/{oracle_id}", CARD))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("card_not_found"))
        .andExpect(jsonPath("$.instance").value("/api/v1/cards/" + CARD));
    String body =
        mvc.perform(get("/api/v1/cards"))
            .andExpect(status().isServiceUnavailable())
            .andExpect(content().contentType("application/problem+json"))
            .andExpect(jsonPath("$.code").value("catalog_unavailable"))
            .andReturn()
            .getResponse()
            .getContentAsString();
    assertThat(body).doesNotContain("sensitive");
  }
}
