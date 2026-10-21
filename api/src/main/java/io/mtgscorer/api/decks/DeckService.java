package io.mtgscorer.api.decks;

import static io.mtgscorer.api.decks.DeckModels.*;

import io.mtgscorer.api.catalog.CatalogService;
import io.mtgscorer.api.decks.DeckRepository.ListedCard;
import io.mtgscorer.api.error.CatalogProblem;
import io.mtgscorer.api.snapshots.SnapshotService;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;

@Service
public class DeckService {
  private final DeckRepository repository;
  private final SnapshotService snapshots;

  public DeckService(DeckRepository repository, SnapshotService snapshots) {
    this.repository = repository;
    this.snapshots = snapshots;
  }

  /**
   * One deck of a published run with its whole list, the cards' details from the given catalog or
   * the active one. A deck from before decks carried their lists has none, rather than failing.
   */
  public DeckDetail deck(String scoreRun, String position, String catalogSnapshot) {
    if (!scoreRun.matches("scores-[0-9a-f]{64}"))
      throw CatalogProblem.query("Invalid score run ID.");
    if (!position.matches("[0-9]{1,7}")) throw CatalogProblem.query("Invalid deck position.");
    int at = Integer.parseInt(position);
    DeckRun run = repository.run(scoreRun).orElseThrow(DeckService::runNotFound);
    var deck =
        repository
            .deck(scoreRun, at)
            .orElseThrow(
                () -> new CatalogProblem(404, "deck_not_found", "Published deck not found."));
    String snapshot = snapshots.resolve(catalogSnapshot);
    List<DeckCard> commanders = null;
    List<DeckCard> mainboard = null;
    List<DeckCard> sideboard = null;
    if (deck.commanders() != null) {
      List<ListedCard> cards = repository.cards(scoreRun, at, snapshot);
      Map<UUID, DeckCard> main =
          cards.stream()
              .filter(card -> !card.sideboard())
              .map(ListedCard::card)
              .collect(Collectors.toMap(DeckCard::oracle_id, Function.identity()));
      commanders = deck.commanders().stream().map(main::get).toList();
      mainboard =
          cards.stream()
              .filter(card -> !card.sideboard())
              .map(ListedCard::card)
              .filter(card -> !deck.commanders().contains(card.oracle_id()))
              .toList();
      sideboard =
          deck.sided()
              ? cards.stream().filter(ListedCard::sideboard).map(ListedCard::card).toList()
              : null;
    }
    return new DeckDetail(
        run,
        snapshot,
        deck.position(),
        deck.source_deck_id(),
        deck.event(),
        deck.archetype(),
        deck.final_rank(),
        deck.made_top_cut(),
        deck.wins(),
        deck.losses(),
        deck.draws(),
        commanders,
        mainboard,
        sideboard);
  }

  private static CatalogProblem runNotFound() {
    return new CatalogProblem(404, "score_run_not_found", "Published score run not found.");
  }

  /**
   * A card's decks in one run. A card no active run lists, or a format it was not played in, has no
   * run and no decks rather than failing, so the page can say so.
   */
  public CardDeckPage decks(String oracle, DeckQuery query) {
    UUID card = CatalogService.oracleId(oracle);
    List<DeckFormat> formats = repository.formats(card);
    DeckRun run = run(formats, query);
    long total = run == null ? 0 : repository.count(run.score_run_id(), card);
    List<CardDeck> items =
        total > query.offset()
            ? repository.page(run.score_run_id(), card, query.offset(), query.limit())
            : List.of();
    return new CardDeckPage(card, formats, run, total, query.offset(), query.limit(), items);
  }

  /**
   * The pinned run, which must belong to the format when both are given; else the requested
   * format's active run, or without one the run listing the most of the card's decks.
   */
  private DeckRun run(List<DeckFormat> formats, DeckQuery query) {
    if (query.scoreRun() != null) {
      // A pinned run keeps every page of a listing on the same published decks.
      DeckRun run = repository.run(query.scoreRun()).orElseThrow(DeckService::runNotFound);
      if (query.format() != null && !query.format().equals(run.format_name()))
        throw CatalogProblem.query("The score run belongs to another format.");
      return run;
    }
    return formats.stream()
        .filter(format -> query.format() == null || format.format_name().equals(query.format()))
        .findFirst()
        .map(format -> repository.run(format.score_run_id()).orElseThrow())
        .orElse(null);
  }
}
