package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;

import io.mtgscorer.api.catalog.CatalogSql;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;
import tools.jackson.databind.ObjectMapper;

/**
 * Cards across the active runs of several formats, by the constructed score. Each format ranks its
 * own scored cards; a card a format did not rank has no cell there.
 */
@Repository
class CompareRepository {
  static final String METHOD = "constructed-score";

  private final NamedParameterJdbcTemplate jdbc;
  private final ObjectMapper mapper;

  CompareRepository(NamedParameterJdbcTemplate jdbc, ObjectMapper mapper) {
    this.jdbc = jdbc;
    this.mapper = mapper;
  }

  /** Every format whose active run has a constructed score. */
  List<CompareFormat> formats() {
    return jdbc.query(
        "SELECT a.format_name,a.score_run_id,"
            + "coalesce((r.summary->'cohort'->'totals'->>'decks')::int,0) decks,"
            + "(r.summary->'cohort'->'rules'->>'players_per_game')::int players_per_game"
            + " FROM scores.active_score_run a JOIN scores.published_score_run r USING(score_run_id)"
            + " WHERE EXISTS(SELECT FROM scores.published_score_run_method m"
            + " WHERE m.score_run_id=a.score_run_id AND m.method_id=:method)"
            + " ORDER BY a.format_name",
        Map.of("method", METHOD),
        (row, index) ->
            new CompareFormat(
                row.getString("format_name"),
                row.getString("score_run_id"),
                row.getInt("decks"),
                row.getObject("players_per_game", Integer.class)));
  }

  private String filtered(List<String> runs, CompareQuery query, Map<String, Object> args) {
    args.put("runs", String.join(",", runs));
    args.put("method", METHOD);
    args.put("compared", runs.size());
    List<String> where = new ArrayList<>();
    if (query.q() != null) {
      where.add(
          "(strpos(lower(x.name),:q)>0 OR EXISTS(SELECT FROM catalog.published_catalog_alias a"
              + " WHERE a.catalog_snapshot_id=c.catalog_snapshot_id AND a.oracle_id=c.oracle_id"
              + " AND strpos(a.alias_key,:q)>0))");
      args.put("q", query.q());
    }
    if (!query.colors().isEmpty()) {
      List<String> any = new ArrayList<>();
      List<String> chromatic = query.colors().stream().filter(c -> !c.equals("C")).toList();
      if (!chromatic.isEmpty()) {
        any.add("c.colors && string_to_array(:anyColors,',')");
        args.put("anyColors", String.join(",", chromatic));
      }
      if (query.colors().contains("C")) any.add("c.colors='{}'");
      where.add("(" + String.join(" OR ", any) + ")");
    }
    if (query.every()) where.add("x.ranked_in=:compared");
    return """
         FROM (SELECT oracle_id,min(name) name,count(*)::int ranked_in,
           (array_agg(format_name ORDER BY score DESC NULLS LAST,format_name))[1] best_format,
           max(score) best_score,
           jsonb_object_agg(format_name,jsonb_build_object('rank',ranking,'score',score,
             'win_rate_delta',win_rate_delta,'share',share,'top_cut_lift',top_cut_lift,
             'share_delta',share_delta)) formats
          FROM (SELECT r.format_name,k.oracle_id,k.name,s.value score,
              rank() OVER (PARTITION BY r.format_name ORDER BY s.value DESC NULLS LAST) ranking,
              k.win_rate_delta,k.deck_count::float8/r.decks share,k.top_cut_lift,k.share_delta
            -- Each run's deck total is read from its summary once, not once per card:
            -- OFFSET 0 keeps the planner from inlining the subquery into the join.
            FROM (SELECT score_run_id,format_name,
                greatest(coalesce((summary->'cohort'->'totals'->>'decks')::int,0),1) decks
              FROM scores.published_score_run
              WHERE score_run_id = ANY(string_to_array(:runs,',')) OFFSET 0) r
            JOIN scores.published_score_run_card k ON k.score_run_id=r.score_run_id AND k.scored
            JOIN scores.published_card_score s ON s.score_run_id=k.score_run_id
              AND s.oracle_id=k.oracle_id AND s.method_id=:method AND s.output='score') cells
          GROUP BY oracle_id) x
         LEFT JOIN catalog.active_catalog ac ON true
         LEFT JOIN catalog.published_catalog_card c
           ON c.catalog_snapshot_id=ac.catalog_snapshot_id AND c.oracle_id=x.oracle_id"""
        + (where.isEmpty() ? "" : " WHERE " + String.join(" AND ", where));
  }

  /** "best", "count", "name" or a format's metric; unknown values sort last. */
  static String orderBy(CompareQuery query, Map<String, Object> args) {
    String direction = query.order().equals("asc") ? "ASC" : "DESC";
    return switch (query.sort()) {
      case "name" -> "x.name " + direction + ",x.oracle_id";
      case "count" ->
          "x.ranked_in " + direction + ",x.best_score DESC NULLS LAST,x.name,x.oracle_id";
      case "best" -> "x.best_score " + direction + " NULLS LAST,x.name,x.oracle_id";
      default -> {
        args.put("sortFormat", query.sortFormat());
        args.put("sortKey", CompareQuery.METRICS.get(query.sortMetric()));
        yield "(x.formats->:sortFormat->>:sortKey)::float8 "
            + direction
            + " NULLS LAST,x.name,x.oracle_id";
      }
    };
  }

  long count(List<String> runs, CompareQuery query) {
    Map<String, Object> args = new HashMap<>();
    return jdbc.queryForObject("SELECT count(*) " + filtered(runs, query, args), args, Long.class);
  }

  List<ComparedCard> page(List<String> runs, CompareQuery query) {
    Map<String, Object> args = new HashMap<>();
    String from = filtered(runs, query, args);
    args.put("limit", query.limit());
    args.put("offset", query.offset());
    // Card details are looked up for the page only, after ordering and limiting.
    String sql =
        "SELECT jsonb_build_object('oracle_id',x.oracle_id,'name',x.name,"
            + "'mana_cost',shown.mana_cost,'type_line',shown.type_line,"
            + "'color_identity',to_jsonb(c.color_identity),'ranked_in',x.ranked_in,"
            + "'best_format',x.best_format,'best_score',x.best_score,'formats',x.formats)::text"
            + " FROM (SELECT x.*,c.catalog_snapshot_id shown_snapshot "
            + from
            + " ORDER BY "
            + orderBy(query, args)
            + " LIMIT :limit OFFSET :offset) x"
            + " LEFT JOIN catalog.published_catalog_card c"
            + " ON c.catalog_snapshot_id=x.shown_snapshot AND c.oracle_id=x.oracle_id"
            + " LEFT JOIN LATERAL "
            + CatalogSql.SHOWN
            + " shown ON true ORDER BY "
            + orderBy(query, args);
    return jdbc.query(
        sql, args, (row, index) -> mapper.readValue(row.getString(1), ComparedCard.class));
  }
}
