package io.mtgscorer.api.catalog;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;

/** Name-key v1 vectors; analytics/src/mtg_scorer/normalize/names.py owns the definition. */
class NameKeyTests {
  // Spelled by code point: the formatter would turn escapes into invisible literals.
  private static final String NO_BREAK_SPACE = Character.toString(0x00A0);
  private static final String IDEOGRAPHIC_SPACE = Character.toString(0x3000);
  private static final String NEXT_LINE = Character.toString(0x0085);
  private static final String LINE_SEPARATOR = Character.toString(0x2028);
  private static final String VERTICAL_TAB = Character.toString(0x000B);
  private static final String COMBINING_CIRCUMFLEX = Character.toString(0x0302);
  private static final String U_WITH_CIRCUMFLEX = Character.toString(0x00FB);

  @Test
  void lowercasesOnlyAsciiLettersAndPreservesAccents() {
    assertThat(NameKey.normalize("Lightning BOLT")).isEqualTo("lightning bolt");
    assertThat(NameKey.normalize("Jötun Grunt")).isEqualTo("jötun grunt");
    assertThat(NameKey.normalize("ÆTHER VIAL")).isEqualTo("Æther vial");
  }

  @Test
  void appliesCompatibilityNormalizationFirst() {
    assertThat(NameKey.normalize("ＦＩＲＥ")).isEqualTo("fire");
    assertThat(NameKey.normalize("ﬁre")).isEqualTo("fire");
    // A decomposed accent composes, so both spellings share one key.
    assertThat(NameKey.normalize("Lim-Du" + COMBINING_CIRCUMFLEX + "l"))
        .isEqualTo("lim-d" + U_WITH_CIRCUMFLEX + "l");
  }

  @Test
  void collapsesAndTrimsAsciiWhitespaceOnly() {
    String ascii = " \t\r\n\f" + VERTICAL_TAB;
    assertThat(NameKey.normalize(ascii + "Fire" + ascii + "//" + ascii + "Ice" + ascii))
        .isEqualTo("fire // ice");
    // NFKC folds no-break and ideographic spaces into ASCII spaces before collapsing.
    assertThat(NameKey.normalize("Fire" + NO_BREAK_SPACE + IDEOGRAPHIC_SPACE + "Ice"))
        .isEqualTo("fire ice");
    // Other Unicode separators are not whitespace in name-key v1.
    assertThat(NameKey.normalize("Fire" + NEXT_LINE + "Ice" + LINE_SEPARATOR))
        .isEqualTo("fire" + NEXT_LINE + "ice" + LINE_SEPARATOR);
  }

  @Test
  void blankInputHasAnEmptyKey() {
    assertThat(NameKey.normalize("")).isEmpty();
    assertThat(NameKey.normalize(" \t\n ")).isEmpty();
  }

  @Test
  void normalizingAKeyLeavesItUnchanged() {
    // Cursor validation relies on keys being fixed points.
    for (String name :
        List.of(
            " ＦＩＲＥ\t // Ice ",
            "Æther 100%_ ",
            "Lim-Du" + COMBINING_CIRCUMFLEX + "l",
            "Fire" + NO_BREAK_SPACE + IDEOGRAPHIC_SPACE + "Ice",
            "  ")) {
      String key = NameKey.normalize(name);
      assertThat(NameKey.normalize(key)).as(name).isEqualTo(key);
    }
  }
}
