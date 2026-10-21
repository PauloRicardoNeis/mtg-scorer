package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class RankingService {
  private final RankingRepository repository;

  public RankingService(RankingRepository repository) {
    this.repository = repository;
  }

  public RankingPage rankings(RankingQuery query) {
    var formats = repository.activeFormats();
    String fallback =
        formats.stream()
                .anyMatch(format -> format.format_name().equals(RankingQuery.DEFAULT_FORMAT))
            ? RankingQuery.DEFAULT_FORMAT
            : RankingQuery.FALLBACK_FORMAT;
    ScoreRunSummary run = run(repository, formats, query.format(), query.scoreRun(), fallback);
    ScoreMethod method = method(run, query.method());
    String output = method.outputs().getFirst();
    String id = run.score_run_id();
    String previous = repository.previousRun(run, method.method_id());
    long total = repository.count(id, previous, method.method_id(), output, query);
    return new RankingPage(
        run,
        method.method_id(),
        output,
        formats,
        repository.activeCatalog(),
        total,
        query.offset(),
        query.limit(),
        query.sort(),
        query.order(),
        query.view(),
        repository.viewCounts(id, previous, method.method_id(), output, query),
        previous,
        repository.maxDeckCount(id),
        repository.windows(run.format_name()),
        repository.pricesUpdatedAt(),
        repository.page(id, previous, method.method_id(), output, query));
  }

  /**
   * The pinned run, which must belong to the format when both are given, else the format's active
   * run; without either, the fallback format's.
   */
  static ScoreRunSummary run(
      RankingRepository repository,
      List<RankedFormat> formats,
      String format,
      String scoreRun,
      String fallback) {
    if (scoreRun != null) {
      // A pinned run keeps every page of a listing on the same published results.
      ScoreRunSummary run =
          repository
              .run(scoreRun)
              .orElseThrow(
                  () ->
                      new CatalogProblem(
                          404, "score_run_not_found", "Published score run not found."));
      if (format != null && !format.equals(run.format_name()))
        throw CatalogProblem.query("The score run belongs to another format.");
      return run;
    }
    String shown = format == null ? fallback : format;
    String active =
        formats.stream()
            .filter(candidate -> candidate.format_name().equals(shown))
            .map(RankedFormat::score_run_id)
            .findFirst()
            .orElseThrow(
                () ->
                    new CatalogProblem(
                        503,
                        "rankings_unavailable",
                        "No published rankings are available for this format yet."));
    return repository.run(active).orElseThrow();
  }

  /**
   * An explicit method must exist in the run; without one, the first preferred method the run has,
   * else the run's first.
   */
  private static ScoreMethod method(ScoreRunSummary run, String requested) {
    if (requested != null)
      return run.methods().stream()
          .filter(method -> method.method_id().equals(requested))
          .findFirst()
          .orElseThrow(() -> CatalogProblem.query("Unknown score method for this run."));
    for (String preferred : RankingQuery.PREFERRED_METHODS)
      for (ScoreMethod method : run.methods())
        if (method.method_id().equals(preferred)) return method;
    return run.methods().getFirst();
  }
}
