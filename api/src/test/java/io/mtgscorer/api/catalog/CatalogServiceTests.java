package io.mtgscorer.api.catalog;

import static io.mtgscorer.api.catalog.CatalogModels.*;
import static io.mtgscorer.api.catalog.QueryParams.cards;
import static io.mtgscorer.api.catalog.QueryParams.cardsAfter;
import static io.mtgscorer.api.catalog.QueryParams.printings;
import static io.mtgscorer.api.catalog.QueryParams.printingsAfter;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.error.CatalogProblem;
import io.mtgscorer.api.snapshots.SnapshotService;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import tools.jackson.databind.json.JsonMapper;

@ExtendWith(MockitoExtension.class)
class CatalogServiceTests {
  private static final String CARD = "a0000000-0000-4000-8000-0000000000f1";
  private static final UUID CARD_ID = UUID.fromString(CARD);
  private static final JsonMapper MAPPER = JsonMapper.builder().build();

  @Mock private CatalogRepository repository;
  @Mock private SnapshotService snapshots;

  private final CursorCodec codec = new CursorCodec(MAPPER);
  private CatalogService service;

  @BeforeEach
  void setUp() {
    service = new CatalogService(repository, snapshots, MAPPER);
  }

  @Test
  void aShortPageHasNoContinuation() {
    var query = cards("limit", "2");
    when(snapshots.resolve(null)).thenReturn("catalog-a");
    when(repository.search("catalog-a", query, null))
        .thenReturn(List.of(row("bolt", 1), row("shock", 2)));

    var page = service.search(query);

    assertThat(page.catalog_snapshot_id()).isEqualTo("catalog-a");
    assertThat(page.items()).extracting(CardSummary::name).containsExactly("bolt", "shock");
    assertThat(page.next_cursor()).isNull();
  }

  @Test
  void aFullPageDropsTheLookaheadRowAndContinuesAfterTheLastVisibleCard() {
    var query = cards("set", "m11", "limit", "2");
    when(snapshots.resolve(null)).thenReturn("catalog-a");
    when(repository.search("catalog-a", query, null))
        .thenReturn(List.of(row("bolt", 1), row("shock", 2), row("zap", 3)));

    var page = service.search(query);

    assertThat(page.items()).extracting(CardSummary::name).containsExactly("bolt", "shock");
    var cursor = codec.decode("cards", cardsAfter(page.next_cursor(), "set", "m11", "limit", "2"));
    assertThat(cursor.catalog_snapshot_id()).isEqualTo("catalog-a");
    assertThat(cursor.last_key()).containsExactly("shock", oracle(2).toString());
  }

  @Test
  void aContinuationStaysOnTheCursorSnapshot() {
    String next = codec.encode("cards", "catalog-old", cards("limit", "2"), List.of("bolt", CARD));
    var query = cardsAfter(next, "limit", "2");
    // The active catalog may have moved on; the cursor keeps the pages consistent.
    when(snapshots.resolve("catalog-old")).thenReturn("catalog-old");
    ArgumentCaptor<CursorCodec.Cursor> cursor = ArgumentCaptor.forClass(CursorCodec.Cursor.class);
    when(repository.search(eq("catalog-old"), eq(query), cursor.capture())).thenReturn(List.of());

    var page = service.search(query);

    assertThat(page.catalog_snapshot_id()).isEqualTo("catalog-old");
    assertThat(page.items()).isEmpty();
    assertThat(page.next_cursor()).isNull();
    assertThat(cursor.getValue().last_key()).containsExactly("bolt", CARD);
  }

  @Test
  void anInvalidCursorFailsBeforeAnyLookup() {
    assertThatThrownBy(() -> service.search(cardsAfter("not!a!cursor")))
        .isInstanceOfSatisfying(
            CatalogProblem.class,
            problem -> assertThat(problem.code()).isEqualTo("invalid_cursor"));
    verifyNoInteractions(snapshots, repository);
  }

