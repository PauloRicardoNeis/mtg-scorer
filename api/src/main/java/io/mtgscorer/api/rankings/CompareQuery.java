package io.mtgscorer.api.rankings;

import io.mtgscorer.api.catalog.CatalogQuery;
import io.mtgscorer.api.catalog.NameKey;
import io.mtgscorer.api.error.CatalogProblem;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Bounds for comparing cards across formats. {@code formats} is empty when absent so the service
 * can compare every format the method scored. {@code method} is one of the graded {@link #METHODS}.
 * {@code sort} is "best", "count", "name" or "{format}:{metric}".
 */
public record CompareQuery(
    List<String> formats,
    String method,
    String q,
    String in,
    List<String> colors,
    boolean every,
    String sort,
    String sortFormat,
    String sortMetric,
    String order,
    int limit,
    int offset) {
  public static final int DEFAULT_LIMIT = 50;
  public static final int MAX_FORMATS = 12;

  /**
   * Methods whose 0-100 percentiles grade cards alike in every format; the first is the default.
   */
  public static final List<String> METHODS = List.of("constructed-score", "signature-score");

  /** Per-format values a column can sort by, and the stored value each reads. */
  public static final Map<String, String> METRICS =
      Map.of(
          "grade", "score",
          "score", "score",
          "win_rate", "win_rate_delta",
          "share", "share",
          "top_cut_lift", "top_cut_lift",
          "trend", "share_delta");

  public static final Set<String> PARAMETERS =
      Set.of("format", "method", "q", "in", "color", "every", "sort", "order", "limit", "offset");

  /** Parameters that may repeat; every other one appears once. */
  static final Set<String> REPEATED = Set.of("format", "color");

  public static CompareQuery parse(Map<String, List<String>> input) {
    if (!PARAMETERS.containsAll(input.keySet()))
      throw CatalogProblem.query("Unknown query parameter.");
    for (var entry : input.entrySet())
      if (!REPEATED.contains(entry.getKey()) && entry.getValue().size() != 1)
        throw CatalogProblem.query("Duplicate scalar parameter.");
    List<String> formats = new ArrayList<>();
    for (String format : input.getOrDefault("format", List.of())) {
      if (!format.matches("[A-Za-z0-9][A-Za-z0-9 /.-]{0,39}"))
        throw CatalogProblem.query("Invalid format.");
      if (!formats.contains(format)) formats.add(format);
    }
    if (formats.size() > MAX_FORMATS) throw CatalogProblem.query("Too many formats.");
    String method = scalar(input, "method");
    if (method == null) method = METHODS.getFirst();
    else if (!METHODS.contains(method)) throw CatalogProblem.query("Invalid score method.");
    String q = scalar(input, "q");
    if (q != null) {
      if (q.length() > 100) throw CatalogProblem.query("Search text exceeds 100 characters.");
      q = NameKey.normalize(q);
      if (q.isEmpty()) q = null;
    }
    String in = CatalogQuery.searchIn(input);
    List<String> selected = input.getOrDefault("color", List.of());
    if (selected.size() > CatalogQuery.COLORS.size())
      throw CatalogProblem.query("Too many color filters.");
    if (!CatalogQuery.COLORS.containsAll(selected)) throw CatalogProblem.query("Invalid color.");
    List<String> colors = CatalogQuery.COLORS.stream().filter(selected::contains).toList();
    String every = scalar(input, "every");
    if (every != null && !every.equals("true") && !every.equals("false"))
      throw CatalogProblem.query("every must be true or false.");
    String sort = scalar(input, "sort");
    String sortFormat = null;
    String sortMetric = null;
    if (sort == null) sort = "best";
    else if (!List.of("best", "count", "name").contains(sort)) {
      int colon = sort.lastIndexOf(':');
      if (colon < 1 || !METRICS.containsKey(sort.substring(colon + 1)))
        throw CatalogProblem.query("Invalid sort.");
      sortFormat = sort.substring(0, colon);
      sortMetric = sort.substring(colon + 1);
      if (!sortFormat.matches("[A-Za-z0-9][A-Za-z0-9 /.-]{0,39}"))
        throw CatalogProblem.query("Invalid sort.");
    }
    String order = scalar(input, "order");
    if (order == null) order = sort.equals("name") ? "asc" : "desc";
    else if (!RankingQuery.ORDERS.contains(order)) throw CatalogProblem.query("Invalid order.");
    int limit = bounded(input, "limit", DEFAULT_LIMIT, 1, 200, "Limit must be between 1 and 200.");
    int offset =
        bounded(
            input, "offset", 0, 0, RankingQuery.MAX_OFFSET, "Offset must be between 0 and 10000.");
    return new CompareQuery(
        List.copyOf(formats),
        method,
        q,
        in,
        colors,
        "true".equals(every),
        sort,
        sortFormat,
        sortMetric,
        order,
        limit,
        offset);
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
