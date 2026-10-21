package io.mtgscorer.api.decks;

import static io.mtgscorer.api.decks.DeckModels.*;

import io.mtgscorer.api.catalog.CatalogQuery;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import java.util.Set;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping(produces = "application/json")
public class DeckController {
  private final DeckService decks;

  public DeckController(DeckService decks) {
    this.decks = decks;
  }

  @GetMapping("/api/v1/cards/{oracle_id}/decks")
  @Operation(
      operationId = "listCardDecks",
      summary = "List the published tournament decks that played a card, newest event first")
  public CardDeckPage decks(
      @PathVariable String oracle_id,
      @Parameter(hidden = true) @RequestParam MultiValueMap<String, String> query) {
    return decks.decks(oracle_id, DeckQuery.parse(query));
  }

  @GetMapping("/api/v1/decks/{score_run_id}/{position}")
  @Operation(operationId = "getDeck", summary = "Get one published tournament deck and its list")
  public DeckDetail deck(
      @PathVariable String score_run_id,
      @PathVariable String position,
      @Parameter(hidden = true) @RequestParam MultiValueMap<String, String> query) {
    CatalogQuery.validateKeys(query, Set.of("catalog_snapshot_id"));
    return decks.deck(score_run_id, position, query.getFirst("catalog_snapshot_id"));
  }
}
