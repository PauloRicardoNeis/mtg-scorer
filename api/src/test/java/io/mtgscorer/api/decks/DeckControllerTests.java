package io.mtgscorer.api.decks;

import static io.mtgscorer.api.decks.DeckModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.mtgscorer.api.error.CatalogExceptionHandler;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

@ExtendWith(MockitoExtension.class)
class DeckControllerTests {
  private static final String BOLT = "4457ed35-7c10-48c8-9776-456485fdf070";

  @Mock private DeckService decks;
  private MockMvc mvc;

  @BeforeEach
  void setUp() {
    mvc =
        MockMvcBuilders.standaloneSetup(new DeckController(decks))
            .setControllerAdvice(new CatalogExceptionHandler())
            .build();
  }

  @Test
  void theQueryStringIsParsedStrictlyAndThePageIsReturned() throws Exception {
    ArgumentCaptor<DeckQuery> query = ArgumentCaptor.forClass(DeckQuery.class);
    when(decks.decks(eq(BOLT), query.capture()))
        .thenReturn(new CardDeckPage(UUID.fromString(BOLT), List.of(), null, 0, 20, 10, List.of()));

    mvc.perform(get("/api/v1/cards/" + BOLT + "/decks?format=Legacy&offset=20&limit=10"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.oracle_id").value(BOLT))
        .andExpect(jsonPath("$.run").isEmpty())
        .andExpect(jsonPath("$.offset").value(20));

    assertThat(query.getValue()).isEqualTo(new DeckQuery("Legacy", null, 10, 20));
  }

  @Test
  void anUnknownParameterIsAProblemBeforeAnyRead() throws Exception {
    mvc.perform(get("/api/v1/cards/" + BOLT + "/decks?sort=name"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("invalid_query"));

    verifyNoInteractions(decks);
  }

  @Test
  void aDeckIsReadByRunAndPositionInTheGivenCatalog() throws Exception {
    String run = "scores-" + "a".repeat(64);
    when(decks.deck(run, "7", "catalog-a"))
        .thenReturn(
            new DeckDetail(
                null,
                "catalog-a",
                7,
                "edh-open#8",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null));

    mvc.perform(get("/api/v1/decks/" + run + "/7?catalog_snapshot_id=catalog-a"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.position").value(7))
        .andExpect(jsonPath("$.mainboard").isEmpty());
    mvc.perform(get("/api/v1/decks/" + run + "/7?offset=1"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("invalid_query"));
  }
}
