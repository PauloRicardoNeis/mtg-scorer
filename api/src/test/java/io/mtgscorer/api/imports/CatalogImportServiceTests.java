package io.mtgscorer.api.imports;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.error.CatalogProblem;
import io.mtgscorer.api.imports.CatalogImportModels.ImportJob;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import tools.jackson.databind.json.JsonMapper;

@ExtendWith(MockitoExtension.class)
class CatalogImportServiceTests {
  private static final UUID JOB = UUID.fromString("20000000-0000-4000-8000-000000000001");

  /** The job row as catalog.catalog_import_status renders it. */
  private static final String SUCCEEDED =
      """
      {"job_id":"%s","state":"succeeded","stage":"complete",
       "requested_at":"2026-05-01T12:00:00.123456+00:00","started_at":"2026-05-01T12:00:01+00:00",
       "updated_at":"2026-05-01T12:05:00+00:00","finished_at":"2026-05-01T12:05:00+00:00",
       "source_snapshot_id":"scryfall-default-cards-20260501","catalog_snapshot_id":"catalog-abc",
       "parser_version":"1","schema_version":"catalog-publication-v1",
       "row_counts":{"cards":2,"printings":3},"excluded_record_counts":{"tokens":1},
       "result":"published","error_code":null,
       "status_url":"/api/v1/admin/catalog-imports/%s"}
      """
          .formatted(JOB, JOB);

  @Mock private JdbcTemplate jdbc;
  private CatalogImportService service;

  @BeforeEach
  void setUp() {
    service = new CatalogImportService(jdbc, JsonMapper.builder().build());
  }

  @Test
  void statusMapsTheDurableJobRecord() {
    when(jdbc.queryForObject(anyString(), eq(String.class), eq(JOB))).thenReturn(SUCCEEDED);

    assertThat(service.status(JOB))
        .isEqualTo(
            new ImportJob(
                JOB,
                "/api/v1/admin/catalog-imports/" + JOB,
                "succeeded",
                "complete",
                "2026-05-01T12:00:00.123456+00:00",
                "2026-05-01T12:00:01+00:00",
                "2026-05-01T12:05:00+00:00",
                "2026-05-01T12:05:00+00:00",
                "scryfall-default-cards-20260501",
                "catalog-abc",
                "1",
                "catalog-publication-v1",
                Map.of("cards", 2L, "printings", 3L),
                Map.of("tokens", 1L),
                "published",
                null));
  }

  @Test
  void anUnknownJobIsNotFound() {
    when(jdbc.queryForObject(anyString(), eq(String.class), eq(JOB))).thenReturn(null);

    assertThatThrownBy(() -> service.status(JOB))
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> {
              assertThat(problem.status()).isEqualTo(404);
              assertThat(problem.code()).isEqualTo("import_not_found");
            });
  }

  @Test
  void requestReportsTheJobTheDatabaseChoseEvenWhenOneWasAlreadyActive() {
    // The database returns the queued or running job instead of the proposed new ID.
    when(jdbc.queryForObject(anyString(), eq(UUID.class), any(UUID.class))).thenReturn(JOB);
    when(jdbc.queryForObject(anyString(), eq(String.class), eq(JOB))).thenReturn(SUCCEEDED);

    assertThat(service.request().job_id()).isEqualTo(JOB);

    ArgumentCaptor<UUID> proposed = ArgumentCaptor.forClass(UUID.class);
    verify(jdbc).queryForObject(anyString(), eq(UUID.class), proposed.capture());
    assertThat(proposed.getValue()).isNotEqualTo(JOB);
  }

  @Test
  void requestProposesAFreshIdEachTime() {
    when(jdbc.queryForObject(anyString(), eq(UUID.class), any(UUID.class)))
        .thenAnswer(call -> call.getArgument(2));
    when(jdbc.queryForObject(anyString(), eq(String.class), any(UUID.class)))
        .thenAnswer(call -> SUCCEEDED.replace(JOB.toString(), call.getArgument(2).toString()));

    assertThat(service.request().job_id()).isNotEqualTo(service.request().job_id());
  }
}
