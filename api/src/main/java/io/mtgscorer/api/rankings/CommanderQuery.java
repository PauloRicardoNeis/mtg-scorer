package io.mtgscorer.api.rankings;

import io.mtgscorer.api.catalog.CatalogQuery;
import io.mtgscorer.api.error.CatalogProblem;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Authoritative HTTP bounds for commander rankings. Format, search, colors, paging and the pinned
 * run share the card rankings' bounds; the orderings and the minimum decks are their own. {@code
 * format} stays null when absent.
 */
public record CommanderQuery(
    String format,
    String q,
    List<String> colors,
    int minDecks,
    String sort,
    String order,
    int limit,
    int offset,
    String scoreRun) {
  /** TopDeck's EDH events are competitive Commander, the format with the most commanders. */
  public static final String DEFAULT_FORMAT = "EDH";

  /**
   * Orderings over stored values; "decks" is also the rank, "movement" the places gained since the
   * previous run.
   */
  public static final List<String> SORTS =
      List.of("decks", "name", "win_rate", "top_cut_lift", "trend", "movement");

  /** The most decks a minimum may ask for; more than any format's run has. */
  public static final int MAX_MIN_DECKS = 100_000;

  public static final Set<String> PARAMETERS =
      Set.of(
          "format", "q", "color", "min_decks", "sort", "order", "limit", "offset", "score_run_id");

  public static CommanderQuery parse(Map<String, List<String>> input) {
    CatalogQuery.validateKeys(input, PARAMETERS);
    Map<String, List<String>> shared = new HashMap<>(input);
    String sort = shared.containsKey("sort") ? shared.remove("sort").getFirst() : "decks";
    if (!SORTS.contains(sort)) throw CatalogProblem.query("Invalid sort.");
    // A small sample can lead a win-rate or top-cut ordering; a minimum leaves it out.
    int minDecks = 1;
    if (shared.containsKey("min_decks")) {
      String value = shared.remove("min_decks").getFirst();
      if (!value.matches("[0-9]{1,6}")
          || Integer.parseInt(value) < 1
          || Integer.parseInt(value) > MAX_MIN_DECKS)
        throw CatalogProblem.query("Minimum decks must be between 1 and 100000.");
      minDecks = Integer.parseInt(value);
    }
    RankingQuery common = RankingQuery.parse(shared);
    // Every ordering defaults to descending except name, which reads A to Z.
    String order =
        input.containsKey("order") ? common.order() : sort.equals("name") ? "asc" : "desc";
    return new CommanderQuery(
        common.format(),
        common.q(),
        common.colors(),
        minDecks,
        sort,
        order,
        common.limit(),
        common.offset(),
        common.scoreRun());
  }
}
