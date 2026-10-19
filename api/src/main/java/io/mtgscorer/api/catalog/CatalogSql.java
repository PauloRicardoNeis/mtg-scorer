package io.mtgscorer.api.catalog;

/**
 * SQL fragments over published catalog views, shared by every module that shows catalog cards. Each
 * expects a published card aliased {@code c} and, for printings, a printing aliased {@code p}.
 */
public final class CatalogSql {
  private CatalogSql() {}

  // Both list previews and printing details use the same snapshot-scoped image projection.
  public static final String PRINTING_JSON =
      """
      (to_jsonb(p)-'catalog_snapshot_id'-'oracle_id'-'retrieved_at'-'raw_snapshot_ref'-'raw_sha256')
      || jsonb_build_object('images',
        (SELECT coalesce(jsonb_agg(jsonb_build_object(
          'face_index',nullif(i.image_slot,-1),'source_uri',i.source_uri,'artist',i.artist)
          ORDER BY i.image_slot),'[]'::jsonb)
         FROM catalog.published_catalog_printing_image i
         WHERE i.catalog_snapshot_id=p.catalog_snapshot_id AND i.scryfall_id=p.scryfall_id))
      """;

  // Double-faced cards may lack a card-level cost or type line; show the front face's
  // cost and every face's type line instead.
  public static final String SHOWN =
      """
      (SELECT coalesce(c.mana_cost,
         (SELECT f.mana_cost FROM catalog.published_catalog_face f
          WHERE f.catalog_snapshot_id=c.catalog_snapshot_id AND f.oracle_id=c.oracle_id
          ORDER BY f.face_index LIMIT 1)) mana_cost,
       coalesce(c.type_line,
         (SELECT string_agg(f.type_line,' // ' ORDER BY f.face_index) FROM catalog.published_catalog_face f
          WHERE f.catalog_snapshot_id=c.catalog_snapshot_id AND f.oracle_id=c.oracle_id)) type_line)
      """;

  /** The order that picks one representative printing: English first, then the newest. */
  public static final String PREVIEW_ORDER =
      "ORDER BY (p.language='en') DESC,p.released_on DESC NULLS LAST,p.scryfall_id LIMIT 1";

  /** "creature" → a match for Creature before the subtype dash on any face of a type line. */
  public static String typePattern(String type) {
    return "(^|//)[^—/]*\\m" + Character.toUpperCase(type.charAt(0)) + type.substring(1) + "\\M";
  }
}
