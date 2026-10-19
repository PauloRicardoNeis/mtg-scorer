package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;

import io.mtgscorer.api.catalog.CatalogModels.Printing;
import io.mtgscorer.api.catalog.CatalogSql;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
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

  private static final Map<String, String> ORDER =
      Map.of(
          "score", "r.score DESC NULLS LAST,r.name,r.oracle_id",
          "decks", "r.deck_count DESC,r.name,r.oracle_id",
          "top_cuts", "r.top_cut_count DESC NULLS LAST,r.name,r.oracle_id",
          "name", "r.name,r.oracle_id");

  List<RankedFormat> activeFormats() {
    return jdbc.query(
        "SELECT a.format_name,a.source,a.score_run_id FROM scores.active_score_run a"
            + " JOIN scores.published_score_run r USING(score_run_id) ORDER BY a.format_name,a.source",
        Map.of(),
        (row, index) ->
            new RankedFormat(
                row.getString("format_name"),
                row.getString("source"),
                row.getString("score_run_id")));
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
        'methods',(SELECT jsonb_agg(jsonb_build_object('method_id',m.method_id,'method_version',m.method_version,
          'label',m.label,'description',m.description,'outputs',to_jsonb(m.outputs)) ORDER BY m.method_id)
          FROM scores.published_score_run_method m WHERE m.score_run_id=r.score_run_id)
      )::text FROM scores.published_score_run r WHERE r.score_run_id=:run
      """,
            Map.of("run", scoreRun),
            (row, index) -> mapper.readValue(row.getString(1), ScoreRunSummary.class))
        .stream()
        .findFirst();
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

  private String filtered(
      String scoreRun, String method, String output, RankingQuery query, Map<String, Object> args) {
    args.put("run", scoreRun);
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
    // Ranks are computed over every scored card before filters, so a filtered row keeps its place.
    return """
        FROM (SELECT k.*,s.value score,rank() OVER (ORDER BY s.value DESC NULLS LAST) ranking
          FROM scores.published_score_run_card k JOIN scores.published_card_score s
          ON s.score_run_id=k.score_run_id AND s.oracle_id=k.oracle_id
          WHERE k.score_run_id=:run AND k.scored AND s.method_id=:method AND s.output=:output) r
        LEFT JOIN catalog.active_catalog ac ON true
        LEFT JOIN catalog.published_catalog_card c
          ON c.catalog_snapshot_id=ac.catalog_snapshot_id AND c.oracle_id=r.oracle_id
        LEFT JOIN LATERAL """
        + CatalogSql.SHOWN
        + " shown ON true"
        + (where.isEmpty() ? "" : " WHERE " + String.join(" AND ", where));
  }

  long count(String scoreRun, String method, String output, RankingQuery query) {
    Map<String, Object> args = new HashMap<>();
    return jdbc.queryForObject(
        "SELECT count(*) " + filtered(scoreRun, method, output, query, args), args, Long.class);
  }

  List<RankedCard> page(String scoreRun, String method, String output, RankingQuery query) {
    Map<String, Object> args = new HashMap<>();
    String from = filtered(scoreRun, method, output, query, args);
    args.put("limit", query.limit());
    args.put("offset", query.offset());
    String sql =
        "SELECT r.ranking,r.oracle_id,r.name,r.score,r.deck_count,r.event_count,r.top_cut_count,"
            + "r.top_cut_known_decks,r.archetype_label,r.archetype_deck_count,r.labelled_deck_count,"
            + "shown.mana_cost,shown.type_line,c.color_identity,"
            + "(SELECT ("
            + CatalogSql.PRINTING_JSON
            + ")::text FROM catalog.published_catalog_printing p"
            + " WHERE p.catalog_snapshot_id=c.catalog_snapshot_id AND p.oracle_id=c.oracle_id "
            + CatalogSql.PREVIEW_ORDER
            + ") printing "
            + from
            + " ORDER BY "
            + ORDER.get(query.sort())
            + " LIMIT :limit OFFSET :offset";
    return jdbc.query(
        sql,
        args,
        (row, index) -> {
          String printing = row.getString("printing");
          return new RankedCard(
              row.getLong("ranking"),
              row.getObject("oracle_id", UUID.class),
              row.getString("name"),
              row.getObject("score", Double.class),
              row.getInt("deck_count"),
              row.getInt("event_count"),
              row.getObject("top_cut_count", Integer.class),
              row.getInt("top_cut_known_decks"),
              row.getString("archetype_label"),
              row.getInt("archetype_deck_count"),
              row.getInt("labelled_deck_count"),
              row.getString("mana_cost"),
              row.getString("type_line"),
              row.getArray("color_identity") == null
                  ? null
                  : List.of((String[]) row.getArray("color_identity").getArray()),
              printing == null ? null : mapper.readValue(printing, Printing.class));
        });
  }
}
