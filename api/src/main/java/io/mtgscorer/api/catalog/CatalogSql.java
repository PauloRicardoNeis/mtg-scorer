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

  /**
   * A printing's sort key, original first: English, then paper, then the oldest release and the
   * lowest collector number. A promo set ("p" + a set code) counts after the set it promotes when
   * the card is in both, since prerelease promos are dated before their set; a release dated only
   * to its year (1 January) counts from the end of that year. Every part is non-null, so the key
   * also works as a keyset row value.
   */
  public static final String ORIGINAL_FIRST =
      """
      p.language<>'en',NOT('paper'=ANY(p.games)),
      p.set_code LIKE 'p%' AND EXISTS(SELECT FROM catalog.published_catalog_printing o
        WHERE o.catalog_snapshot_id=p.catalog_snapshot_id AND o.oracle_id=p.oracle_id
        AND 'p'||o.set_code=p.set_code),
      coalesce(p.released_on+CASE WHEN extract(doy FROM p.released_on)=1 THEN 364 ELSE 0 END,
        'infinity'),
      coalesce(substring(p.collector_number FROM '^[0-9]+')::numeric,'NaN'),
      p.collector_number,p.scryfall_id""";

  /** The order that picks one representative printing: the original. */
  public static final String PREVIEW_ORDER = "ORDER BY " + ORIGINAL_FIRST + " LIMIT 1";

  /** A match for {@code :q} in any of the card's names and face names, as name keys. */
  public static final String NAME_MATCH =
      "EXISTS(SELECT FROM catalog.published_catalog_alias a"
          + " WHERE a.catalog_snapshot_id=c.catalog_snapshot_id AND a.oracle_id=c.oracle_id"
          + " AND strpos(a.alias_key,:q)>0)";

  /** A match for {@code :q} in the card's or any face's column, ignoring case. */
  private static String anyFace(String column) {
    return "(strpos(lower(c."
        + column
        + "),lower(:q))>0 OR EXISTS(SELECT FROM catalog.published_catalog_face f"
        + " WHERE f.catalog_snapshot_id=c.catalog_snapshot_id AND f.oracle_id=c.oracle_id"
        + " AND strpos(lower(f."
        + column
        + "),lower(:q))>0))";
  }

  /**
   * A match for {@code :q} in the part of the card that {@code in} names: its names, its type line,
   * its rules text, or any of them. {@code names} is the name match, so a module can add a name of
   * its own, as rankings do for cards outside the catalog.
   */
  public static String search(String in, String names) {
    return switch (in) {
      case "name" -> names;
      case "type" -> anyFace("type_line");
      case "text" -> anyFace("oracle_text");
      default ->
          "(" + names + " OR " + anyFace("type_line") + " OR " + anyFace("oracle_text") + ")";
    };
  }

  /** "creature" → a match for Creature before the subtype dash on any face of a type line. */
  public static String typePattern(String type) {
    return "(^|//)[^—/]*\\m" + Character.toUpperCase(type.charAt(0)) + type.substring(1) + "\\M";
  }
}
