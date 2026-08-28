package dev.mtgscorer.api.catalog;

import java.util.List;

public record PublishedCardScore(
        String oracleId,
        String name,
        List<String> colors,
        List<CardPrinting> printings,
        CardScores scores,
        List<String> reasons) {

    public PublishedCardScore {
        colors = List.copyOf(colors);
        printings = List.copyOf(printings);
        reasons = List.copyOf(reasons);
    }
}
