package io.mtgscorer.api.snapshots;

import io.mtgscorer.api.error.CatalogProblem;
import org.springframework.boot.health.contributor.Health;
import org.springframework.boot.health.contributor.HealthIndicator;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Component;

@Component("catalogHealthIndicator")
public class CatalogHealthIndicator implements HealthIndicator {
  private final SnapshotService snapshots;

  public CatalogHealthIndicator(SnapshotService snapshots) {
    this.snapshots = snapshots;
  }

  @Override
  public Health health() {
    try {
      snapshots.resolve(null);
      return Health.up().build();
    } catch (CatalogProblem | DataAccessException unavailable) {
      return Health.down().build();
    }
  }
}
