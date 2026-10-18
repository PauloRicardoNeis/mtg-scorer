package io.mtgscorer.api.catalog;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Authoritative HTTP bounds and filter identity, independent of SQL and Spring. */
public record CatalogQuery(
    String q,
    List<String> sets,
    List<String> rarities,
    String game,
    String colorIdentity,
    List<String> colors,
    String type,
    String sort,
    int limit,
    String snapshot,
    String cursor) {
  public static final Set<String> RARITIES =
      Set.of("common", "uncommon", "rare", "mythic", "special", "bonus");
  public static final Set<String> GAMES = Set.of("paper", "arena", "mtgo");

  /** Card colors in WUBRG order; C selects known colorless cards. */
  public static final List<String> COLORS = List.of("W", "U", "B", "R", "G", "C");

  /** Card types matched on any face's type line, before its subtypes. */
  public static final Set<String> TYPES =
      Set.of("creature", "planeswalker", "instant", "sorcery", "artifact", "enchantment", "land");

  public static final Set<String> CARD_PARAMETERS =
      Set.of(
          "q",
          "set",
          "rarity",
          "game",
          "color_identity",
          "color",
          "type",
          "sort",
          "limit",
          "catalog_snapshot_id",
          "cursor");
  public static final Set<String> PRINTING_PARAMETERS =
      Set.of("set", "rarity", "game", "limit", "catalog_snapshot_id", "cursor");

  public static CatalogQuery parse(Map<String, List<String>> input, boolean printings) {
    validateKeys(input, printings ? PRINTING_PARAMETERS : CARD_PARAMETERS);
    String q = scalar(input, "q");
    if (q != null) {
      if (q.length() > 100) throw CatalogProblem.query("Search text exceeds 100 characters.");
      q = NameKey.normalize(q);
      if (q.isEmpty()) q = null;
    }
    List<String> sets = repeated(input, "set", 32);
    if (sets.stream().anyMatch(s -> !s.matches("[a-z0-9]{2,8}")))
      throw CatalogProblem.query("Invalid set code.");
    List<String> rarities = repeated(input, "rarity", 6);
    if (!RARITIES.containsAll(rarities)) throw CatalogProblem.query("Invalid rarity.");
    String game = scalar(input, "game");
    if (game != null && !GAMES.contains(game)) throw CatalogProblem.query("Invalid game.");
    String colors = scalar(input, "color_identity");
    if (colors != null) {
      if (!colors.matches("C|[WUBRG]{1,5}") || colors.chars().distinct().count() != colors.length())
        throw CatalogProblem.query("Invalid color identity.");
      if (!colors.equals("C")) {
        String selected = colors;
        colors =
            "WUBRG"
                .chars()
                .filter(c -> selected.indexOf(c) >= 0)
                .collect(StringBuilder::new, StringBuilder::appendCodePoint, StringBuilder::append)
                .toString();
      }
    }
    List<String> selected = repeated(input, "color", COLORS.size());
    if (!COLORS.containsAll(selected)) throw CatalogProblem.query("Invalid color.");
    List<String> anyColors = COLORS.stream().filter(selected::contains).toList();
    String type = scalar(input, "type");
    if (type != null && !TYPES.contains(type)) throw CatalogProblem.query("Invalid card type.");
    String sort = scalar(input, "sort");
    if (sort != null && !sort.equals("name_asc")) throw CatalogProblem.query("Invalid sort.");
    String size = scalar(input, "limit");
    int limit = 24;
    if (size != null) {
      if (!size.matches("[0-9]{1,3}"))
        throw CatalogProblem.query("Limit must be between 1 and 100.");
      limit = Integer.parseInt(size);
      if (limit < 1 || limit > 100) throw CatalogProblem.query("Limit must be between 1 and 100.");
    }
    String snapshot = scalar(input, "catalog_snapshot_id");
    if (snapshot != null && !snapshot.matches("[a-z0-9][a-z0-9-]{0,95}"))
      throw CatalogProblem.query("Invalid snapshot ID.");
    return new CatalogQuery(
        q,
        sets,
        rarities,
        game,
        colors,
        anyColors,
        type,
        printings ? "scryfall_id_asc" : "name_asc",
        limit,
        snapshot,
        scalar(input, "cursor"));
  }

  public static void validateKeys(Map<String, List<String>> input, Set<String> allowed) {
    if (!allowed.containsAll(input.keySet()))
      throw CatalogProblem.query("Unknown query parameter.");
    for (var entry : input.entrySet()) {
      if (!Set.of("set", "rarity", "color").contains(entry.getKey())
          && entry.getValue().size() != 1)
        throw CatalogProblem.query("Duplicate scalar parameter.");
    }
  }

  private static String scalar(Map<String, List<String>> input, String key) {
    return input.containsKey(key) ? input.get(key).getFirst() : null;
  }

  private static List<String> repeated(Map<String, List<String>> input, String key, int maximum) {
    List<String> values = input.getOrDefault(key, List.of());
    if (values.size() > maximum) throw CatalogProblem.query("Too many " + key + " filters.");
    return values.stream().distinct().sorted().toList();
  }
}
