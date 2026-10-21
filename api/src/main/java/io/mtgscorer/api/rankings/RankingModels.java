package io.mtgscorer.api.rankings;

import io.mtgscorer.api.catalog.CatalogModels.Printing;
import io.swagger.v3.oas.annotations.media.Schema;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Published score runs as Python wrote them; nothing here is computed by the API beyond ranks, the
 * change against the previous run, an average of stored counts and score per dollar. An overall run
 * is read like a format's run; its per-format grades are the stored scores of its components.
 */
public final class RankingModels {
  private RankingModels() {}

  public record ScoreMethod(
      String method_id,
      String method_version,
      String label,
      String description,
      List<String> outputs,
      @Schema(
              minimum = "0",
              description =
                  "Cards with a value for the method's first output; 0 when the method could not"
                      + " score this run, e.g. a signature score without archetype labels.")
          int scored_cards) {}

  public record ScoreRunSummary(
      String score_run_id,
      String source,
      String format_name,
      @Schema(format = "date") LocalDate window_starts_on,
      @Schema(format = "date", description = "Exclusive end of the cohort window.")
          LocalDate window_ends_before,
      OffsetDateTime published_at,
      String attribution,
      @Schema(minimum = "0") int events,
      @Schema(minimum = "0") int players,
      @Schema(minimum = "0", description = "Published decks in the cohort.") int decks,
      @Schema(minimum = "0") int top_cut_decks,
      @Schema(minimum = "0", description = "Cards the methods scored; ranks run up to this.")
          int scored_cards,
      @Schema(
              types = {"integer", "null"},
              description = "Games reported in standings; null for runs that did not record them.")
          Integer matches,
      @Schema(
              types = {"integer", "null"},
              description = "2 for one-on-one formats, 4 for pods; null for older runs.")
          Integer players_per_game,
      @Schema(
              types = {"number", "null"},
              description = "The field's match points per game, 0-1.")
          Double field_win_rate,
      @Schema(
              types = {"number", "null"},
              description = "Share of decks with a known result that made the top cut, 0-1.")
          Double field_top_cut_rate,
      @Schema(
              types = {"string", "null"},
              format = "date",
              description = "First day of the trend series.")
          LocalDate series_starts_on,
      @Schema(types = {"integer", "null"}) Integer series_period_days,
      @Schema(
              types = {"array", "null"},
              description = "The cohort's decks in each trend period, oldest first.")
          List<Integer> series_decks,
      List<ScoreMethod> methods,
      @Schema(
              types = {"array", "null"},
              description =
                  "The format runs an overall run combines, by format name; null for a format's"
                      + " own run.")
          List<RunComponent> components) {}

  public record RunComponent(
      String format_name,
      String score_run_id,
      @Schema(minimum = "1") int decks,
      @Schema(
              minimum = "0",
              maximum = "1",
              description = "How much the format counts in the overall grade, from its decklists.")
          double weight) {}

  /** A card's score in one format an overall run combines. */
  public record FormatGrade(
      String format_name, @Schema(minimum = "0", maximum = "100") double score) {}

  public record RankedFormat(
      String format_name,
      String source,
      String score_run_id,
      @Schema(minimum = "0") int decks,
      @Schema(types = {"integer", "null"}) Integer players_per_game,
      @Schema(
              minimum = "0",
              description =
                  "Commanders the run ranks; 0 in formats without commanders and in runs from"
                      + " before commanders were ranked.")
          int commanders) {}

  public record RunWindow(
      String score_run_id,
      String source,
      @Schema(format = "date") LocalDate window_starts_on,
      @Schema(format = "date", description = "Exclusive end of the cohort window.")
          LocalDate window_ends_before,
      @Schema(minimum = "0") int decks,
      @Schema(description = "Whether this is the run shown without a pinned run.") boolean active,
      @Schema(minimum = "0", description = "Commanders the run ranks.") int commanders) {}

  public record ArchetypeShare(
      String label,
      @Schema(minimum = "1", description = "The card's decks with this label.") int deck_count,
      @Schema(description = "Colors the archetype's core cards span, in WUBRG order.")
          List<String> colors) {}

  public record ViewCounts(
      @Schema(minimum = "0") long all,
      @Schema(minimum = "0") long risers,
      @Schema(minimum = "0") long fallers) {}

