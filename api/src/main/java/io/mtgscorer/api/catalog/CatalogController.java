package io.mtgscorer.api.catalog;

import static io.mtgscorer.api.catalog.CatalogModels.*;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import java.util.Set;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping(value = "/api/v1/cards", produces = "application/json")
public class CatalogController {
  private final CatalogService catalog;

  public CatalogController(CatalogService catalog) {
    this.catalog = catalog;
  }

  @GetMapping
  @Operation(
      operationId = "searchCards",
      summary = "Search names and faces within a jointly eligible printing pool")
  public CardPage search(
      @Parameter(hidden = true) @RequestParam MultiValueMap<String, String> query) {
    return catalog.search(CatalogQuery.parse(query, false));
  }

  @GetMapping("/{oracle_id}")
  @Operation(operationId = "getCard", summary = "Get a card with every canonical face")
  public CardDetail detail(
      @PathVariable String oracle_id,
      @Parameter(hidden = true) @RequestParam MultiValueMap<String, String> query) {
    CatalogQuery.validateKeys(query, Set.of("catalog_snapshot_id"));
    return catalog.detail(oracle_id, query.getFirst("catalog_snapshot_id"));
  }

  @GetMapping("/{oracle_id}/printings")
  @Operation(operationId = "listPrintings", summary = "List jointly eligible printings for a card")
  public PrintingPage printings(
      @PathVariable String oracle_id,
      @Parameter(hidden = true) @RequestParam MultiValueMap<String, String> query) {
    return catalog.printings(oracle_id, CatalogQuery.parse(query, true));
  }
}
