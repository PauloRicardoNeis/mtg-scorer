package dev.mtgscorer.api.catalog;

import java.util.List;

public record CardCatalog(
        String contractVersion,
        String catalogKind,
        CatalogSnapshot snapshot,
        List<PublishedCardScore> cards) {

    public CardCatalog {
        cards = List.copyOf(cards);
    }
}
