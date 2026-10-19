package io.mtgscorer.api.catalog;

import static io.mtgscorer.api.catalog.CatalogModels.*;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;
import tools.jackson.databind.ObjectMapper;

/** Explicit, bound queries against published views; no ingestion or external-source dependency. */
@Repository
class CatalogRepository {
  private final NamedParameterJdbcTemplate jdbc;
  private final ObjectMapper mapper;

  CatalogRepository(NamedParameterJdbcTemplate jdbc, ObjectMapper mapper) {
    this.jdbc = jdbc;
    this.mapper = mapper;
  }

  record CardRow(CardSummary summary, String nameKey) {}

  private static final String PRINTING_JSON = CatalogSql.PRINTING_JSON;
  private static final String SHOWN = CatalogSql.SHOWN;

  private String printingPredicate(CatalogQuery query, Map<String, Object> args) {
    List<String> conditions = new ArrayList<>();
    conditions.add("p.catalog_snapshot_id=:snapshot AND p.oracle_id=c.oracle_id");
    if (!query.sets().isEmpty()) {
      conditions.add("p.set_code IN (:sets)");
      args.put("sets", query.sets());
    }
    if (!query.rarities().isEmpty()) {
      conditions.add("p.rarity IN (:rarities)");
      args.put("rarities", query.rarities());
    }
    if (query.game() != null) {
      conditions.add(":game=ANY(p.games)");
      args.put("game", query.game());
    }
    return String.join(" AND ", conditions);
  }

  List<CardRow> search(String snapshot, CatalogQuery query, CursorCodec.Cursor cursor) {
    Map<String, Object> args = new HashMap<>();
    args.put("snapshot", snapshot);
    args.put("limit", query.limit() + 1);
    String predicate = printingPredicate(query, args);
    String where = "c.catalog_snapshot_id=:snapshot";
    if (query.q() != null) {
      where +=
          " AND EXISTS(SELECT FROM catalog.published_catalog_alias a WHERE a.catalog_snapshot_id=c.catalog_snapshot_id AND a.oracle_id=c.oracle_id AND strpos(a.alias_key,:q)>0)";
      args.put("q", query.q());
    }
    if (query.colorIdentity() != null) {
      where += " AND c.color_identity <@ string_to_array(:colors,',')";
      args.put(
          "colors",
          query.colorIdentity().equals("C")
              ? ""
              : String.join(",", query.colorIdentity().split("")));
    }
    if (!query.colors().isEmpty()) {
      // Any selected color matches; unknown colors (null) never match.
      List<String> any = new ArrayList<>();
      List<String> chromatic = query.colors().stream().filter(c -> !c.equals("C")).toList();
      if (!chromatic.isEmpty()) {
        any.add("c.colors && string_to_array(:anyColors,',')");
        args.put("anyColors", String.join(",", chromatic));
      }
      if (query.colors().contains("C")) any.add("c.colors='{}'");
      where += " AND (" + String.join(" OR ", any) + ")";
    }
    if (query.type() != null) {
      where += " AND shown.type_line ~ :typePattern";
      args.put("typePattern", CatalogSql.typePattern(query.type()));
    }
    if (cursor != null) {
      where += " AND (c.name_key,c.oracle_id) > (:lastName COLLATE \"C\",CAST(:lastId AS uuid))";
      args.put("lastName", cursor.last_key().getFirst());
      args.put("lastId", cursor.last_key().getLast());
    }
    String sql =
        "SELECT c.oracle_id,c.name,c.layout,shown.mana_cost,shown.type_line,c.color_identity,c.name_key,eligible.n,preview.printing FROM catalog.published_catalog_card c CROSS JOIN LATERAL "
            + SHOWN
            + " shown CROSS JOIN LATERAL (SELECT count(*) n FROM catalog.published_catalog_printing p WHERE "
            + predicate
            + ") eligible CROSS JOIN LATERAL (SELECT ("
            + PRINTING_JSON
            + ")::text printing FROM catalog.published_catalog_printing p WHERE "
            + predicate
            + " "
            + CatalogSql.PREVIEW_ORDER
            + ") preview WHERE "
            + where
            + " AND eligible.n>0 ORDER BY c.name_key COLLATE \"C\",c.oracle_id LIMIT :limit";
    return jdbc.query(
        sql,
        args,
        (row, index) ->
            new CardRow(
                new CardSummary(
                    row.getObject("oracle_id", UUID.class),
                    row.getString("name"),
                    row.getString("layout"),
                    row.getString("mana_cost"),
                    row.getString("type_line"),
                    row.getArray("color_identity") == null
                        ? null
                        : List.of((String[]) row.getArray("color_identity").getArray()),
                    row.getLong("n"),
                    mapper.readValue(row.getString("printing"), Printing.class)),
                row.getString("name_key")));
  }

  void requireCard(String snapshot, UUID oracle) {
    if (jdbc.queryForObject(
            "SELECT count(*) FROM catalog.published_catalog_card WHERE catalog_snapshot_id=:snapshot AND oracle_id=:oracle",
            Map.of("snapshot", snapshot, "oracle", oracle),
            Integer.class)
        == 0) throw new CatalogProblem(404, "card_not_found", "Card not found in this catalog.");
  }

  CardDetail detail(String snapshot, UUID oracle) {
    List<CardDetail> cards =
        jdbc.query(
            """
      SELECT ((to_jsonb(c)-'name_key'-'source_scryfall_id') || jsonb_build_object('faces',
       (SELECT coalesce(jsonb_agg(to_jsonb(f)-'catalog_snapshot_id'-'oracle_id' ORDER BY f.face_index),'[]'::jsonb)
        FROM catalog.published_catalog_face f WHERE f.catalog_snapshot_id=c.catalog_snapshot_id AND f.oracle_id=c.oracle_id)))::text
      FROM catalog.published_catalog_card c WHERE c.catalog_snapshot_id=:snapshot AND c.oracle_id=:oracle
      """,
            Map.of("snapshot", snapshot, "oracle", oracle),
            (row, index) -> mapper.readValue(row.getString(1), CardDetail.class));
    if (cards.isEmpty())
      throw new CatalogProblem(404, "card_not_found", "Card not found in this catalog.");
    return cards.getFirst();
  }

  List<Printing> printings(
      String snapshot, UUID oracle, CatalogQuery query, CursorCodec.Cursor cursor) {
    requireCard(snapshot, oracle);
    Map<String, Object> args = new HashMap<>();
    args.put("snapshot", snapshot);
    args.put("oracle", oracle);
    args.put("limit", query.limit() + 1);
    String predicate = printingPredicate(query, args);
    if (cursor != null) {
      predicate += " AND p.scryfall_id>CAST(:lastId AS uuid)";
      args.put("lastId", cursor.last_key().getFirst());
    }
    return jdbc.query(
        "SELECT ("
            + PRINTING_JSON
            + ")::text FROM catalog.published_catalog_printing p JOIN catalog.published_catalog_card c ON c.catalog_snapshot_id=p.catalog_snapshot_id AND c.oracle_id=p.oracle_id WHERE c.oracle_id=:oracle AND "
            + predicate
            + " ORDER BY p.scryfall_id LIMIT :limit",
        args,
        (row, index) -> mapper.readValue(row.getString(1), Printing.class));
  }
}
