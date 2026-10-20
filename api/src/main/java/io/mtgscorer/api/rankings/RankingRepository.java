package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;

import io.mtgscorer.api.catalog.CatalogSql;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;
import tools.jackson.databind.ObjectMapper;

/**
 * Bound queries against published score-run views. Ranks and orderings are SQL over stored values;
 * no score is computed here. Card details come from the active catalog when the card is in it.
 */
@Repository
class RankingRepository {
  private final NamedParameterJdbcTemplate jdbc;
  private final ObjectMapper mapper;

  RankingRepository(NamedParameterJdbcTemplate jdbc, ObjectMapper mapper) {
    this.jdbc = jdbc;
    this.mapper = mapper;
  }

  /** Score per dollar; null when either side is unknown. */
  private static final String VALUE = "r.score/pr.usd";

  /**
   * The stored value each sort orders by; ties fall back to name, then oracle id. Win rate orders
   * by its gap to the field: the same order within a format's run, and the only one an overall run
   * has, since win rates of one-on-one and multiplayer formats are not pooled.
   */
  private static final Map<String, String> ORDER =
      Map.of(
          "score", "r.score",
          "decks", "r.deck_count",
          "top_cuts", "r.top_cut_count",
          "name", "r.name",
          "win_rate", "r.win_rate_delta",
          "top_cut_lift", "r.top_cut_lift",
          "trend", "r.share_delta",
          "movement", "prev.ranking-r.ranking",
          "price", "pr.usd",
          "value", VALUE);

  static String orderBy(RankingQuery query) {
    String direction = query.order().equals("asc") ? "ASC" : "DESC";
    String column = ORDER.get(query.sort());
    return query.sort().equals("name")
        ? "r.name " + direction + ",r.oracle_id"
        : column + " " + direction + " NULLS LAST,r.name,r.oracle_id";
  }

  List<RankedFormat> activeFormats() {
    return jdbc.query(
        """
        SELECT a.format_name,a.source,a.score_run_id,
          coalesce((r.summary->'cohort'->'totals'->>'decks')::int,0) decks,
          (r.summary->'cohort'->'rules'->>'players_per_game')::int players_per_game
        FROM scores.active_score_run a JOIN scores.published_score_run r USING(score_run_id)
        ORDER BY a.format_name,a.source
        """,
        Map.of(),
        (row, index) ->
            new RankedFormat(
                row.getString("format_name"),
                row.getString("source"),
                row.getString("score_run_id"),
                row.getInt("decks"),
                row.getObject("players_per_game", Integer.class)));
  }

  Optional<ScoreRunSummary> run(String scoreRun) {
    return jdbc
        .query(
            """
      SELECT jsonb_build_object(
        'score_run_id',r.score_run_id,'source',r.source,'format_name',r.format_name,
        'window_starts_on',r.window_starts_on,'window_ends_before',r.window_ends_before,
        'published_at',r.published_at,'attribution',r.attribution,
        'events',r.summary->'cohort'->'totals'->'events','players',r.summary->'cohort'->'totals'->'players',
        'decks',r.summary->'cohort'->'totals'->'decks','top_cut_decks',r.summary->'cohort'->'totals'->'top_cut_decks',
        'scored_cards',r.summary->'population'->'scored_cards',
        'matches',r.summary->'cohort'->'totals'->'matches',
        'players_per_game',r.summary->'cohort'->'rules'->'players_per_game',
        'field_win_rate',r.summary->'cohort'->'performance'->'win_rate',
        'field_top_cut_rate',r.summary->'cohort'->'performance'->'top_cut_rate',
        'series_starts_on',r.summary->'cohort'->'series'->'starts_on',
        'series_period_days',r.summary->'cohort'->'series'->'period_days',
        'series_decks',r.summary->'cohort'->'series'->'decks',
        'methods',(SELECT jsonb_agg(jsonb_build_object('method_id',m.method_id,'method_version',m.method_version,
          'label',m.label,'description',m.description,'outputs',to_jsonb(m.outputs),
          'scored_cards',(SELECT count(*) FROM scores.published_card_score s
            WHERE s.score_run_id=m.score_run_id AND s.method_id=m.method_id
              AND s.output=m.outputs[1] AND s.value IS NOT NULL)) ORDER BY m.method_id)
          FROM scores.published_score_run_method m WHERE m.score_run_id=r.score_run_id),
        'components',(SELECT jsonb_agg(jsonb_build_object('format_name',c->>'format_name',
            'score_run_id',c->>'score_run_id','decks',(c->>'decks')::int,
            'weight',(c->>'weight')::float8) ORDER BY c->>'format_name')
          FROM jsonb_array_elements(r.summary->'components') c)
      )::text FROM scores.published_score_run r WHERE r.score_run_id=:run
      """,
            Map.of("run", scoreRun),
            (row, index) -> mapper.readValue(row.getString(1), ScoreRunSummary.class))
        .stream()
        .findFirst();
  }

