package io.mtgscorer.api.rankings;

import io.mtgscorer.api.catalog.CatalogQuery;
import io.mtgscorer.api.catalog.NameKey;
import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Authoritative HTTP bounds for ranking requests. {@code format} and {@code method} stay null when
 * absent so the service can tell a default from an explicit choice.
 */
public record RankingQuery(
    String format,
    String method,
    String q,
    String type,
    List<String> colors,
    String sort,
    String order,
    String view,
    int limit,
    int offset,
    String scoreRun) {
  public static final String DEFAULT_FORMAT = "Modern";
  public static final String DEFAULT_METHOD = "constructed-score";

  /** Without an explicit method, the first of these the run has; else the run's first. */
  public static final List<String> PREFERRED_METHODS = List.of(DEFAULT_METHOD, "max-ratio");

  public static final int DEFAULT_LIMIT = 25;
  public static final int MAX_OFFSET = 10_000;

  /**
   * Orderings over stored values; "score" is the selected method's first output and "movement" the
   * places gained since the previous run.
   */
  public static final List<String> SORTS =
      List.of(
          "score", "decks", "top_cuts", "name", "win_rate", "top_cut_lift", "trend", "movement");

  /** Every ordering defaults to descending except name, which reads A to Z. */
  public static final List<String> ORDERS = List.of("asc", "desc");

  /** Risers gained places since the previous run, fallers lost them. */
  public static final List<String> VIEWS = List.of("all", "risers", "fallers");

  public static final Set<String> PARAMETERS =
      Set.of(
          "format",
          "method",
          "q",
          "type",
          "color",
          "sort",
          "order",
          "view",
          "limit",
          "offset",
          "score_run_id");

  public static RankingQuery parse(Map<String, List<String>> input) {
    CatalogQuery.validateKeys(input, PARAMETERS);
    String format = scalar(input, "format");
    if (format != null && !format.matches("[A-Za-z0-9][A-Za-z0-9 /.-]{0,39}"))
      throw CatalogProblem.query("Invalid format.");
    String method = scalar(input, "method");
    if (method != null && !method.matches("[a-z0-9][a-z0-9-]{0,63}"))
      throw CatalogProblem.query("Invalid score method.");
    String q = scalar(input, "q");
    if (q != null) {
      if (q.length() > 100) throw CatalogProblem.query("Search text exceeds 100 characters.");
      q = NameKey.normalize(q);
      if (q.isEmpty()) q = null;
    }
    String type = scalar(input, "type");
    if (type != null && !CatalogQuery.TYPES.contains(type))
      throw CatalogProblem.query("Invalid card type.");
    List<String> selected = input.getOrDefault("color", List.of());
    if (selected.size() > CatalogQuery.COLORS.size())
      throw CatalogProblem.query("Too many color filters.");
    if (!CatalogQuery.COLORS.containsAll(selected)) throw CatalogProblem.query("Invalid color.");
    List<String> colors = CatalogQuery.COLORS.stream().filter(selected::contains).toList();
    String sort = scalar(input, "sort");
    if (sort == null) sort = "score";
    else if (!SORTS.contains(sort)) throw CatalogProblem.query("Invalid sort.");
    String order = scalar(input, "order");
    if (order == null) order = sort.equals("name") ? "asc" : "desc";
    else if (!ORDERS.contains(order)) throw CatalogProblem.query("Invalid order.");
    String view = scalar(input, "view");
    if (view == null) view = "all";
    else if (!VIEWS.contains(view)) throw CatalogProblem.query("Invalid view.");
    int limit = bounded(input, "limit", DEFAULT_LIMIT, 1, 100, "Limit must be between 1 and 100.");
    int offset = bounded(input, "offset", 0, 0, MAX_OFFSET, "Offset must be between 0 and 10000.");
    String scoreRun = scalar(input, "score_run_id");
    if (scoreRun != null && !scoreRun.matches("scores-[0-9a-f]{64}"))
      throw CatalogProblem.query("Invalid score run ID.");
    return new RankingQuery(
        format, method, q, type, colors, sort, order, view, limit, offset, scoreRun);
  }

  private static String scalar(Map<String, List<String>> input, String key) {
    return input.containsKey(key) ? input.get(key).getFirst() : null;
  }

  private static int bounded(
      Map<String, List<String>> input,
      String key,
      int fallback,
      int minimum,
      int maximum,
      String message) {
    String value = scalar(input, key);
    if (value == null) return fallback;
    if (!value.matches("[0-9]{1,5}")) throw CatalogProblem.query(message);
    int parsed = Integer.parseInt(value);
    if (parsed < minimum || parsed > maximum) throw CatalogProblem.query(message);
    return parsed;
  }
}
