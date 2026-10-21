package io.mtgscorer.api.decks;

import static io.mtgscorer.api.decks.DeckModels.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

import io.mtgscorer.api.decks.DeckRepository.DeckHeader;
import io.mtgscorer.api.decks.DeckRepository.ListedCard;
import io.mtgscorer.api.error.CatalogProblem;
import io.mtgscorer.api.snapshots.SnapshotService;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class DeckServiceTests {
  private static final UUID BOLT = UUID.fromString("4457ed35-7c10-48c8-9776-456485fdf070");
  private static final String MODERN = "scores-" + "a".repeat(64);
  private static final String LEGACY = "scores-" + "b".repeat(64);
  private static final String OLDER = "scores-" + "c".repeat(64);
  private static final List<DeckFormat> FORMATS =
      List.of(
          new DeckFormat("Modern", "topdeck", MODERN, 412),
          new DeckFormat("Legacy", "topdeck", LEGACY, 96));

  private static final UUID KINNAN = UUID.fromString("6a1c4d8e-7f5b-4a0e-9c1d-2b3e4f5a6b7c");
  private static final UUID ISLAND = UUID.fromString("b2c6aa39-2d2a-459c-a555-fb48ba993373");
  private static final UUID PYROBLAST = UUID.fromString("0f3a8b5e-1c2d-4e6f-8a9b-1c2d3e4f5a6b");

  @Mock private DeckRepository repository;
  @Mock private SnapshotService snapshots;

  private DeckService service() {
    return new DeckService(repository, snapshots);
  }

  private static DeckHeader header(List<UUID> commanders, boolean sided) {
    return new DeckHeader(
        7,
        "event#8",
        new DeckEvent("event", "An event", null, LocalDate.of(2026, 9, 1), 32),
        "Kinnan, Bonder Prodigy",
        null,
        true,
        3,
        1,
        0,
        commanders,
        sided);
  }

  private static DeckCard card(UUID id, String name, int copies) {
    return new DeckCard(id, name, copies, null, "Instant", 1.0, true);
  }

  private static DeckRun run(String id, String format) {
    return new DeckRun(
        id, "topdeck", format, LocalDate.of(2024, 1, 1), LocalDate.of(2026, 10, 1), "TopDeck");
  }

  private static CardDeck deck(int position) {
    return new CardDeck(
        position,
        "event#1",
        new DeckEvent("event", "An event", null, LocalDate.of(2026, 9, 1), 32),
        "Burn",
        4,
        null,
        true,
        3,
        1,
        0);
  }

  private static DeckQuery query(String... pairs) {
    var input = new java.util.HashMap<String, List<String>>();
    for (int index = 0; index < pairs.length; index += 2)
      input.put(pairs[index], List.of(pairs[index + 1]));
    return DeckQuery.parse(input);
  }

  @Test
  void aListedDeckSetsItsCommandersApartFromTheMainDeckAndKeepsItsSideboard() {
    when(repository.run(MODERN)).thenReturn(Optional.of(run(MODERN, "EDH")));
    when(repository.deck(MODERN, 7)).thenReturn(Optional.of(header(List.of(KINNAN), true)));
    when(snapshots.resolve(null)).thenReturn("catalog-a");
    when(repository.cards(MODERN, 7, "catalog-a"))
        .thenReturn(
            List.of(
                new ListedCard(false, card(ISLAND, "Island", 30)),
                new ListedCard(false, card(KINNAN, "Kinnan, Bonder Prodigy", 1)),
                new ListedCard(true, card(PYROBLAST, "Pyroblast", 2))));

    var deck = service().deck(MODERN, "7", null);

    assertThat(deck.catalog_snapshot_id()).isEqualTo("catalog-a");
    assertThat(deck.run().format_name()).isEqualTo("EDH");
    assertThat(deck.position()).isEqualTo(7);
    assertThat(deck.commanders())
        .extracting(DeckCard::name)
        .containsExactly("Kinnan, Bonder Prodigy");
    assertThat(deck.mainboard()).extracting(DeckCard::name).containsExactly("Island");
    assertThat(deck.sideboard()).extracting(DeckCard::copies).containsExactly(2);
    assertThat(deck.made_top_cut()).isTrue();
    assertThat(List.of(deck.wins(), deck.losses(), deck.draws())).containsExactly(3, 1, 0);
  }

  @Test
  void aSideboardTheSourceDidNotReportStaysUnknown() {
    when(repository.run(MODERN)).thenReturn(Optional.of(run(MODERN, "Modern")));
    when(repository.deck(MODERN, 0)).thenReturn(Optional.of(header(List.of(), false)));
    when(snapshots.resolve("catalog-b")).thenReturn("catalog-b");
    when(repository.cards(MODERN, 0, "catalog-b"))
        .thenReturn(List.of(new ListedCard(false, card(ISLAND, "Island", 20))));

    var deck = service().deck(MODERN, "0", "catalog-b");

    assertThat(deck.commanders()).isEmpty();
    assertThat(deck.mainboard()).hasSize(1);
    assertThat(deck.sideboard()).isNull();
  }

  @Test
  void aDeckFromBeforeDeckListsHasNoLists() {
    when(repository.run(OLDER)).thenReturn(Optional.of(run(OLDER, "Modern")));
    when(repository.deck(OLDER, 3)).thenReturn(Optional.of(header(null, false)));
    when(snapshots.resolve(null)).thenReturn("catalog-a");

    var deck = service().deck(OLDER, "3", null);

    assertThat(List.of(deck.archetype(), deck.source_deck_id()))
        .containsExactly("Kinnan, Bonder Prodigy", "event#8");
    assertThat(deck.commanders()).isNull();
    assertThat(deck.mainboard()).isNull();
    assertThat(deck.sideboard()).isNull();
    verify(repository).deck(OLDER, 3);
    verify(repository).run(OLDER);
    verifyNoMoreInteractions(repository);
  }

  @Test
  void aDeckMustBeInAPublishedRun() {
    when(repository.run(OLDER)).thenReturn(Optional.empty());
    assertThatThrownBy(() -> service().deck(OLDER, "3", null))
        .isInstanceOf(CatalogProblem.class)
        .hasFieldOrPropertyWithValue("code", "score_run_not_found");

    when(repository.run(MODERN)).thenReturn(Optional.of(run(MODERN, "Modern")));
    when(repository.deck(MODERN, 99)).thenReturn(Optional.empty());
    assertThatThrownBy(() -> service().deck(MODERN, "99", null))
        .isInstanceOf(CatalogProblem.class)
        .hasFieldOrPropertyWithValue("status", 404)
        .hasFieldOrPropertyWithValue("code", "deck_not_found");
  }

  @Test
  void aDeckIsNamedByARunIdAndAPosition() {
    for (String[] path : new String[][] {{"scores-abc", "1"}, {MODERN, "-1"}, {MODERN, "one"}})
      assertThatThrownBy(() -> service().deck(path[0], path[1], null))
          .isInstanceOf(CatalogProblem.class)
          .hasFieldOrPropertyWithValue("code", "invalid_query");
    verifyNoMoreInteractions(repository);
  }

  @Test
  void withoutAFormatTheRunListingTheMostOfTheCardsDecksIsShown() {
    when(repository.formats(BOLT)).thenReturn(FORMATS);
    when(repository.run(MODERN)).thenReturn(Optional.of(run(MODERN, "Modern")));
    when(repository.count(MODERN, BOLT)).thenReturn(412L);
    when(repository.page(MODERN, BOLT, 0, 20)).thenReturn(List.of(deck(0), deck(3)));

    var page = service().decks(BOLT.toString(), query());

    assertThat(page.oracle_id()).isEqualTo(BOLT);
    assertThat(page.formats()).isEqualTo(FORMATS);
    assertThat(page.run().format_name()).isEqualTo("Modern");
    assertThat(page.total()).isEqualTo(412);
    assertThat(page.items()).extracting(CardDeck::position).containsExactly(0, 3);
  }

  @Test
  void aRequestedFormatShowsItsActiveRun() {
    when(repository.formats(BOLT)).thenReturn(FORMATS);
    when(repository.run(LEGACY)).thenReturn(Optional.of(run(LEGACY, "Legacy")));
    when(repository.count(LEGACY, BOLT)).thenReturn(96L);
    when(repository.page(LEGACY, BOLT, 40, 20)).thenReturn(List.of(deck(80)));

    var page = service().decks(BOLT.toString(), query("format", "Legacy", "offset", "40"));

    assertThat(page.run().score_run_id()).isEqualTo(LEGACY);
    assertThat(page.offset()).isEqualTo(40);
  }

  @Test
  void aFormatTheCardWasNotPlayedInHasNoRunAndNoDecks() {
    when(repository.formats(BOLT)).thenReturn(FORMATS);

    var page = service().decks(BOLT.toString(), query("format", "Pauper"));

    assertThat(page.run()).isNull();
    assertThat(page.total()).isZero();
    assertThat(page.items()).isEmpty();
    verify(repository).formats(BOLT);
    verifyNoMoreInteractions(repository);
  }

  @Test
  void aPinnedRunIsShownEvenWhenNoLongerActiveAndAPagePastItsDecksIsEmpty() {
    when(repository.formats(BOLT)).thenReturn(FORMATS);
    when(repository.run(OLDER)).thenReturn(Optional.of(run(OLDER, "Modern")));
    when(repository.count(OLDER, BOLT)).thenReturn(20L);

    var page =
        service()
            .decks(
                BOLT.toString(), query("format", "Modern", "score_run_id", OLDER, "offset", "20"));

    assertThat(page.run().score_run_id()).isEqualTo(OLDER);
    assertThat(page.total()).isEqualTo(20);
    assertThat(page.items()).isEmpty();
  }

  @Test
  void aPinnedRunWithoutAFormatIsShown() {
    when(repository.formats(BOLT)).thenReturn(FORMATS);
    when(repository.run(OLDER)).thenReturn(Optional.of(run(OLDER, "Modern")));
    when(repository.count(OLDER, BOLT)).thenReturn(0L);

    assertThat(service().decks(BOLT.toString(), query("score_run_id", OLDER)).run())
        .isEqualTo(run(OLDER, "Modern"));
  }

  @Test
  void aPinnedRunMustBelongToTheFormat() {
    when(repository.formats(BOLT)).thenReturn(FORMATS);
    when(repository.run(LEGACY)).thenReturn(Optional.of(run(LEGACY, "Legacy")));

    assertThatThrownBy(
            () ->
                service().decks(BOLT.toString(), query("format", "Modern", "score_run_id", LEGACY)))
        .isInstanceOf(CatalogProblem.class)
        .hasFieldOrPropertyWithValue("code", "invalid_query");
  }

  @Test
  void aPinnedRunMustBePublished() {
    when(repository.formats(BOLT)).thenReturn(FORMATS);
    when(repository.run(OLDER)).thenReturn(Optional.empty());

    assertThatThrownBy(() -> service().decks(BOLT.toString(), query("score_run_id", OLDER)))
        .isInstanceOf(CatalogProblem.class)
        .hasFieldOrPropertyWithValue("code", "score_run_not_found");
  }

  @Test
  void anOracleIdMustBeAUuid() {
    assertThatThrownBy(() -> service().decks("bolt", DeckQuery.parse(Map.of())))
        .isInstanceOf(CatalogProblem.class)
        .hasFieldOrPropertyWithValue("code", "invalid_query");
  }
}
