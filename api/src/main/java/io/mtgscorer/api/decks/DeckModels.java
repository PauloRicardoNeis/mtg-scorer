package io.mtgscorer.api.decks;

import io.swagger.v3.oas.annotations.media.Schema;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/**
 * The decks behind a card's published counts, as Python wrote them: one run's cohort, newest event
 * first. Nothing here is computed by the API.
 */
public final class DeckModels {
  private DeckModels() {}

  /** A format whose active run lists the card's decks. */
  public record DeckFormat(
      String format_name,
      String source,
      String score_run_id,
      @Schema(minimum = "1", description = "The card's decks in the run.") int deck_count) {}

  public record DeckRun(
      String score_run_id,
      String source,
      String format_name,
      @Schema(format = "date") LocalDate window_starts_on,
      @Schema(format = "date", description = "Exclusive end of the cohort window.")
          LocalDate window_ends_before,
      String attribution) {}

  public record DeckEvent(
      String source_event_id,
      @Schema(
              types = {"string", "null"},
              description = "The event as its source names it; null when it named none.")
          String name,
      @Schema(
              types = {"string", "null"},
              format = "uri",
              description = "The source's page for the event.")
          String url,
      @Schema(format = "date") LocalDate occurred_on,
      @Schema(
              types = {"integer", "null"},
              minimum = "1")
          Integer players) {}

  public record CardDeck(
      @Schema(minimum = "0", description = "The deck's place in its run, newest event first.")
          int position,
      String source_deck_id,
      DeckEvent event,
      @Schema(
              types = {"string", "null"},
              description = "The source's label, or an unlabelled commander deck's commanders.")
          String archetype,
      @Schema(minimum = "1", description = "Mainboard copies of the card the deck plays.")
          int copies,
      @Schema(
              types = {"integer", "null"},
              minimum = "1",
              description = "Final standing when the source states one.")
          Integer final_rank,
      @Schema(
              types = {"boolean", "null"},
              description = "Null when unknown or when the event had no top cut.")
          Boolean made_top_cut,
      @Schema(
              types = {"integer", "null"},
              minimum = "0",
              description = "Match wins reported in standings; with losses and draws, or null.")
          Integer wins,
      @Schema(
              types = {"integer", "null"},
              minimum = "0")
          Integer losses,
      @Schema(
              types = {"integer", "null"},
              minimum = "0")
          Integer draws) {}

  /** One card of a deck's list, with its details when the catalog shown has it. */
  public record DeckCard(
      UUID oracle_id,
      String name,
      @Schema(minimum = "1") int copies,
      @Schema(types = {"string", "null"}) String mana_cost,
      @Schema(
              types = {"string", "null"},
              description = "Null when the catalog shown does not have the card.")
          String type_line,
      @Schema(types = {"number", "null"}) Double mana_value,
      @Schema(description = "Whether the catalog shown has the card, so it can be opened.")
          boolean in_catalog) {}

  /**
   * One published deck and its whole list. The lists are null for runs from before decks carried
   * them; the sideboard is also null when the source reported none, or not all of it.
   */
  public record DeckDetail(
      DeckRun run,
      @Schema(description = "The catalog the cards' details come from.") String catalog_snapshot_id,
      @Schema(minimum = "0", description = "The deck's place in its run, newest event first.")
          int position,
      String source_deck_id,
      DeckEvent event,
      @Schema(
              types = {"string", "null"},
              description = "The source's label, or an unlabelled commander deck's commanders.")
          String archetype,
      @Schema(
              types = {"integer", "null"},
              minimum = "1",
              description = "Final standing when the source states one.")
          Integer final_rank,
      @Schema(
              types = {"boolean", "null"},
              description = "Null when unknown or when the event had no top cut.")
          Boolean made_top_cut,
      @Schema(
              types = {"integer", "null"},
              minimum = "0",
              description = "Match wins reported in standings; with losses and draws, or null.")
          Integer wins,
      @Schema(
              types = {"integer", "null"},
              minimum = "0")
          Integer losses,
      @Schema(
              types = {"integer", "null"},
              minimum = "0")
          Integer draws,
      @Schema(
              types = {"array", "null"},
              description = "The cards the source listed as commanders, apart from the main deck.")
          List<DeckCard> commanders,
      @Schema(
              types = {"array", "null"},
              description = "The main deck, by name, without commanders.")
          List<DeckCard> mainboard,
      @Schema(
              types = {"array", "null"},
              description = "The sideboard, by name.")
          List<DeckCard> sideboard) {}

  public record CardDeckPage(
      UUID oracle_id,
      @Schema(description = "Active runs that list the card's decks, most decks first.")
          List<DeckFormat> formats,
      @Schema(description = "The run shown; null when no active run lists the card's decks.")
          DeckRun run,
      @Schema(minimum = "0", description = "The card's decks in the run.") long total,
      @Schema(minimum = "0") int offset,
      @Schema(minimum = "1") int limit,
      List<CardDeck> items) {}
}
