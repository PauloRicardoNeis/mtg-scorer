package io.mtgscorer.api.snapshots;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.error.CatalogProblem;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.health.contributor.Health;
import org.springframework.boot.health.contributor.Status;
import org.springframework.jdbc.CannotGetJdbcConnectionException;

@ExtendWith(MockitoExtension.class)
class CatalogHealthIndicatorTests {
  @Mock private SnapshotService snapshots;

  @Test
  void upWhenAnActiveCatalogResolves() {
    when(snapshots.resolve(null)).thenReturn("catalog-a");

    assertBare(new CatalogHealthIndicator(snapshots).health(), Status.UP);
  }

  @Test
  void downWithoutAPublishedCatalog() {
    when(snapshots.resolve(null))
        .thenThrow(
            new CatalogProblem(
                503, "catalog_unavailable", "No published catalog is available yet."));

    assertBare(new CatalogHealthIndicator(snapshots).health(), Status.DOWN);
  }

  @Test
  void downWhenTheDatabaseIsUnreachable() {
    when(snapshots.resolve(null)).thenThrow(new CannotGetJdbcConnectionException("sensitive"));

    assertBare(new CatalogHealthIndicator(snapshots).health(), Status.DOWN);
  }

  @Test
  void unexpectedFailuresPropagateToTheHealthEndpoint() {
    when(snapshots.resolve(null)).thenThrow(new IllegalStateException("bug"));

    assertThatThrownBy(() -> new CatalogHealthIndicator(snapshots).health())
        .isInstanceOf(IllegalStateException.class);
  }

  /** Readiness never exposes the snapshot ID or the failure. */
  private static void assertBare(Health health, Status status) {
    assertThat(health.getStatus()).isEqualTo(status);
    assertThat(health.getDetails()).isEmpty();
  }
}
