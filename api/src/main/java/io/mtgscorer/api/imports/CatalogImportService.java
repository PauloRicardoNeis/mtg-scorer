package io.mtgscorer.api.imports;

import io.mtgscorer.api.error.CatalogProblem;
import io.mtgscorer.api.imports.CatalogImportModels.ImportJob;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

/** Database control plane for the separately operated import worker. */
@Service
public class CatalogImportService {
  private final JdbcTemplate jdbc;
  private final ObjectMapper mapper;

  public CatalogImportService(JdbcTemplate jdbc, ObjectMapper mapper) {
    this.jdbc = jdbc;
    this.mapper = mapper;
  }

  public ImportJob request() {
    UUID id =
        jdbc.queryForObject(
            "SELECT catalog.request_catalog_import(?)", UUID.class, UUID.randomUUID());
    return status(id);
  }

  public ImportJob status(UUID id) {
    String json =
        jdbc.queryForObject("SELECT catalog.catalog_import_status(?)::text", String.class, id);
    if (json == null) throw new CatalogProblem(404, "import_not_found", "Import job not found.");
    return mapper.readValue(json, ImportJob.class);
  }
}
