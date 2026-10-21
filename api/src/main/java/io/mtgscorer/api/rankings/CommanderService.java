package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;

import org.springframework.stereotype.Service;

@Service
public class CommanderService {
  private final CommanderRepository repository;
  private final RankingRepository rankings;

  public CommanderService(CommanderRepository repository, RankingRepository rankings) {
    this.repository = repository;
    this.rankings = rankings;
  }

  /**
   * A run's commanders. A format without commanders, or a run from before they were ranked, lists
   * none rather than failing, so a reader can switch windows or formats from the empty page.
   */
  public CommanderPage commanders(CommanderQuery query) {
    var formats = rankings.activeFormats();
    ScoreRunSummary run =
        RankingService.run(
            rankings, formats, query.format(), query.scoreRun(), CommanderQuery.DEFAULT_FORMAT);
    String id = run.score_run_id();
    String previous = repository.previousRun(run);
    return new CommanderPage(
        run,
        formats,
        rankings.activeCatalog(),
        repository.count(id, previous, query),
        query.offset(),
        query.limit(),
        query.sort(),
        query.order(),
        previous,
        repository.maxDeckCount(id),
        rankings.windows(run.format_name()),
        repository.page(id, previous, query));
  }
}
