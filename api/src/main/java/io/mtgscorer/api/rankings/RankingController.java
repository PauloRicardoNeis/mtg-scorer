package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping(value = "/api/v1/rankings", produces = "application/json")
public class RankingController {
  private final RankingService rankings;

  public RankingController(RankingService rankings) {
    this.rankings = rankings;
  }

  @GetMapping
  @Operation(
      operationId = "listRankings",
      summary = "Rank one format's scored cards by a published score method")
  public RankingPage list(
      @Parameter(hidden = true) @RequestParam MultiValueMap<String, String> query) {
    return rankings.rankings(RankingQuery.parse(query));
  }
}
