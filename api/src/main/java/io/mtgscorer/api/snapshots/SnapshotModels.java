package io.mtgscorer.api.snapshots;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

public final class SnapshotModels {
  private SnapshotModels() {}

  public record Selection(String kind, String description) {}

  public record SetInfo(String set_code, String set_name) {}

  public record Attribution(String label, String url) {}

  public record TournamentEvidence(String state, List<String> reason_codes) {}

  public record Snapshot(
      String catalog_snapshot_id,
      String schema_version,
      String source,
      String parser_version,
      OffsetDateTime created_at,
      OffsetDateTime published_at,
      Selection selection,
      long card_count,
      long printing_count,
      List<SetInfo> sets,
      List<Attribution> attribution,
      TournamentEvidence tournament_evidence,
      OffsetDateTime retrieved_from,
      OffsetDateTime retrieved_to,
      Map<String, Integer> excluded_record_counts) {}

  public record SnapshotList(String active_catalog_snapshot_id, List<Snapshot> items) {}
}
