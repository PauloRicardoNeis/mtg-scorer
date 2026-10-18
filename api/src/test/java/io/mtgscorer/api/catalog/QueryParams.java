package io.mtgscorer.api.catalog;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Builds query maps the way Spring binds repeated request parameters. */
final class QueryParams {
  private QueryParams() {}

  static Map<String, List<String>> params(String... pairs) {
    if (pairs.length % 2 != 0) throw new IllegalArgumentException("Expected name/value pairs.");
    Map<String, List<String>> result = new LinkedHashMap<>();
    for (int i = 0; i < pairs.length; i += 2)
      result.computeIfAbsent(pairs[i], name -> new ArrayList<>()).add(pairs[i + 1]);
    return result;
  }

  static CatalogQuery cards(String... pairs) {
    return CatalogQuery.parse(params(pairs), false);
  }

  static CatalogQuery printings(String... pairs) {
    return CatalogQuery.parse(params(pairs), true);
  }

  static CatalogQuery cardsAfter(String cursor, String... pairs) {
    var input = params(pairs);
    input.put("cursor", List.of(cursor));
    return CatalogQuery.parse(input, false);
  }

  static CatalogQuery printingsAfter(String cursor, String... pairs) {
    var input = params(pairs);
    input.put("cursor", List.of(cursor));
    return CatalogQuery.parse(input, true);
  }

  /** The same parameter repeated once per value. */
  static String[] repeated(String name, List<String> values) {
    String[] pairs = new String[values.size() * 2];
    for (int i = 0; i < values.size(); i++) {
      pairs[2 * i] = name;
      pairs[2 * i + 1] = values.get(i);
    }
    return pairs;
  }
}
