package io.mtgscorer.api.catalog;

import static io.mtgscorer.api.catalog.CatalogModels.*;

import io.mtgscorer.api.error.CatalogProblem;
import io.mtgscorer.api.snapshots.SnapshotService;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

@Service
public class CatalogService {
  private final CatalogRepository repository;
  private final SnapshotService snapshots;
  private final CursorCodec cursors;

  public CatalogService(
      CatalogRepository repository, SnapshotService snapshots, ObjectMapper mapper) {
    this.repository = repository;
    this.snapshots = snapshots;
    this.cursors = new CursorCodec(mapper);
  }

  public CardPage search(CatalogQuery query) {
    var cursor = cursors.decode("cards", query);
    String snapshot =
        snapshots.resolve(cursor == null ? query.snapshot() : cursor.catalog_snapshot_id());
    var rows = repository.search(snapshot, query, cursor);
    boolean more = rows.size() > query.limit();
    var visible = rows.stream().limit(query.limit()).toList();
    String next = null;
    if (more) {
      var last = visible.getLast();
      next =
          cursors.encode(
              "cards",
              snapshot,
              query,
              List.of(last.nameKey(), last.summary().oracle_id().toString()));
    }
    return new CardPage(
        snapshot, visible.stream().map(CatalogRepository.CardRow::summary).toList(), next);
  }

  public CardDetail detail(String oracle, String explicitSnapshot) {
    UUID id = oracleId(oracle);
    return repository.detail(snapshots.resolve(explicitSnapshot), id);
  }

  public PrintingPage printings(String oracle, CatalogQuery query) {
    UUID id = oracleId(oracle);
    String resource = "printings:" + id;
    var cursor = cursors.decode(resource, query);
    String snapshot =
        snapshots.resolve(cursor == null ? query.snapshot() : cursor.catalog_snapshot_id());
    var rows = repository.printings(snapshot, id, query, cursor);
    var visible = rows.stream().limit(query.limit()).toList();
    String next =
        rows.size() > query.limit()
            ? cursors.encode(
                resource, snapshot, query, List.of(visible.getLast().scryfall_id().toString()))
            : null;
    return new PrintingPage(snapshot, id, visible, next);
  }

  private UUID oracleId(String value) {
    if (!value.matches(
        "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"))
      throw CatalogProblem.query("Invalid Oracle ID.");
    return UUID.fromString(value);
  }
}
