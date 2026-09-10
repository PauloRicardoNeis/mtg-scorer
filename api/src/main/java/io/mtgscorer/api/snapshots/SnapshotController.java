package io.mtgscorer.api.snapshots;

import static io.mtgscorer.api.snapshots.SnapshotModels.*;

import io.mtgscorer.api.error.CatalogProblem;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping(value = "/api/v1/snapshots", produces = "application/json")
public class SnapshotController {
  private final SnapshotService snapshots;

  public SnapshotController(SnapshotService snapshots) {
    this.snapshots = snapshots;
  }

  @GetMapping
  @Operation(operationId = "listSnapshots", summary = "List published catalogs, active first")
  public SnapshotList list(
      @Parameter(hidden = true) @RequestParam MultiValueMap<String, String> query) {
    if (!query.isEmpty()) throw CatalogProblem.query("Unknown query parameter.");
    return snapshots.list();
  }

  @GetMapping("/{catalog_snapshot_id}")
  @Operation(operationId = "getSnapshot", summary = "Inspect catalog provenance and available sets")
  public Snapshot detail(
      @PathVariable String catalog_snapshot_id,
      @Parameter(hidden = true) @RequestParam MultiValueMap<String, String> query) {
    if (!query.isEmpty()) throw CatalogProblem.query("Unknown query parameter.");
    return snapshots.detail(catalog_snapshot_id);
  }
}
