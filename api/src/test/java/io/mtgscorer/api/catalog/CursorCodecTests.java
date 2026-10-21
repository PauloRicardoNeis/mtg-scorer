package io.mtgscorer.api.catalog;

import static io.mtgscorer.api.catalog.QueryParams.cards;
import static io.mtgscorer.api.catalog.QueryParams.cardsAfter;
import static io.mtgscorer.api.catalog.QueryParams.printings;
import static io.mtgscorer.api.catalog.QueryParams.printingsAfter;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.mtgscorer.api.error.CatalogProblem;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.function.Consumer;
import java.util.stream.Stream;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

class CursorCodecTests {
  private static final String CARD = "a0000000-0000-4000-8000-0000000000f1";
  private static final String OTHER_CARD = "00000000-0000-4000-8000-000000000002";
  private static final String PRINTING = "10000000-0000-4000-8000-000000000001";
  private static final JsonMapper MAPPER = JsonMapper.builder().build();

  private final CursorCodec codec = new CursorCodec(MAPPER);

  @Test
  void roundTripPreservesTheBindingAndKeyOfAFilteredPage() {
    String[] filters = {
      "q",
      "Lightning",
      "set",
      "m11",
      "set",
      "2x2",
      "rarity",
      "common",
      "game",
      "paper",
      "color_identity",
      "RU",
      "color",
      "R",
      "type",
      "instant",
      "limit",
      "5"
    };
    String encoded =
        codec.encode("cards", "catalog-abc", cards(filters), List.of("lightning bolt", CARD));

    assertThat(encoded).matches("[A-Za-z0-9_-]+");
    var cursor = codec.decode("cards", cardsAfter(encoded, filters));
    assertThat(cursor.version()).isEqualTo(1);
    assertThat(cursor.resource()).isEqualTo("cards");
    assertThat(cursor.catalog_snapshot_id()).isEqualTo("catalog-abc");
    assertThat(cursor.sort()).isEqualTo("name_asc");
    assertThat(cursor.limit()).isEqualTo(5);
    assertThat(cursor.last_key()).containsExactly("lightning bolt", CARD);
    assertThat(cursor.filter_hash()).matches("[0-9a-f]{64}");
  }

  @Test
  void encodedCursorIsUnpaddedBase64UrlJsonWithExactlyTheBoundFields() {
    String encoded =
        codec.encode("cards", "catalog-abc", cards("limit", "2"), List.of("bolt", CARD));

    JsonNode json = MAPPER.readTree(Base64.getUrlDecoder().decode(encoded));
    assertThat(json.propertyNames())
        .containsExactlyInAnyOrder(
            "version",
            "resource",
            "catalog_snapshot_id",
            "filter_hash",
            "sort",
            "limit",
            "last_key");
    assertThat(encoded).doesNotContain("=", "+", "/");
  }

  @Test
  void noCursorMeansTheFirstPage() {
    assertThat(codec.decode("cards", cards())).isNull();
  }

  @Test
  void equivalentSpellingsOfTheSameFiltersContinueTheSameCursor() {
    String encoded =
        codec.encode(
            "cards",
            "catalog-abc",
            cards(
                "q",
                "  Lightning   BOLT ",
                "set",
                "m11",
                "set",
                "2x2",
                "color_identity",
                "RU",
                "color",
                "R",
                "color",
                "W"),
            List.of("bolt", CARD));

    var cursor =
        codec.decode(
            "cards",
            cardsAfter(
                encoded,
                "q",
                "lightning bolt",
                "set",
                "2x2",
                "set",
                "m11",
                "set",
                "m11",
                "color_identity",
                "UR",
                "color",
                "W",
                "color",
                "R"));
    assertThat(cursor.last_key()).containsExactly("bolt", CARD);
  }

  @Test
  void filtersAddedLaterLeaveTheFingerprintOfEarlierCursorsUnchanged() throws Exception {
    String encoded =
        codec.encode("cards", "catalog-abc", cards("set", "m11"), List.of("bolt", CARD));

    // The fingerprint of a query without color or type filters predates those filters.
    String legacy =
        "{\"color_identity\":null,\"game\":null,\"q\":null,\"rarities\":null,\"sets\":[\"m11\"]}";
    assertThat(cursorJson(encoded).path("filter_hash").asString()).isEqualTo(sha256(legacy));
  }

