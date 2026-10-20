package io.mtgscorer.api.rankings;

import io.mtgscorer.api.catalog.CatalogModels.Printing;
import io.swagger.v3.oas.annotations.media.Schema;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** Published score runs as Python wrote them; nothing here is computed by the API. */
public final class RankingModels {
  private RankingModels() {}

  public record ScoreMethod(
      String method_id,
      String method_version,
      String label,
      String description,
      List<String> outputs) {}

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
      List<ScoreMethod> methods) {}

  public record RankedFormat(String format_name, String source, String score_run_id) {}

  public record RankedCard(
      @Schema(minimum = "1", description = "Position by the selected score among all scored cards.")
          long rank,
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
      @Schema(types = {"string", "null"}) String mana_cost,
      @Schema(types = {"string", "null"}) String type_line,
      @Schema(types = {"array", "null"}) List<String> color_identity,
      // Documented as nullable by RankingOpenApi: null when the card is not in the active catalog.
      Printing preview_printing) {}

  public record RankingPage(
      ScoreRunSummary score_run,
      String method_id,
      String output,
      List<RankedFormat> formats,
      @Schema(types = {"string", "null"}) String catalog_snapshot_id,
      @Schema(minimum = "0") long total,
      @Schema(minimum = "0") int offset,
      @Schema(minimum = "1") int limit,
      List<RankedCard> items) {}
}
