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
 * Bound queries over the published archetypes that commanders name. Ranks and orderings are SQL
 * over stored values; commander details come from the active catalog when the card is in it.
 */
@Repository
class CommanderRepository {
  private final NamedParameterJdbcTemplate jdbc;
  private final ObjectMapper mapper;

  CommanderRepository(NamedParameterJdbcTemplate jdbc, ObjectMapper mapper) {
    this.jdbc = jdbc;
    this.mapper = mapper;
  }

  /**
   * The stored value each sort orders by; ties fall back to the label, which is unique in a run.
   * Win rate orders by its gap to the field, as card rankings do.
   */
  private static final Map<String, String> ORDER =
      Map.of(
          "decks", "r.deck_count",
          "name", "r.label",
          "win_rate", "r.win_rate_delta",
          "top_cut_lift", "r.top_cut_lift",
          "trend", "r.share_delta",
          "movement", "prev.ranking-r.ranking");

  static String orderBy(CommanderQuery query) {
    String direction = query.order().equals("asc") ? "ASC" : "DESC";
    return query.sort().equals("name")
        ? "r.label " + direction
        : ORDER.get(query.sort()) + " " + direction + " NULLS LAST,r.label";
  }

  /** One run's commanders, each ranked by its decks; ties share a place. */
  private static String ranked(String run) {
    return "SELECT a.*,rank() OVER (ORDER BY a.deck_count DESC) ranking"
        + " FROM scores.published_score_run_archetype a WHERE a.score_run_id="
        + run
        + " AND cardinality(a.commanders)>0";
  }

  /**
   * The run rank changes are measured against: the latest published run of the same source and
   * format whose window ended earlier and that ranks commanders.
   */
  String previousRun(ScoreRunSummary run) {
    return jdbc
        .queryForList(
            """
            SELECT r.score_run_id FROM scores.published_score_run r
            WHERE r.source=:source AND r.format_name=:format
              AND r.window_ends_before<:endsBefore AND r.score_run_id<>:run
              AND EXISTS(SELECT FROM scores.published_score_run_archetype a
                WHERE a.score_run_id=r.score_run_id AND cardinality(a.commanders)>0)
            ORDER BY r.window_ends_before DESC,r.published_at DESC LIMIT 1
            """,
            Map.of(
                "source", run.source(),
                "format", run.format_name(),
                "endsBefore", run.window_ends_before(),
                "run", run.score_run_id()),
            String.class)
        .stream()
        .findFirst()
        .orElse(null);
  }

  int maxDeckCount(String scoreRun) {
    Integer most =
        jdbc.queryForObject(
            "SELECT max(deck_count) FROM scores.published_score_run_archetype"
                + " WHERE score_run_id=:run AND cardinality(commanders)>0",
            Map.of("run", scoreRun),
            Integer.class);
    return most == null ? 0 : most;
  }

  /**
   * The commanders' combined color identity; null when none of them is in the active catalog, so a
   * color filter never matches unknown colors.
   */
  private static final String IDENTITY =
      """
      (SELECT CASE WHEN count(*)>0
          THEN coalesce(array_agg(DISTINCT x) FILTER (WHERE x IS NOT NULL),'{}') END colors
       FROM catalog.published_catalog_card c LEFT JOIN LATERAL unnest(c.color_identity) x ON true
       WHERE c.catalog_snapshot_id=ac.catalog_snapshot_id AND c.oracle_id=ANY(r.commanders))""";

