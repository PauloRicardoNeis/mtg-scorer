package io.mtgscorer.api.catalog;

import java.text.Normalizer;

/** Query text conformance with Python-owned name-key v1; no layout normalization here. */
public final class NameKey {
  private NameKey() {}

  public static String normalize(String value) {
    String normalized = Normalizer.normalize(value, Normalizer.Form.NFKC);
    StringBuilder result = new StringBuilder();
    for (char character : normalized.toCharArray()) {
      result.append(character >= 'A' && character <= 'Z' ? (char) (character + 32) : character);
    }
    return result.toString().replaceAll("[ \\t\\r\\n\\f\\x0B]+", " ").replaceAll("^ | $", "");
  }
}
