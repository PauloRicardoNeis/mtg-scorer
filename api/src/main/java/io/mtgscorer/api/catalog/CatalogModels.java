package io.mtgscorer.api.catalog;

import io.swagger.v3.oas.annotations.media.Schema;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

public final class CatalogModels {
  private CatalogModels() {}

  public record CardSummary(
      UUID oracle_id,
      String name,
      String layout,
      @Schema(types = {"array", "null"}) List<String> color_identity,
      @Schema(minimum = "1") long eligible_printing_count) {}

  public record CardPage(
      String catalog_snapshot_id,
      List<CardSummary> items,
      @Schema(types = {"string", "null"}) String next_cursor) {}

  public record Face(
      int face_index,
      String name,
      @Schema(types = {"string", "null"}) String mana_cost,
      @Schema(types = {"string", "null"}) String oracle_text,
      @Schema(types = {"string", "null"}) String type_line,
      @Schema(types = {"array", "null"}) List<String> colors) {}

  public record CardDetail(
      String catalog_snapshot_id,
      UUID oracle_id,
      String name,
      String layout,
      @Schema(types = {"string", "null"}) String mana_cost,
      @Schema(types = {"number", "null"}) Double mana_value,
      @Schema(types = {"string", "null"}) String oracle_text,
      @Schema(types = {"string", "null"}) String type_line,
      @Schema(types = {"array", "null"}) List<String> colors,
      @Schema(types = {"array", "null"}) List<String> color_identity,
      List<Face> faces) {}

  public record Printing(
      UUID scryfall_id,
      String set_code,
      String set_name,
      String collector_number,
      String rarity,
      @Schema(
              types = {"string", "null"},
              format = "date")
          LocalDate released_on,
      String language,
      List<String> games,
      String source_uri) {}

  public record PrintingPage(
      String catalog_snapshot_id,
      UUID oracle_id,
      List<Printing> items,
      @Schema(types = {"string", "null"}) String next_cursor) {}
}