  private String filtered(
      String scoreRun, String previous, CommanderQuery query, Map<String, Object> args) {
    args.put("run", scoreRun);
    args.put("previous", previous);
    List<String> where = new ArrayList<>();
    if (query.minDecks() > 1) {
      where.add("r.deck_count>=:minDecks");
      args.put("minDecks", query.minDecks());
    }
    if (query.q() != null) {
      where.add(
          "(strpos(lower(r.label),:q)>0 OR EXISTS(SELECT FROM catalog.published_catalog_alias a"
              + " WHERE a.catalog_snapshot_id=ac.catalog_snapshot_id"
              + " AND a.oracle_id=ANY(r.commanders) AND strpos(a.alias_key,:q)>0))");
      args.put("q", query.q());
    }
    if (!query.colors().isEmpty()) {
      // Any selected color matches, as for cards; colorless is an identity of its own.
      List<String> any = new ArrayList<>();
      List<String> chromatic = query.colors().stream().filter(c -> !c.equals("C")).toList();
      if (!chromatic.isEmpty()) {
        any.add("idc.colors && string_to_array(:anyColors,',')");
        args.put("anyColors", String.join(",", chromatic));
      }
      if (query.colors().contains("C")) any.add("idc.colors='{}'");
      where.add("(" + String.join(" OR ", any) + ")");
    }
    // Ranks are computed over every commander before filters, so a filtered row keeps its place.
    return " FROM ("
        + ranked(":run")
        + ") r LEFT JOIN ("
        + ranked("CAST(:previous AS text)")
        + ") prev ON prev.label=r.label"
        + " LEFT JOIN catalog.active_catalog ac ON true"
        + " LEFT JOIN LATERAL "
        + IDENTITY
        + " idc ON true"
        + (where.isEmpty() ? "" : " WHERE " + String.join(" AND ", where));
  }

  long count(String scoreRun, String previous, CommanderQuery query) {
    Map<String, Object> args = new HashMap<>();
    return jdbc.queryForObject(
        "SELECT count(*)" + filtered(scoreRun, previous, query, args), args, Long.class);
  }

  /** Each commander in label order, named as the run names it, with its catalog details. */
  private static final String COMMANDERS =
      "(SELECT jsonb_agg(jsonb_build_object('oracle_id',k.oracle_id,'name',sc.name,"
          + "'mana_cost',shown.mana_cost,'type_line',shown.type_line,"
          + "'color_identity',to_jsonb(c.color_identity),'preview_printing',(SELECT "
          + CatalogSql.PRINTING_JSON
          + " FROM catalog.published_catalog_printing p"
          + " WHERE p.catalog_snapshot_id=c.catalog_snapshot_id AND p.oracle_id=c.oracle_id "
          + CatalogSql.PREVIEW_ORDER
          + ")) ORDER BY k.position)"
          + " FROM unnest(r.commanders) WITH ORDINALITY k(oracle_id,position)"
          + " JOIN scores.published_score_run_card sc"
          + " ON sc.score_run_id=r.score_run_id AND sc.oracle_id=k.oracle_id"
          + " LEFT JOIN catalog.published_catalog_card c"
          + " ON c.catalog_snapshot_id=ac.catalog_snapshot_id AND c.oracle_id=k.oracle_id"
          + " LEFT JOIN LATERAL "
          + CatalogSql.SHOWN
          + " shown ON true)";

  List<RankedCommander> page(String scoreRun, String previous, CommanderQuery query) {
    Map<String, Object> args = new HashMap<>();
    String from = filtered(scoreRun, previous, query, args);
    args.put("limit", query.limit());
    args.put("offset", query.offset());
    String sql =
        "SELECT jsonb_build_object("
            + "'rank',r.ranking,'rank_change',prev.ranking-r.ranking,'label',r.label,"
            + "'commanders',"
            + COMMANDERS
            + ",'colors',CASE WHEN idc.colors IS NOT NULL THEN coalesce((SELECT"
            + " jsonb_agg(x ORDER BY array_position(ARRAY['W','U','B','R','G'],x))"
            + " FROM unnest(idc.colors) x),'[]'::jsonb) END,"
            + "'deck_count',r.deck_count,'event_count',r.event_count,"
            + "'top_cut_count',r.top_cut_count,'top_cut_known_decks',r.top_cut_known_decks,"
            + "'win_rate',r.win_rate,'win_rate_delta',r.win_rate_delta,"
            + "'win_rate_ci95',r.win_rate_ci95,"
            + "'games',r.record_wins+r.record_losses+r.record_draws,'top_cut_lift',r.top_cut_lift,"
            + "'share_delta',r.share_delta,'series_decks',to_jsonb(r.series_decks),"
            + "'core_card_count',cardinality(r.core_cards))::text"
            + from
            + " ORDER BY "
            + orderBy(query)
            + " LIMIT :limit OFFSET :offset";
    return jdbc.query(
        sql, args, (row, index) -> mapper.readValue(row.getString(1), RankedCommander.class));
  }
}