  /**
   * The run rank changes are measured against: the latest published run of the same source and
   * format whose window ended earlier and that scored with the same method.
   */
  String previousRun(ScoreRunSummary run, String method) {
    return jdbc
        .queryForList(
            """
            SELECT r.score_run_id FROM scores.published_score_run r
            WHERE r.source=:source AND r.format_name=:format
              AND r.window_ends_before<:endsBefore AND r.score_run_id<>:run
              AND EXISTS(SELECT FROM scores.published_score_run_method m
                WHERE m.score_run_id=r.score_run_id AND m.method_id=:method)
            ORDER BY r.window_ends_before DESC,r.published_at DESC LIMIT 1
            """,
            Map.of(
                "source", run.source(),
                "format", run.format_name(),
                "endsBefore", run.window_ends_before(),
                "run", run.score_run_id(),
                "method", method),
            String.class)
        .stream()
        .findFirst()
        .orElse(null);
  }

  /**
   * The format's published windows: per source and window, the active run or else the latest
   * publication, latest end first and shorter windows before longer ones.
   */
  List<RunWindow> windows(String format) {
    return jdbc.query(
        """
        SELECT * FROM (SELECT DISTINCT ON (r.source,r.window_starts_on,r.window_ends_before)
            r.score_run_id,r.source,r.window_starts_on,r.window_ends_before,
            coalesce((r.summary->'cohort'->'totals'->>'decks')::int,0) decks,
            a.score_run_id IS NOT NULL active
          FROM scores.published_score_run r
          LEFT JOIN scores.active_score_run a USING(score_run_id)
          WHERE r.format_name=:format
          ORDER BY r.source,r.window_starts_on,r.window_ends_before,
            a.score_run_id IS NOT NULL DESC,r.published_at DESC) w
        ORDER BY window_ends_before DESC,window_ends_before-window_starts_on,source
        """,
        Map.of("format", format),
        (row, index) ->
            new RunWindow(
                row.getString("score_run_id"),
                row.getString("source"),
                row.getObject("window_starts_on", java.time.LocalDate.class),
                row.getObject("window_ends_before", java.time.LocalDate.class),
                row.getInt("decks"),
                row.getBoolean("active")));
  }

  /** The active catalog, if any; card details are optional for rankings. */
  String activeCatalog() {
    return jdbc
        .queryForList(
            "SELECT s.catalog_snapshot_id FROM catalog.active_catalog a"
                + " JOIN catalog.published_snapshot s USING(catalog_snapshot_id)",
            Map.of(),
            String.class)
        .stream()
        .findFirst()
        .orElse(null);
  }

  /** When the source last refreshed the active prices, if any are published. */
  OffsetDateTime pricesUpdatedAt() {
    return jdbc
        .queryForList(
            "SELECT s.source_updated_at FROM prices.active_price_snapshot a"
                + " JOIN prices.price_snapshot s USING(price_snapshot_id)",
            Map.of(),
            OffsetDateTime.class)
        .stream()
        .findFirst()
        .orElse(null);
  }

  int maxDeckCount(String scoreRun) {
    Integer most =
        jdbc.queryForObject(
            "SELECT max(deck_count) FROM scores.published_score_run_card"
                + " WHERE score_run_id=:run AND scored",
            Map.of("run", scoreRun),
            Integer.class);
    return most == null ? 0 : most;
  }

