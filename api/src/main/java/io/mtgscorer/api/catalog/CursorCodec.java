package io.mtgscorer.api.catalog;

import io.mtgscorer.api.error.CatalogProblem;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

/** Public keyset cursor, strictly validated and bound; it is not an authorization token. */
public final class CursorCodec {
  private final ObjectMapper mapper;

  public CursorCodec(ObjectMapper mapper) {
    this.mapper = mapper;
  }

  public record Cursor(
      int version,
      String resource,
      String catalog_snapshot_id,
      String filter_hash,
      String sort,
      int limit,
      List<String> last_key) {}

  private String fingerprint(CatalogQuery query) {
    Map<String, Object> filters = new TreeMap<>();
    filters.put("q", query.q());
    filters.put("sets", query.sets().isEmpty() ? null : query.sets());
    filters.put("rarities", query.rarities().isEmpty() ? null : query.rarities());
    filters.put("game", query.game());
    filters.put("color_identity", query.colorIdentity());
    try {
      return HexFormat.of()
          .formatHex(
              MessageDigest.getInstance("SHA-256").digest(mapper.writeValueAsBytes(filters)));
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException(impossible);
    }
  }

  public String encode(String resource, String snapshot, CatalogQuery query, List<String> key) {
    return Base64.getUrlEncoder()
        .withoutPadding()
        .encodeToString(
            mapper.writeValueAsBytes(
                new Cursor(
                    1, resource, snapshot, fingerprint(query), query.sort(), query.limit(), key)));
  }

  public Cursor decode(String resource, CatalogQuery query) {
    if (query.cursor() == null) return null;
    try {
      String encoded = query.cursor();
      if (encoded.length() > 4096 || !encoded.matches("[A-Za-z0-9_-]+"))
        throw CatalogProblem.cursor();
      byte[] bytes = Base64.getUrlDecoder().decode(encoded);
      String json = new String(bytes, StandardCharsets.UTF_8);
      if (!java.util.Arrays.equals(bytes, json.getBytes(StandardCharsets.UTF_8)))
        throw CatalogProblem.cursor();
      JsonNode node = mapper.readTree(json);
      if (!node.isObject()
          || !node.propertyNames()
              .equals(
                  Set.of(
                      "version",
                      "resource",
                      "catalog_snapshot_id",
                      "filter_hash",
                      "sort",
                      "limit",
                      "last_key"))) throw CatalogProblem.cursor();
      if (!node.path("version").isIntegralNumber()
          || node.path("version").asInt() != 1
          || !node.path("limit").isIntegralNumber()) throw CatalogProblem.cursor();
      for (String field : List.of("resource", "catalog_snapshot_id", "filter_hash", "sort")) {
        if (!node.path(field).isString()) throw CatalogProblem.cursor();
      }
      if (!node.path("last_key").isArray()) throw CatalogProblem.cursor();
      for (JsonNode key : node.path("last_key")) if (!key.isString()) throw CatalogProblem.cursor();
      Cursor cursor = mapper.treeToValue(node, Cursor.class);
      int size = resource.equals("cards") ? 2 : 1;
      if (!cursor.resource().equals(resource)
          || !cursor.filter_hash().equals(fingerprint(query))
          || !cursor.sort().equals(query.sort())
          || cursor.limit() != query.limit()
          || !cursor.catalog_snapshot_id().matches("[a-z0-9][a-z0-9-]{0,95}")
          || (query.snapshot() != null && !cursor.catalog_snapshot_id().equals(query.snapshot()))
          || cursor.last_key().size() != size) throw CatalogProblem.cursor();
      if (!cursor
          .last_key()
          .getLast()
          .matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))
        throw CatalogProblem.cursor();
      if (size == 2
          && (cursor.last_key().getFirst().isEmpty()
              || cursor.last_key().getFirst().length() > 512
              || !NameKey.normalize(cursor.last_key().getFirst())
                  .equals(cursor.last_key().getFirst()))) throw CatalogProblem.cursor();
      return cursor;
    } catch (IllegalArgumentException | tools.jackson.core.JacksonException error) {
      throw CatalogProblem.cursor();
    }
  }
}