  @Test
  void whereTextIsSearchedBindsTheCursorOnlyWithTextAndOffTheDefault() {
    List<String> key = List.of("bolt", CARD);
    String all = codec.encode("cards", "catalog-abc", cards("q", "elf"), key);
    String types = codec.encode("cards", "catalog-abc", cards("q", "elf", "in", "type"), key);
    String noText = codec.encode("cards", "catalog-abc", cards("in", "type"), key);

    assertThat(codec.decode("cards", cardsAfter(all, "q", "elf", "in", "all"))).isNotNull();
    assertThat(codec.decode("cards", cardsAfter(types, "q", "elf", "in", "type"))).isNotNull();
    assertInvalidCursor(() -> codec.decode("cards", cardsAfter(types, "q", "elf")));
    assertInvalidCursor(() -> codec.decode("cards", cardsAfter(all, "q", "elf", "in", "text")));
    // Without text there is nothing to look for, wherever it would be.
    assertThat(codec.decode("cards", cardsAfter(noText))).isNotNull();
  }

  @Test
  void anExplicitSnapshotMustBeTheCursorSnapshot() {
    String encoded =
        codec.encode("cards", "catalog-abc", cards("limit", "2"), List.of("bolt", CARD));

    var cursor =
        codec.decode(
            "cards", cardsAfter(encoded, "limit", "2", "catalog_snapshot_id", "catalog-abc"));
    assertThat(cursor.catalog_snapshot_id()).isEqualTo("catalog-abc");
    assertInvalidCursor(
        () ->
            codec.decode(
                "cards", cardsAfter(encoded, "limit", "2", "catalog_snapshot_id", "catalog-new")));
  }

  @Test
  void printingCursorsCarryOnlyTheLastScryfallIdOfTheirCard() {
    String resource = "printings:" + CARD;
    String[] filters = {"set", "m11", "limit", "1"};
    String encoded = codec.encode(resource, "catalog-abc", printings(filters), List.of(PRINTING));

    var cursor = codec.decode(resource, printingsAfter(encoded, filters));
    assertThat(cursor.sort()).isEqualTo("original_first");
    assertThat(cursor.last_key()).containsExactly(PRINTING);
    assertInvalidCursor(
        () -> codec.decode("printings:" + OTHER_CARD, printingsAfter(encoded, filters)));

    String twoKeys =
        codec.encode(resource, "catalog-abc", printings(filters), List.of("bolt", PRINTING));
    assertInvalidCursor(() -> codec.decode(resource, printingsAfter(twoKeys, filters)));

    // Same filters, but a card page sorts differently and has a different resource.
    String cardsCursor =
        codec.encode("cards", "catalog-abc", cards(filters), List.of("bolt", PRINTING));
    assertInvalidCursor(() -> codec.decode(resource, printingsAfter(cardsCursor, filters)));
  }

  @Test
  void encodedLengthIsBoundedAt4096Characters() {
    byte[] json =
        Base64.getUrlDecoder()
            .decode(
                codec.encode("cards", "catalog-abc", cards("limit", "2"), List.of("bolt", CARD)));

    // Leading whitespace keeps the JSON valid while growing the encoding: 3072 bytes -> 4096.
    String atLimit = base64(leftPad(json, 3072));
    String overLimit = base64(leftPad(json, 3073));
    assertThat(atLimit).hasSize(4096);
    assertThat(overLimit.length()).isGreaterThan(4096);
    assertThat(codec.decode("cards", cardsAfter(atLimit, "limit", "2"))).isNotNull();
    assertInvalidCursor(() -> codec.decode("cards", cardsAfter(overLimit, "limit", "2")));
  }