  /** One ranking of a run: each scored card's rank by the method's output. */
  private static String ranked(String run) {
    return "SELECT k.*,s.value score,rank() OVER (ORDER BY s.value DESC NULLS LAST) ranking"
        + " FROM scores.published_score_run_card k JOIN scores.published_card_score s"
        + " ON s.score_run_id=k.score_run_id AND s.oracle_id=k.oracle_id"
        + " WHERE k.score_run_id="
        + run
        + " AND k.scored AND s.method_id=:method AND s.output=:output";
  }

  private String filtered(
      String scoreRun,
      String previous,
      String method,
      String output,
      RankingQuery query,
      boolean byView,
      Map<String, Object> args) {
    args.put("run", scoreRun);
    args.put("previous", previous);
    args.put("method", method);
    args.put("output", output);
    List<String> where = new ArrayList<>();
    if (query.q() != null) {
      where.add(
          "(strpos(lower(r.name),:q)>0 OR EXISTS(SELECT FROM catalog.published_catalog_alias a"
              + " WHERE a.catalog_snapshot_id=c.catalog_snapshot_id AND a.oracle_id=c.oracle_id"
              + " AND strpos(a.alias_key,:q)>0))");
      args.put("q", query.q());
    }
    if (query.type() != null) {
      where.add("shown.type_line ~ :typePattern");
      args.put("typePattern", CatalogSql.typePattern(query.type()));
    }
    if (!query.colors().isEmpty()) {
      // Any selected color matches; cards outside the catalog have unknown colors and never do.
      List<String> any = new ArrayList<>();
      List<String> chromatic = query.colors().stream().filter(c -> !c.equals("C")).toList();
      if (!chromatic.isEmpty()) {
        any.add("c.colors && string_to_array(:anyColors,',')");
        args.put("anyColors", String.join(",", chromatic));
      }
      if (query.colors().contains("C")) any.add("c.colors='{}'");
      where.add("(" + String.join(" OR ", any) + ")");
    }
    if (byView && query.view().equals("risers")) where.add("prev.ranking>r.ranking");
    if (byView && query.view().equals("fallers")) where.add("prev.ranking<r.ranking");
    // Ranks are computed over every scored card before filters, so a filtered row keeps its place.
    return " FROM ("
        + ranked(":run")
        + ") r LEFT JOIN ("
        + ranked("CAST(:previous AS text)")
        + ") prev ON prev.oracle_id=r.oracle_id"
        + " LEFT JOIN catalog.active_catalog ac ON true"
        + " LEFT JOIN catalog.published_catalog_card c"
        + " ON c.catalog_snapshot_id=ac.catalog_snapshot_id AND c.oracle_id=r.oracle_id"
        + " LEFT JOIN LATERAL "
        + CatalogSql.SHOWN
        + " shown ON true"
        + " LEFT JOIN prices.active_price_snapshot ap ON true"
        + " LEFT JOIN prices.card_price pr"
        + " ON pr.price_snapshot_id=ap.price_snapshot_id AND pr.oracle_id=r.oracle_id"
        + (where.isEmpty() ? "" : " WHERE " + String.join(" AND ", where));
  }

  long count(String scoreRun, String previous, String method, String output, RankingQuery query) {
    Map<String, Object> args = new HashMap<>();
    return jdbc.queryForObject(
        "SELECT count(*)" + filtered(scoreRun, previous, method, output, query, true, args),
        args,
        Long.class);
  }

  /** Every view's count under the same filters, so the view tabs can show them all. */
  ViewCounts viewCounts(
      String scoreRun, String previous, String method, String output, RankingQuery query) {
    Map<String, Object> args = new HashMap<>();
    return jdbc.queryForObject(
        "SELECT count(*) total,count(*) FILTER (WHERE prev.ranking>r.ranking) risers,"
            + "count(*) FILTER (WHERE prev.ranking<r.ranking) fallers"
            + filtered(scoreRun, previous, method, output, query, false, args),
        args,
        (row, index) ->
            new ViewCounts(row.getLong("total"), row.getLong("risers"), row.getLong("fallers")));
  }

