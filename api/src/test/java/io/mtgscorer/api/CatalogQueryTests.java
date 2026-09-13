package io.mtgscorer.api;

import static org.assertj.core.api.Assertions.*;

import io.mtgscorer.api.catalog.CatalogQuery;
import io.mtgscorer.api.catalog.CursorCodec;
import io.mtgscorer.api.catalog.NameKey;
import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

class CatalogQueryTests {
  @Test
  void normalizationAndCanonicalFilterIdentity() {
    assertThat(NameKey.normalize(" ＦＩＲＥ\t // Ice ")).isEqualTo("fire // ice");
    assertThat(NameKey.normalize("Æther 100%_ ")).isEqualTo("Æther 100%_");
    var query =
        CatalogQuery.parse(
            Map.of("set", List.of("m11", "2x2", "m11"), "color_identity", List.of("RU")), false);
    assertThat(query.sets()).containsExactly("2x2", "m11");
    assertThat(query.colorIdentity()).isEqualTo("UR");
  }

  @Test
  void rejectsUnknownDuplicateAndUnboundedInput() {
    for (var input :
        List.of(
            Map.of("score", List.of("100")),
            Map.of("q", List.of("a", "b")),
            Map.of("limit", List.of("0")),
            Map.of("color_identity", List.of("RR")),
            Map.of("rarity", List.of("legendary")))) {
      assertThatThrownBy(() -> CatalogQuery.parse(input, false)).isInstanceOf(CatalogProblem.class);
    }
    assertThatThrownBy(() -> CatalogQuery.parse(Map.of("q", List.of("face")), true))
        .isInstanceOf(CatalogProblem.class);
  }

  @Test
  void cursorBoundToResourceFiltersSnapshotSortAndLimit() {
    var codec = new CursorCodec(JsonMapper.builder().build());
    var query = CatalogQuery.parse(Map.of("set", List.of("m11"), "limit", List.of("2")), false);
    String encoded =
        codec.encode(
            "cards", "catalog-old", query, List.of("bolt", "00000000-0000-4000-8000-000000000001"));
    var continuation =
        CatalogQuery.parse(
            Map.of("set", List.of("m11"), "limit", List.of("2"), "cursor", List.of(encoded)),
            false);
    assertThat(codec.decode("cards", continuation).catalog_snapshot_id()).isEqualTo("catalog-old");
    assertThatThrownBy(() -> codec.decode("printings:other", continuation))
        .isInstanceOf(CatalogProblem.class);
    for (var mismatch :
        List.of(
            Map.of("cursor", List.of(encoded)),
            Map.of("set", List.of("2x2"), "limit", List.of("2"), "cursor", List.of(encoded)),
            Map.of(
                "set",
                List.of("m11"),
                "limit",
                List.of("2"),
                "catalog_snapshot_id",
                List.of("catalog-new"),
                "cursor",
                List.of(encoded)))) {
      assertThatThrownBy(() -> codec.decode("cards", CatalogQuery.parse(mismatch, false)))
          .isInstanceOf(CatalogProblem.class);
    }
  }
}
