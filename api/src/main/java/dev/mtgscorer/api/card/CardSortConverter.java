package dev.mtgscorer.api.card;

import java.util.Locale;

import org.springframework.core.convert.converter.Converter;
import org.springframework.stereotype.Component;

@Component
public final class CardSortConverter implements Converter<String, CardSort> {

    @Override
    public CardSort convert(String source) {
        return CardSort.valueOf(source.strip().toUpperCase(Locale.ROOT));
    }
}