  public record RankedCard(
      @Schema(minimum = "1", description = "Position by the selected score among all scored cards.")
          long rank,
      @Schema(
              types = {"integer", "null"},
              description =
                  "Places gained since the previous run of this format; null without one or when"
                      + " the card was not ranked there.")
          Integer rank_change,
      UUID oracle_id,
      String name,
      @Schema(
              types = {"number", "null"},
              description = "The selected output; null when the method could not score the card.")
          Double score,
      @Schema(minimum = "1") int deck_count,
      @Schema(minimum = "1") int event_count,
      @Schema(
              types = {"integer", "null"},
              description = "Unknown when no deck with this card has a known top-cut result.")
          Integer top_cut_count,
      @Schema(minimum = "0") int top_cut_known_decks,
      @Schema(types = {"string", "null"}) String archetype_label,
      @Schema(minimum = "0") int archetype_deck_count,
      @Schema(minimum = "0") int labelled_deck_count,
      @Schema(
              types = {"number", "null"},
              description = "Match points per game of the card's decks, 0-1.")
          Double win_rate,
      @Schema(
              types = {"number", "null"},
              description = "Win rate minus the field's, as a fraction.")
          Double win_rate_delta,
      @Schema(
              types = {"number", "null"},
              description = "Half-width of the 95% interval.")
          Double win_rate_ci95,
      @Schema(
              types = {"integer", "null"},
              description = "Games behind the win rate.")
          Integer games,
      @Schema(
              types = {"number", "null"},
              description = "Top-cut conversion divided by the field's.")
          Double top_cut_lift,
      @Schema(
              types = {"number", "null"},
              description = "Meta share in the last trend period minus the first, as a fraction.")
          Double share_delta,
      @Schema(
              types = {"number", "null"},
              description = "Mainboard copies per deck.")
          Double avg_copies,
      @Schema(
              types = {"array", "null"},
              description = "The card's decks in each trend period, oldest first.")
          List<Integer> series_decks,
      @Schema(description = "Up to three archetypes playing the card, most decks first.")
          List<ArchetypeShare> archetypes,
      @Schema(
              types = {"integer", "null"},
              description = "Distinct archetype labels among the card's decks.")
          Integer archetype_count,
      @Schema(types = {"string", "null"}) String mana_cost,
      @Schema(types = {"string", "null"}) String type_line,
      @Schema(types = {"array", "null"}) List<String> color_identity,
      // Documented as nullable by RankingOpenApi: null when the card is not in the active catalog.
      Printing preview_printing,
      @Schema(
              types = {"number", "null"},
              description =
                  "Cheapest USD market price among the card's playable paper printings; null"
                      + " without one or without published prices.")
          Double price_usd,
      @Schema(
              types = {"number", "null"},
              description = "The selected output divided by the USD price; null without both.")
          Double score_per_usd,
      @Schema(
              types = {"array", "null"},
              description =
                  "In an overall run, the card's score in each format it combines, best first;"
                      + " null for a format's own run.")
          List<FormatGrade> formats) {}

  public record RankingPage(
      ScoreRunSummary score_run,
      String method_id,
      String output,
      List<RankedFormat> formats,
      @Schema(types = {"string", "null"}) String catalog_snapshot_id,
      @Schema(minimum = "0") long total,
      @Schema(minimum = "0") int offset,
      @Schema(minimum = "1") int limit,
      String sort,
      @Schema(allowableValues = {"asc", "desc"}) String order,
      @Schema(allowableValues = {"all", "risers", "fallers"}) String view,
      @Schema(description = "Matches per view under the same filters.") ViewCounts view_counts,
      @Schema(
              types = {"string", "null"},
              description = "The run rank changes are measured against.")
          String previous_score_run_id,
      @Schema(minimum = "0", description = "The most decks any scored card has in this run.")
          int max_deck_count,
      @Schema(
              description =
                  "Every published window of this format, latest end first, one run per source"
                      + " and window.")
          List<RunWindow> windows,
      @Schema(
              types = {"string", "null"},
              format = "date-time",
              description =
                  "When the source last refreshed the published prices; null without any.")
          OffsetDateTime prices_updated_at,
      List<RankedCard> items) {}

  /** A card that names a commander archetype, with its details from the active catalog. */
  public record CommanderCard(
      UUID oracle_id,
      @Schema(description = "As the run's decks most often spell it.") String name,
      @Schema(types = {"string", "null"}) String mana_cost,
      @Schema(types = {"string", "null"}) String type_line,
      @Schema(types = {"array", "null"}) List<String> color_identity,
      // Documented as nullable by CatalogOpenApi: null when the card is not in the active catalog.
      Printing preview_printing) {}