  static Stream<Arguments> malformedCursors() {
    return Stream.of(
        Arguments.of("empty", ""),
        Arguments.of("padded", "e30="),
        Arguments.of("standard alphabet", "ab+/"),
        Arguments.of("whitespace", "e30 "),
        Arguments.of("impossible length", "A"),
        Arguments.of("not JSON", base64("cursor")),
        Arguments.of("JSON array", base64("[]")),
        Arguments.of("JSON string", base64("\"cursor\"")),
        Arguments.of("JSON null", base64("null")),
        Arguments.of("blank JSON", base64("   ")),
        Arguments.of("empty object", base64("{}")),
        Arguments.of("invalid UTF-8", base64(new byte[] {'{', (byte) 0xC3, (byte) 0x28, '}'})));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("malformedCursors")
  void rejectsMalformedEncodings(String name, String cursor) {
    assertInvalidCursor(() -> codec.decode("cards", cardsAfter(cursor)));
  }

  @Test
  void anUntamperedReencodingStillDecodes() {
    ObjectNode node = validCursorNode();
    assertThat(
            codec.decode("cards", cardsAfter(base64(MAPPER.writeValueAsBytes(node)), "limit", "2")))
        .isNotNull();
  }

  @Test
  void trailingDataAfterTheCursorObjectIsRejected() {
    String json = MAPPER.writeValueAsString(validCursorNode());

    for (String trailing : List.of(" {}", " 1", "}"))
      assertInvalidCursor(
          () -> codec.decode("cards", cardsAfter(base64(json + trailing), "limit", "2")));
  }

  static Stream<Arguments> tamperedCursors() {
    return Stream.of(
        tamper("newer version", node -> node.put("version", 2)),
        tamper("version as text", node -> node.put("version", "1")),
        tamper("fractional version", node -> node.put("version", 1.0)),
        tamper("other limit", node -> node.put("limit", 3)),
        tamper("limit as text", node -> node.put("limit", "2")),
        tamper("fractional limit", node -> node.put("limit", 2.0)),
        tamper("other resource", node -> node.put("resource", "printings:" + CARD)),
        tamper("null resource", node -> node.putNull("resource")),
        tamper("other sort", node -> node.put("sort", "original_first")),
        tamper("numeric sort", node -> node.put("sort", 1)),
        tamper("other filters", node -> node.put("filter_hash", "0".repeat(64))),
        tamper("uppercase snapshot", node -> node.put("catalog_snapshot_id", "Catalog-ABC")),
        tamper("empty snapshot", node -> node.put("catalog_snapshot_id", "")),
        tamper("snapshot path", node -> node.put("catalog_snapshot_id", "../catalog")),
        tamper("key as text", node -> node.put("last_key", "bolt")),
        tamper("single key", node -> node.set("last_key", keys("bolt"))),
        tamper("three keys", node -> node.set("last_key", keys("bolt", CARD, CARD))),
        tamper(
            "numeric name key",
            node -> node.set("last_key", MAPPER.createArrayNode().add(1).add(CARD))),
        tamper(
            "uppercase oracle ID", node -> node.set("last_key", keys("bolt", CARD.toUpperCase()))),
        tamper("not an oracle ID", node -> node.set("last_key", keys("bolt", "not-a-uuid"))),
        tamper("empty name key", node -> node.set("last_key", keys("", CARD))),
        tamper("unnormalized name key", node -> node.set("last_key", keys("Bolt", CARD))),
        tamper("padded name key", node -> node.set("last_key", keys(" bolt", CARD))),
        tamper("oversized name key", node -> node.set("last_key", keys("b".repeat(513), CARD))),
        tamper("missing field", node -> node.remove("sort")),
        tamper("extra field", node -> node.put("admin", true)));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("tamperedCursors")
  void rejectsTamperedFields(String name, Consumer<ObjectNode> change) {
    ObjectNode node = validCursorNode();
    change.accept(node);
    String tampered = base64(MAPPER.writeValueAsBytes(node));

    assertInvalidCursor(() -> codec.decode("cards", cardsAfter(tampered, "limit", "2")));
  }

  @Test
  void acceptsANameKeyAtTheLengthLimit() {
    ObjectNode node = validCursorNode();
    node.set("last_key", keys("b".repeat(512), CARD));

    var cursor =
        codec.decode("cards", cardsAfter(base64(MAPPER.writeValueAsBytes(node)), "limit", "2"));
    assertThat(cursor.last_key().getFirst()).hasSize(512);
  }

  private ObjectNode validCursorNode() {
    return (ObjectNode)
        cursorJson(
            codec.encode("cards", "catalog-abc", cards("limit", "2"), List.of("bolt", CARD)));
  }

  private static Arguments tamper(String name, Consumer<ObjectNode> change) {
    return Arguments.of(name, change);
  }

  private static ArrayNode keys(String... values) {
    ArrayNode array = MAPPER.createArrayNode();
    for (String value : values) array.add(value);
    return array;
  }

  private static JsonNode cursorJson(String encoded) {
    return MAPPER.readTree(Base64.getUrlDecoder().decode(encoded));
  }

  private static String base64(String text) {
    return base64(text.getBytes(StandardCharsets.UTF_8));
  }

  private static String base64(byte[] bytes) {
    return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
  }

  private static byte[] leftPad(byte[] json, int size) {
    byte[] padded = new byte[size];
    Arrays.fill(padded, (byte) ' ');
    System.arraycopy(json, 0, padded, size - json.length, json.length);
    return padded;
  }

  private static String sha256(String text) throws Exception {
    return HexFormat.of()
        .formatHex(
            MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)));
  }

  private static void assertInvalidCursor(ThrowingCallable call) {
    assertThatThrownBy(call)
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> {
              assertThat(problem.status()).isEqualTo(400);
              assertThat(problem.code()).isEqualTo("invalid_cursor");
              assertThat(problem.getMessage()).isEqualTo("The cursor does not match this request.");
            });
  }
}
