package dev.mtgscorer.api.catalog;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.HashSet;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Repository;

import tools.jackson.databind.json.JsonMapper;

@Repository
public final class ClasspathCardCatalogRepository implements CardCatalogRepository {

    private static final String SUPPORTED_CONTRACT = "card-catalog-v1";

    private final CardCatalog catalog;

    public ClasspathCardCatalogRepository(
            JsonMapper jsonMapper,
            @Value("${mtg-scorer.catalog.resource:classpath:catalog/demo-card-scores.json}")
                    Resource catalogResource) {
        try (var input = catalogResource.getInputStream()) {
            catalog = validate(jsonMapper.readValue(input, CardCatalog.class));
        } catch (IOException exception) {
            throw new UncheckedIOException("could not load published score catalog", exception);
        }
    }

    @Override
    public CardCatalog getPublishedCatalog() {
        return catalog;
    }

    private static CardCatalog validate(CardCatalog candidate) {
        if (!SUPPORTED_CONTRACT.equals(candidate.contractVersion())) {
            throw new IllegalStateException(
                    "unsupported catalog contract: " + candidate.contractVersion());
        }
        if (candidate.snapshot() == null || candidate.cards() == null) {
            throw new IllegalStateException("catalog snapshot and cards are required");
        }
        var oracleIds = new HashSet<String>();
        for (var card : candidate.cards()) {
            if (!oracleIds.add(card.oracleId())) {
                throw new IllegalStateException("duplicate Oracle ID: " + card.oracleId());
            }
        }
        return candidate;
    }
}
