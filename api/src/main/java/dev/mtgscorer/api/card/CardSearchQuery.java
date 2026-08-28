package dev.mtgscorer.api.card;

public record CardSearchQuery(
        String query,
        String setCode,
        String rarity,
        CardSort sort,
        int limit) {}
