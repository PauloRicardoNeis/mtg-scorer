package io.mtgscorer.api.snapshots;

import static io.mtgscorer.api.snapshots.SnapshotModels.*;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

/** Public snapshot resolver. Catalog callers use this entry point, never snapshot SQL. */
@Service
public class SnapshotService {
  private final JdbcTemplate jdbc;
  private final ObjectMapper mapper;

  public SnapshotService(JdbcTemplate jdbc, ObjectMapper mapper) {
    this.jdbc = jdbc;
    this.mapper = mapper;
  }

  public String resolve(String explicit) {
    if (explicit != null && !explicit.matches("[a-z0-9][a-z0-9-]{0,95}"))
      throw CatalogProblem.query("Invalid snapshot ID.");
    List<String> ids =
        explicit == null
            ? jdbc.queryForList(
                "SELECT s.catalog_snapshot_id FROM catalog.active_catalog a JOIN catalog.published_snapshot s USING(catalog_snapshot_id)",
                String.class)
            : jdbc.queryForList(
                "SELECT catalog_snapshot_id FROM catalog.published_snapshot WHERE catalog_snapshot_id=?",
                String.class,
                explicit);
    if (ids.isEmpty()) {
      if (explicit != null)
        throw new CatalogProblem(404, "snapshot_not_found", "Published snapshot not found.");
      throw new CatalogProblem(
          503, "catalog_unavailable", "No published catalog is available yet.");
    }
    return ids.getFirst();
  }

  public SnapshotList list() {
    String active = resolve(null);
    List<String> ids =
        jdbc.queryForList(
            "SELECT catalog_snapshot_id FROM catalog.published_snapshot ORDER BY (catalog_snapshot_id=?) DESC,published_at DESC,catalog_snapshot_id LIMIT 20",
            String.class,
            active);
    return new SnapshotList(active, ids.stream().map(this::detail).toList());
  }

  public Snapshot detail(String id) {
    String snapshot = resolve(id);
    return jdbc.queryForObject(
        """
      SELECT jsonb_build_object(
        'catalog_snapshot_id',s.catalog_snapshot_id,'schema_version',s.schema_version,
        'source',s.source,'parser_version',s.parser_version,'created_at',s.created_at,
        'published_at',s.published_at,'selection',s.selection,
        'card_count',s.manifest->'row_counts'->'cards','printing_count',s.manifest->'row_counts'->'printings',
        'excluded_record_counts',s.manifest->'excluded_record_counts',
        'retrieved_from',(SELECT min(retrieved_at) FROM catalog.published_catalog_printing WHERE catalog_snapshot_id=s.catalog_snapshot_id),
        'retrieved_to',(SELECT max(retrieved_at) FROM catalog.published_catalog_printing WHERE catalog_snapshot_id=s.catalog_snapshot_id),
        'sets',(SELECT jsonb_agg(to_jsonb(v) ORDER BY set_code) FROM (SELECT DISTINCT set_code,set_name FROM catalog.published_catalog_printing WHERE catalog_snapshot_id=s.catalog_snapshot_id) v),
        'attribution',jsonb_build_array(jsonb_build_object('label','Scryfall card metadata','url','https://scryfall.com/docs/api'),jsonb_build_object('label','Magic: The Gathering / Wizards of the Coast','url','https://magic.wizards.com/')),
        'tournament_evidence',jsonb_build_object('state','not_available','reason_codes',jsonb_build_array('no_tournament_dataset'))
      )::text FROM catalog.published_snapshot s WHERE s.catalog_snapshot_id=?
      """,
        (row, index) -> mapper.readValue(row.getString(1), Snapshot.class),
        snapshot);
  }
}
