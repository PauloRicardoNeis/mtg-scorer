package dev.mtgscorer.api.card;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import dev.mtgscorer.api.catalog.PublishedCardScore;

@Validated
@RestController
@RequestMapping("/api/v1/cards")
public final class CardController {

    private final CardSearchService cardSearchService;

    public CardController(CardSearchService cardSearchService) {
        this.cardSearchService = cardSearchService;
    }

    @GetMapping
    public CardSearchResponse search(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(required = false) String set,
            @RequestParam(required = false) String rarity,
            @RequestParam(defaultValue = "BUILDAROUND") CardSort sort,
            @RequestParam(defaultValue = "24") @Min(1) @Max(100) int limit) {
        return cardSearchService.search(new CardSearchQuery(query, set, rarity, sort, limit));
    }

    @GetMapping("/{oracleId}")
    public ResponseEntity<PublishedCardScore> findByOracleId(@PathVariable String oracleId) {
        return cardSearchService
                .findByOracleId(oracleId)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }
}