  @Test
  void detailResolvesTheRequestedSnapshotAndNormalizesTheOracleId() {
    var detail =
        new CardDetail(
            "catalog-a",
            CARD_ID,
            "Bolt",
            "normal",
            "{R}",
            1.0,
            "",
            "Instant",
            List.of("R"),
            List.of("R"),
            List.of());
    when(snapshots.resolve("catalog-a")).thenReturn("catalog-a");
    when(repository.detail("catalog-a", CARD_ID)).thenReturn(detail);

    assertThat(service.detail(CARD.toUpperCase(), "catalog-a")).isSameAs(detail);
  }

  @Test
  void detailWithoutASnapshotUsesTheActiveCatalog() {
    when(snapshots.resolve(isNull())).thenReturn("catalog-active");

    service.detail(CARD, null);

    verify(repository).detail("catalog-active", CARD_ID);
  }

  @Test
  void malformedOracleIdsAreRejectedBeforeAnyLookup() {
    // UUID.fromString alone would accept the abbreviated form.
    for (String id : List.of("not-a-uuid", "1-1-1-1-1", "{" + CARD + "}", CARD + "0", "")) {
      assertThatThrownBy(() -> service.detail(id, null))
          .isInstanceOfSatisfying(
              CatalogProblem.class,
              problem -> assertThat(problem.getMessage()).isEqualTo("Invalid Oracle ID."));
      assertThatThrownBy(() -> service.printings(id, printings()))
          .isInstanceOf(CatalogProblem.class);
    }
    verifyNoInteractions(snapshots, repository);
  }

  @Test
  void printingPagesContinueOnlyForTheSameCard() {
    var query = printings("limit", "1");
    when(snapshots.resolve(null)).thenReturn("catalog-a");
    when(repository.printings("catalog-a", CARD_ID, query, null))
        .thenReturn(List.of(printing(1), printing(2)));

    var page = service.printings(CARD, query);

    assertThat(page.catalog_snapshot_id()).isEqualTo("catalog-a");
    assertThat(page.oracle_id()).isEqualTo(CARD_ID);
    assertThat(page.items()).extracting(Printing::scryfall_id).containsExactly(scryfall(1));
    var continuation = printingsAfter(page.next_cursor(), "limit", "1");
    assertThat(codec.decode("printings:" + CARD, continuation).last_key())
        .containsExactly(scryfall(1).toString());
    assertThatThrownBy(
            () -> codec.decode("printings:00000000-0000-4000-8000-000000000002", continuation))
        .isInstanceOf(CatalogProblem.class);
  }

  @Test
  void aPrintingContinuationAcceptsTheSameCardInAnyHexCase() {
    String next =
        codec.encode(
            "printings:" + CARD,
            "catalog-old",
            printings("limit", "1"),
            List.of(scryfall(1).toString()));
    var query = printingsAfter(next, "limit", "1");
    when(snapshots.resolve("catalog-old")).thenReturn("catalog-old");
    ArgumentCaptor<CursorCodec.Cursor> cursor = ArgumentCaptor.forClass(CursorCodec.Cursor.class);
    when(repository.printings(eq("catalog-old"), eq(CARD_ID), eq(query), cursor.capture()))
        .thenReturn(List.of(printing(2)));

    var page = service.printings(CARD.toUpperCase(), query);

    assertThat(page.items()).extracting(Printing::scryfall_id).containsExactly(scryfall(2));
    assertThat(page.next_cursor()).isNull();
    assertThat(cursor.getValue().last_key()).containsExactly(scryfall(1).toString());
  }

  private static UUID oracle(int n) {
    return UUID.fromString("00000000-0000-4000-8000-%012d".formatted(n));
  }

  private static UUID scryfall(int n) {
    return UUID.fromString("10000000-0000-4000-8000-%012d".formatted(n));
  }

  private static CatalogRepository.CardRow row(String nameKey, int n) {
    return new CatalogRepository.CardRow(
        new CardSummary(
            oracle(n), nameKey, "normal", "{R}", "Instant", List.of("R"), 1, printing(n)),
        nameKey);
  }

  private static Printing printing(int n) {
    return new Printing(
        scryfall(n),
        "m11",
        "Magic 2011",
        Integer.toString(n),
        "common",
        LocalDate.of(2010, 7, 16),
        "en",
        List.of("paper"),
        "https://scryfall.com/card/m11/" + n,
        List.of());
  }
}