  /** An archetype's colors: the union of its core cards' color identities, in WUBRG order. */
  private static final String ARCHETYPES =
      """
      (SELECT coalesce(jsonb_agg(jsonb_build_object('label',a.label,'deck_count',a.deck_count,
        'colors',coalesce((SELECT jsonb_agg(x ORDER BY array_position(ARRAY['W','U','B','R','G'],x))
          FROM (SELECT DISTINCT unnest(cc.color_identity) x FROM scores.published_score_run_archetype ar
            JOIN catalog.published_catalog_card cc ON cc.catalog_snapshot_id=ac.catalog_snapshot_id
              AND cc.oracle_id=ANY(ar.core_cards)
            WHERE ar.score_run_id=a.score_run_id AND ar.label=a.label) colors),'[]'::jsonb))
        ORDER BY a.position),'[]'::jsonb)
       FROM scores.published_score_run_card_archetype a
       WHERE a.score_run_id=r.score_run_id AND a.oracle_id=r.oracle_id)""";

  /**
   * In an overall run, the card's stored score in each run it combines, best first; the run's
   * summary names each component's run, method and output. Null for a format's own run.
   */
  private static final String FORMATS =
      """
      (SELECT jsonb_agg(jsonb_build_object('format_name',comp->>'format_name','score',cs.value)
          ORDER BY cs.value DESC,comp->>'format_name')
       FROM jsonb_array_elements((SELECT summary->'components' FROM scores.published_score_run
         WHERE score_run_id=:run)) comp
       JOIN scores.published_card_score cs ON cs.score_run_id=comp->>'score_run_id'
         AND cs.method_id=comp->>'method_id' AND cs.output=comp->>'output'
         AND cs.oracle_id=r.oracle_id AND cs.value IS NOT NULL)""";

  List<RankedCard> page(
      String scoreRun, String previous, String method, String output, RankingQuery query) {
    Map<String, Object> args = new HashMap<>();
    String from = filtered(scoreRun, previous, method, output, query, true, args);
    args.put("limit", query.limit());
    args.put("offset", query.offset());
    String sql =
        "SELECT jsonb_build_object("
            + "'rank',r.ranking,'rank_change',prev.ranking-r.ranking,'oracle_id',r.oracle_id,"
            + "'name',r.name,'score',r.score,'deck_count',r.deck_count,'event_count',r.event_count,"
            + "'top_cut_count',r.top_cut_count,'top_cut_known_decks',r.top_cut_known_decks,"
            + "'archetype_label',r.archetype_label,'archetype_deck_count',r.archetype_deck_count,"
            + "'labelled_deck_count',r.labelled_deck_count,'win_rate',r.win_rate,"
            + "'win_rate_delta',r.win_rate_delta,'win_rate_ci95',r.win_rate_ci95,"
            + "'games',r.record_wins+r.record_losses+r.record_draws,'top_cut_lift',r.top_cut_lift,"
            + "'share_delta',r.share_delta,"
            + "'avg_copies',round(r.mainboard_copies::numeric/r.deck_count,2),"
            + "'series_decks',to_jsonb(r.series_decks),'archetypes',"
            + ARCHETYPES
            + ",'archetype_count',r.archetype_count,"
            + "'mana_cost',shown.mana_cost,'type_line',shown.type_line,"
            + "'color_identity',to_jsonb(c.color_identity),"
            + "'preview_printing',(SELECT "
            + CatalogSql.PRINTING_JSON
            + " FROM catalog.published_catalog_printing p"
            + " WHERE p.catalog_snapshot_id=c.catalog_snapshot_id AND p.oracle_id=c.oracle_id "
            + CatalogSql.PREVIEW_ORDER
            + "),'price_usd',pr.usd,'score_per_usd',"
            + VALUE
            + ",'formats',"
            + FORMATS
            + ")::text"
            + from
            + " ORDER BY "
            + orderBy(query)
            + " LIMIT :limit OFFSET :offset";
    return jdbc.query(
        sql, args, (row, index) -> mapper.readValue(row.getString(1), RankedCard.class));
  }
}
