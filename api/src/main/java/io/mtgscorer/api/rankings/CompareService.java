package io.mtgscorer.api.rankings;

import static io.mtgscorer.api.rankings.RankingModels.*;

import io.mtgscorer.api.error.CatalogProblem;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class CompareService {
  private final CompareRepository repository;
  private final RankingRepository rankings;

  public CompareService(CompareRepository repository, RankingRepository rankings) {
    this.repository = repository;
    this.rankings = rankings;
  }

  public ComparePage compare(CompareQuery requested) {
    List<CompareFormat> available = repository.formats();
    List<CompareFormat> formats =
        requested.formats().isEmpty()
            ? available
            : available.stream()
                .filter(f -> requested.formats().contains(f.format_name()))
                .toList();
    if (formats.isEmpty())
      throw new CatalogProblem(
          503,
          "rankings_unavailable",
          "No published constructed scores are available for these formats yet.");
    // A column of a format that is not compared falls back to the best format.
    boolean compared =
        requested.sortFormat() == null
            || formats.stream().anyMatch(f -> f.format_name().equals(requested.sortFormat()));
    CompareQuery query =
        compared
            ? requested
            : new CompareQuery(
                requested.formats(),
                requested.q(),
                requested.colors(),
                requested.every(),
                "best",
                null,
                null,
                "desc",
                requested.limit(),
                requested.offset());
    List<String> runs = formats.stream().map(CompareFormat::score_run_id).toList();
    return new ComparePage(
        formats,
        available,
        rankings.activeCatalog(),
        repository.count(runs, query),
        query.offset(),
        query.limit(),
        query.sort(),
        query.order(),
        query.every(),
        repository.page(runs, query));
  }
}
