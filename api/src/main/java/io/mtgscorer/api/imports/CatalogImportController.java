package io.mtgscorer.api.imports;

import io.mtgscorer.api.error.CatalogProblem;
import io.mtgscorer.api.imports.CatalogImportModels.ImportJob;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.enums.SecuritySchemeType;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.security.SecurityScheme;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/** Administrative control plane: short database operations, no source I/O. */
@RestController
@RequestMapping("/api/v1/admin/catalog-imports")
@SecurityScheme(name = "catalogAdmin", type = SecuritySchemeType.HTTP, scheme = "bearer")
@SecurityRequirement(name = "catalogAdmin")
public class CatalogImportController {
  private final CatalogImportService service;
  private final String token;

  public CatalogImportController(
      CatalogImportService service, @Value("${catalog.import.admin-token:}") String token) {
    this.service = service;
    this.token = token;
  }

  private void authorize(String authorization) {
    if (token.length() < 32)
      throw new CatalogProblem(
          503, "admin_unavailable", "Catalog import administration is disabled.");
    if (authorization == null
        || !MessageDigest.isEqual(
            ("Bearer " + token).getBytes(StandardCharsets.UTF_8),
            authorization.getBytes(StandardCharsets.UTF_8)))
      throw new CatalogProblem(
          401, "unauthorized", "A valid administrative credential is required.");
  }

  @PostMapping
  @ResponseStatus(org.springframework.http.HttpStatus.ACCEPTED)
  @Operation(summary = "Queue an import of the current Scryfall default-cards snapshot")
  public ResponseEntity<ImportJob> request(
      @RequestHeader(value = "Authorization", required = false) String authorization) {
    authorize(authorization);
    ImportJob job = service.request();
    return ResponseEntity.accepted().location(URI.create(job.status_url())).body(job);
  }

  @GetMapping("/{job_id}")
  @Operation(summary = "Inspect durable import status and available counts")
  public ImportJob get(
      @RequestHeader(value = "Authorization", required = false) String authorization,
      @PathVariable("job_id") String id) {
    authorize(authorization);
    if (!id.matches("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"))
      throw CatalogProblem.query("Invalid import job ID.");
    return service.status(UUID.fromString(id));
  }
}
