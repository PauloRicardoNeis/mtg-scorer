package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;

import io.mtgscorer.api.error.CatalogProblem;
import org.springframework.stereotype.Service;

@Service
public class RankingService {
  private final RankingRepository repository;

  public RankingService(RankingRepository repository) {
    this.repository = repository;
  }

  public RankingPage rankings(RankingQuery query) {
    var formats = repository.activeFormats();
    ScoreRunSummary run;
    if (query.scoreRun() != null) {
      // A pinned run keeps every page of a listing on the same published results.
      run =
          repository
              .run(query.scoreRun())
              .orElseThrow(
                  () ->
                      new CatalogProblem(
                          404, "score_run_not_found", "Published score run not found."));
      if (query.format() != null && !query.format().equals(run.format_name()))
        throw CatalogProblem.query("The score run belongs to another format.");
    } else {
      String format = query.format() == null ? RankingQuery.DEFAULT_FORMAT : query.format();
      String active =
          formats.stream()
              .filter(candidate -> candidate.format_name().equals(format))
              .map(RankedFormat::score_run_id)
              .findFirst()
              .orElseThrow(
                  () ->
                      new CatalogProblem(
                          503,
                          "rankings_unavailable",
                          "No published rankings are available for this format yet."));
      run = repository.run(active).orElseThrow();
    }
    ScoreMethod method = method(run, query.method());
    String output = method.outputs().getFirst();
    long total = repository.count(run.score_run_id(), method.method_id(), output, query);
    return new RankingPage(
        run,
        method.method_id(),
        output,
        formats,
        repository.activeCatalog(),
        total,
        query.offset(),
        query.limit(),
        repository.page(run.score_run_id(), method.method_id(), output, query));
  }

  /** An explicit method must exist in the run; the default falls back to the run's first. */
  private static ScoreMethod method(ScoreRunSummary run, String requested) {
    String wanted = requested == null ? RankingQuery.DEFAULT_METHOD : requested;
    for (ScoreMethod method : run.methods()) if (method.method_id().equals(wanted)) return method;
    if (requested != null) throw CatalogProblem.query("Unknown score method for this run.");
    return run.methods().getFirst();
  }
}
