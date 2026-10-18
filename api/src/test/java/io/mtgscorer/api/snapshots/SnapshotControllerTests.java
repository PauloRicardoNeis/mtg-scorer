package io.mtgscorer.api.snapshots;

import static io.mtgscorer.api.snapshots.SnapshotModels.*;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.mtgscorer.api.error.CatalogExceptionHandler;
import io.mtgscorer.api.error.CatalogProblem;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

@ExtendWith(MockitoExtension.class)
class SnapshotControllerTests {
  private static final OffsetDateTime AT = OffsetDateTime.parse("2026-05-01T12:00:00Z");
  private static final Snapshot SNAPSHOT =
      new Snapshot(
          "catalog-a",
          "catalog-publication-v1",
          "scryfall",
          "1",
          AT,
          AT,
          new Selection("default_cards", "Default cards"),
          2,
          3,
          List.of(new SetInfo("m11", "Magic 2011")),
          List.of(new Attribution("Scryfall card metadata", "https://scryfall.com/docs/api")),
          new TournamentEvidence("not_available", List.of("no_tournament_dataset")),
          AT,
          AT,
          Map.of());

  @Mock private SnapshotService snapshots;
  private MockMvc mvc;

  @BeforeEach
  void setUp() {
    mvc =
        MockMvcBuilders.standaloneSetup(new SnapshotController(snapshots))
            .setControllerAdvice(new CatalogExceptionHandler())
            .build();
  }

  @Test
  void listsPublishedSnapshots() throws Exception {
    when(snapshots.list()).thenReturn(new SnapshotList("catalog-a", List.of(SNAPSHOT)));

    mvc.perform(get("/api/v1/snapshots"))
        .andExpect(status().isOk())
        .andExpect(content().contentType("application/json"))
        .andExpect(jsonPath("$.active_catalog_snapshot_id").value("catalog-a"))
        .andExpect(jsonPath("$.items[0].sets[0].set_code").value("m11"))
        .andExpect(jsonPath("$.items[0].tournament_evidence.state").value("not_available"));
  }

  @Test
  void describesOneSnapshot() throws Exception {
    when(snapshots.detail("catalog-a")).thenReturn(SNAPSHOT);

    mvc.perform(get("/api/v1/snapshots/{id}", "catalog-a"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.catalog_snapshot_id").value("catalog-a"))
        .andExpect(jsonPath("$.card_count").value(2));
  }

  @Test
  void neitherEndpointAcceptsQueryParameters() throws Exception {
    for (String path : List.of("/api/v1/snapshots", "/api/v1/snapshots/catalog-a")) {
      mvc.perform(get(path).queryParam("limit", "5"))
          .andExpect(status().isBadRequest())
          .andExpect(content().contentType("application/problem+json"))
          .andExpect(jsonPath("$.code").value("invalid_query"))
          .andExpect(jsonPath("$.detail").value("Unknown query parameter."))
          .andExpect(jsonPath("$.instance").value(path));
    }
    verifyNoInteractions(snapshots);
  }

  @Test
  void anUnknownSnapshotIsAProblemDetail() throws Exception {
    when(snapshots.detail("catalog-gone"))
        .thenThrow(new CatalogProblem(404, "snapshot_not_found", "Published snapshot not found."));

    mvc.perform(get("/api/v1/snapshots/{id}", "catalog-gone"))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("snapshot_not_found"));
  }
}