  /**
   * A commander, or a partner pair, as the archetype of the decks it leads. Its numbers describe
   * those decks the way a ranked card's describe the decks that play the card.
   */
  public record RankedCommander(
      @Schema(minimum = "1", description = "Position by decks among the run's commanders.")
          long rank,
      @Schema(
              types = {"integer", "null"},
              description =
                  "Places gained since the previous run of this format; null without one or when"
                      + " the commander was not ranked there.")
          Integer rank_change,
      @Schema(description = "The commander's name, or a partner pair's joined by \" + \".")
          String label,
      @Schema(description = "One card, or two for a partner pair, in label order.")
          List<CommanderCard> commanders,
      @Schema(
              types = {"array", "null"},
              description =
                  "The commanders' combined color identity in WUBRG order, empty when colorless;"
                      + " null when no commander is in the active catalog.")
          List<String> colors,
      @Schema(minimum = "1") int deck_count,
      @Schema(minimum = "1") int event_count,
      @Schema(
              types = {"integer", "null"},
              description = "Unknown when none of its decks has a known top-cut result.")
          Integer top_cut_count,
      @Schema(minimum = "0") int top_cut_known_decks,
      @Schema(
              types = {"number", "null"},
              description = "Match points per game of its decks, 0-1.")
          Double win_rate,
      @Schema(
              types = {"number", "null"},
              description = "Win rate minus the field's, as a fraction.")
          Double win_rate_delta,
      @Schema(
              types = {"number", "null"},
              description = "Half-width of the 95% interval.")
          Double win_rate_ci95,
      @Schema(
              types = {"integer", "null"},
              description = "Games behind the win rate.")
          Integer games,
      @Schema(
              types = {"number", "null"},
              description = "Top-cut conversion divided by the field's.")
          Double top_cut_lift,
      @Schema(
              types = {"number", "null"},
              description = "Meta share in the newer half of the trend series minus the older.")
          Double share_delta,
      @Schema(description = "Its decks in each trend period, oldest first.")
          List<Integer> series_decks,
      @Schema(minimum = "0", description = "Cards at least half of its decks play.")
          int core_card_count) {}

  public record CommanderPage(
      ScoreRunSummary score_run,
      List<RankedFormat> formats,
      @Schema(types = {"string", "null"}) String catalog_snapshot_id,
      @Schema(minimum = "0") long total,
      @Schema(minimum = "0") int offset,
      @Schema(minimum = "1") int limit,
      String sort,
      @Schema(allowableValues = {"asc", "desc"}) String order,
      @Schema(
              types = {"string", "null"},
              description = "The run rank changes are measured against.")
          String previous_score_run_id,
      @Schema(minimum = "0", description = "The most decks any commander has in this run.")
          int max_deck_count,
      @Schema(
              description =
                  "Every published window of this format, latest end first, one run per source"
                      + " and window.")
          List<RunWindow> windows,
      List<RankedCommander> items) {}

  public record CompareFormat(
      String format_name,
      String score_run_id,
      @Schema(minimum = "0") int decks,
      @Schema(types = {"integer", "null"}) Integer players_per_game,
      @Schema(
              minimum = "0",
              description =
                  "Cards the method scored in this run; 0 leaves the format out of the"
                      + " comparison, e.g. a signature score without archetype labels.")
          int scored_cards) {}

  public record CompareCell(
      @Schema(minimum = "1", description = "The card's rank in this format.") long rank,
      @Schema(
              types = {"number", "null"},
              description = "The method's score, 0-100.")
          Double score,
      @Schema(types = {"number", "null"}) Double win_rate_delta,
      @Schema(
              types = {"number", "null"},
              description = "Share of the format's decks, 0-1.")
          Double share,
      @Schema(types = {"number", "null"}) Double top_cut_lift,
      @Schema(types = {"number", "null"}) Double share_delta) {}

  public record ComparedCard(
      UUID oracle_id,
      String name,
      @Schema(types = {"string", "null"}) String mana_cost,
      @Schema(types = {"string", "null"}) String type_line,
      @Schema(types = {"array", "null"}) List<String> color_identity,
      @Schema(minimum = "1", description = "Compared formats that rank the card.") int ranked_in,
      @Schema(description = "The compared format where the card scores highest.")
          String best_format,
      @Schema(types = {"number", "null"}) Double best_score,
      @Schema(description = "One cell per compared format that ranks the card.")
          Map<String, CompareCell> formats) {}

  public record ComparePage(
      @Schema(
              allowableValues = {"constructed-score", "signature-score"},
              description = "The method every compared format is graded by.")
          String method_id,
      @Schema(description = "The compared formats.") List<CompareFormat> formats,
      @Schema(
              description =
                  "Every format whose active run published the method, compared or not; one"
                      + " the method scored no card in cannot be compared.")
          List<CompareFormat> available,
      @Schema(
              description =
                  "Every active run, comparable or not, such as the overall run; the format bar"
                      + " lists them.")
          List<RankedFormat> active_formats,
      @Schema(types = {"string", "null"}) String catalog_snapshot_id,
      @Schema(minimum = "0") long total,
      @Schema(minimum = "0") int offset,
      @Schema(minimum = "1") int limit,
      String sort,
      @Schema(allowableValues = {"asc", "desc"}) String order,
      boolean every,
      List<ComparedCard> items) {}
}
