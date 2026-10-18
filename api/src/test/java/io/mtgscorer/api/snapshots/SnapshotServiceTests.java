package io.mtgscorer.api.snapshots;

import static io.mtgscorer.api.snapshots.SnapshotModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.error.CatalogProblem;
import java.sql.ResultSet;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import tools.jackson.databind.json.JsonMapper;

@ExtendWith(MockitoExtension.class)
class SnapshotServiceTests {
  @Mock private JdbcTemplate jdbc;
  private SnapshotService service;

  @BeforeEach
  void setUp() {
    service = new SnapshotService(jdbc, JsonMapper.builder().build());
  }

  @Test
  void theActiveSnapshotResolvesThroughThePublishedPointer() {
    when(jdbc.queryForList(anyString(), eq(String.class))).thenReturn(List.of("catalog-a"));

    assertThat(service.resolve(null)).isEqualTo("catalog-a");
  }

  @Test
  void withoutAnActiveSnapshotTheCatalogIsUnavailable() {
    when(jdbc.queryForList(anyString(), eq(String.class))).thenReturn(List.of());

    assertProblem(
        () -> service.resolve(null),
        503,
        "catalog_unavailable",
        "No published catalog is available yet.");
  }

  @Test
  void anExplicitSnapshotMustBePublished() {
    when(jdbc.queryForList(anyString(), eq(String.class), eq("catalog-a")))
        .thenReturn(List.of("catalog-a"));
    when(jdbc.queryForList(anyString(), eq(String.class), eq("catalog-staging")))
        .thenReturn(List.of());

    assertThat(service.resolve("catalog-a")).isEqualTo("catalog-a");
    assertProblem(
        () -> service.resolve("catalog-staging"),
        404,
        "snapshot_not_found",
        "Published snapshot not found.");
  }

  @ParameterizedTest
  @ValueSource(strings = {"", "Catalog-A", "-catalog", "catalog_a", "catalog a", "catalog/../a"})
  void malformedSnapshotIdsAreRejectedWithoutQuerying(String id) {
    assertProblem(() -> service.resolve(id), 400, "invalid_query", "Invalid snapshot ID.");
    assertProblem(() -> service.detail(id), 400, "invalid_query", "Invalid snapshot ID.");
    verifyNoInteractions(jdbc);
  }

  @Test
  void aSnapshotIdLongerThan96CharactersIsRejected() {
    assertProblem(
        () -> service.resolve("c".repeat(97)), 400, "invalid_query", "Invalid snapshot ID.");
    verifyNoInteractions(jdbc);
  }

  @Test
  void detailMapsThePublishedProvenance() {
    when(jdbc.queryForList(anyString(), eq(String.class), eq("catalog-a")))
        .thenReturn(List.of("catalog-a"));
    stubDetails();

    Snapshot snapshot = service.detail("catalog-a");

    assertThat(snapshot.catalog_snapshot_id()).isEqualTo("catalog-a");
    assertThat(snapshot.schema_version()).isEqualTo("catalog-publication-v1");
    assertThat(snapshot.created_at())
        .isAtSameInstantAs(OffsetDateTime.parse("2026-05-01T12:00:00.123456+00:00"));
    assertThat(snapshot.published_at())
        .isAtSameInstantAs(OffsetDateTime.parse("2026-05-01T09:30:00-03:00"));
    assertThat(snapshot.selection()).isEqualTo(new Selection("default_cards", "Default cards"));
    assertThat(snapshot.card_count()).isEqualTo(2);
    assertThat(snapshot.printing_count()).isEqualTo(3);
    assertThat(snapshot.sets()).containsExactly(new SetInfo("m11", "Magic 2011"));
    assertThat(snapshot.attribution())
        .extracting(Attribution::url)
        .contains("https://scryfall.com/docs/api");
    assertThat(snapshot.tournament_evidence())
        .isEqualTo(new TournamentEvidence("not_available", List.of("no_tournament_dataset")));
    assertThat(snapshot.retrieved_from()).isNotNull();
    assertThat(snapshot.retrieved_to()).isNotNull();
    assertThat(snapshot.excluded_record_counts()).isEqualTo(Map.of("tokens", 1));
  }

  @Test
  void listPutsTheActiveSnapshotFirstAndDescribesEach() {
    when(jdbc.queryForList(anyString(), eq(String.class))).thenReturn(List.of("catalog-b"));
    // First the listing ordered around the active ID, then that snapshot's own resolution.
    when(jdbc.queryForList(anyString(), eq(String.class), eq("catalog-b")))
        .thenReturn(List.of("catalog-b", "catalog-a"), List.of("catalog-b"));
    when(jdbc.queryForList(anyString(), eq(String.class), eq("catalog-a")))
        .thenReturn(List.of("catalog-a"));
    stubDetails();

    SnapshotList list = service.list();

    assertThat(list.active_catalog_snapshot_id()).isEqualTo("catalog-b");
    assertThat(list.items())
        .extracting(Snapshot::catalog_snapshot_id)
        .containsExactly("catalog-b", "catalog-a");
  }

  @Test
  void listingWithoutAnActiveSnapshotIsUnavailable() {
    when(jdbc.queryForList(anyString(), eq(String.class))).thenReturn(List.of());

    assertProblem(
        service::list, 503, "catalog_unavailable", "No published catalog is available yet.");
  }

  /** Renders each requested snapshot through the service's own row mapper. */
  @SuppressWarnings("unchecked")
  private void stubDetails() {
    when(jdbc.queryForObject(anyString(), any(RowMapper.class), anyString()))
        .thenAnswer(
            call -> {
              String json = json(call.getArgument(2));
              ResultSet row = mock(ResultSet.class, column -> json);
              return call.<RowMapper<Snapshot>>getArgument(1).mapRow(row, 0);
            });
  }

  /** A snapshot as the detail query's jsonb_build_object renders it. */
  private static String json(String id) {
    return """
        {"catalog_snapshot_id":"%s","schema_version":"catalog-publication-v1","source":"scryfall",
         "parser_version":"1","created_at":"2026-05-01T12:00:00.123456+00:00",
         "published_at":"2026-05-01T12:30:00+00:00",
         "selection":{"kind":"default_cards","description":"Default cards"},
         "card_count":2,"printing_count":3,"excluded_record_counts":{"tokens":1},
         "retrieved_from":"2026-05-01T11:00:00+00:00","retrieved_to":"2026-05-01T11:10:00+00:00",
         "sets":[{"set_code":"m11","set_name":"Magic 2011"}],
         "attribution":[{"label":"Scryfall card metadata","url":"https://scryfall.com/docs/api"},
                        {"label":"Magic: The Gathering / Wizards of the Coast",
                         "url":"https://magic.wizards.com/"}],
         "tournament_evidence":{"state":"not_available","reason_codes":["no_tournament_dataset"]}}
        """
        .formatted(id);
  }

  private static void assertProblem(ThrowingCallable call, int status, String code, String detail) {
    assertThatThrownBy(call)
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> {
              assertThat(problem.status()).isEqualTo(status);
              assertThat(problem.code()).isEqualTo(code);
              assertThat(problem.getMessage()).isEqualTo(detail);
            });
  }
}
