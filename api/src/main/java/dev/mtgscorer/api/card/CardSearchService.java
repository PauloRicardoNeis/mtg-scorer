package dev.mtgscorer.api.card;

import java.util.Comparator;
import java.util.Locale;
import java.util.Optional;
import java.util.function.ToDoubleFunction;

import org.springframework.stereotype.Service;

import dev.mtgscorer.api.catalog.CardCatalogRepository;
import dev.mtgscorer.api.catalog.PublishedCardScore;

@Service
public final class CardSearchService {

    private final CardCatalogRepository catalogRepository;

    public CardSearchService(CardCatalogRepository catalogRepository) {
        this.catalogRepository = catalogRepository;
    }

    public CardSearchResponse search(CardSearchQuery query) {
        var catalog = catalogRepository.getPublishedCatalog();
        var matchingCards = catalog.cards().stream()
                .filter(card -> containsIgnoreCase(card.name(), query.query()))
                .filter(card -> printingMatches(card, query.setCode(), query.rarity()))
                .sorted(comparator(query.sort()))
                .toList();
        var visibleCards = matchingCards.stream().limit(query.limit()).toList();

        return new CardSearchResponse(
                catalog.contractVersion(),
                catalog.catalogKind(),
                catalog.snapshot(),
                matchingCards.size(),
                visibleCards);
    }

    public Optional<PublishedCardScore> findByOracleId(String oracleId) {
        return catalogRepository.getPublishedCatalog().cards().stream()
                .filter(card -> card.oracleId().equals(oracleId))
                .findFirst();
    }

    private static boolean containsIgnoreCase(String value, String fragment) {
        return normalize(value).contains(normalize(fragment));
    }

    private static boolean printingMatches(
            PublishedCardScore card, String setCode, String rarity) {
        if (isBlank(setCode) && isBlank(rarity)) {
            return true;
        }
        return card.printings().stream()
                .anyMatch(printing ->
                        (isBlank(setCode) || normalize(printing.setCode()).equals(normalize(setCode)))
                                && (isBlank(rarity)
                                        || normalize(printing.rarity()).equals(normalize(rarity))));
    }

    private static Comparator<PublishedCardScore> comparator(CardSort sort) {
        ToDoubleFunction<PublishedCardScore> score = switch (sort) {
            case STAPLE -> card -> card.scores().staple();
            case BUILDAROUND -> card -> card.scores().buildaroundSignal();
            case EVIDENCE -> card -> card.scores().evidence();
            case DISTINCTIVENESS -> card -> card.scores().distinctivenessDelta();
        };
        return Comparator.comparingDouble(score)
                .reversed()
                .thenComparing(PublishedCardScore::name);
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static String normalize(String value) {
        return value == null ? "" : value.strip().toLowerCase(Locale.ROOT);
    }
}
