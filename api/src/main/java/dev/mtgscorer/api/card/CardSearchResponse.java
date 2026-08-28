package dev.mtgscorer.api.card;

import java.util.List;

import dev.mtgscorer.api.catalog.CatalogSnapshot;
import dev.mtgscorer.api.catalog.PublishedCardScore;

public record CardSearchResponse(
        String contractVersion,
        String catalogKind,
        CatalogSnapshot snapshot,
        int total,
        List<PublishedCardScore> cards) {

    public CardSearchResponse {
        cards = List.copyOf(cards);
    }
}
