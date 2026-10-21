package io.mtgscorer.api.decks;

import io.mtgscorer.api.catalog.CatalogQuery;
import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Authoritative HTTP bounds for a card's decks. {@code format} and {@code scoreRun} stay null when
 * absent: the card's format with the most decks is shown then.
 */
public record DeckQuery(String format, String scoreRun, int limit, int offset) {
  public static final int DEFAULT_LIMIT = 20;
  public static final int MAX_LIMIT = 100;

  /** Past any run's decks: EDH's year of TopDeck events holds about 83,000. */
  public static final int MAX_OFFSET = 1_000_000;

  public static final Set<String> PARAMETERS = Set.of("format", "score_run_id", "limit", "offset");

  public static DeckQuery parse(Map<String, List<String>> input) {
    CatalogQuery.validateKeys(input, PARAMETERS);
    String format = scalar(input, "format");
    if (format != null && !format.matches("[A-Za-z0-9][A-Za-z0-9 /.-]{0,39}"))
      throw CatalogProblem.query("Invalid format.");
    String scoreRun = scalar(input, "score_run_id");
    if (scoreRun != null && !scoreRun.matches("scores-[0-9a-f]{64}"))
      throw CatalogProblem.query("Invalid score run ID.");
    int limit =
        bounded(input, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT, "Limit must be between 1 and 100.");
    int offset =
        bounded(input, "offset", 0, 0, MAX_OFFSET, "Offset must be between 0 and 1000000.");
    return new DeckQuery(format, scoreRun, limit, offset);
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
    if (!value.matches("[0-9]{1,7}")) throw CatalogProblem.query(message);
    int parsed = Integer.parseInt(value);
    if (parsed < minimum || parsed > maximum) throw CatalogProblem.query(message);
    return parsed;
  }
}
