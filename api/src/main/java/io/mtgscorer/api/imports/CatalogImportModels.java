package io.mtgscorer.api.imports;

import io.swagger.v3.oas.annotations.media.Schema;
import java.util.Map;
import java.util.UUID;

public final class CatalogImportModels {
  private CatalogImportModels() {}

  public record ImportJob(
      UUID job_id,
      String status_url,
      @Schema(allowableValues = {"queued", "running", "succeeded", "failed"}) String state,
      @Schema(
              allowableValues = {
                "queued",
                "source",
                "normalizing",
                "validating",
                "publishing",
                "promoting",
                "complete"
              })
          String stage,
      @Schema(format = "date-time") String requested_at,
      @Schema(
              types = {"string", "null"},
              format = "date-time")
          String started_at,
      @Schema(format = "date-time") String updated_at,
      @Schema(
              types = {"string", "null"},
              format = "date-time")
          String finished_at,
      @Schema(types = {"string", "null"}) String source_snapshot_id,
      @Schema(types = {"string", "null"}) String catalog_snapshot_id,
      @Schema(types = {"string", "null"}) String parser_version,
      @Schema(types = {"string", "null"}) String schema_version,
      Map<String, Long> row_counts,
      Map<String, Long> excluded_record_counts,
      @Schema(
              types = {"string", "null"},
              allowableValues = {"published", "already_published"})
          String result,
      @Schema(
              types = {"string", "null"},
              allowableValues = {"import_failed", "worker_interrupted"})
          String error_code) {}
}
