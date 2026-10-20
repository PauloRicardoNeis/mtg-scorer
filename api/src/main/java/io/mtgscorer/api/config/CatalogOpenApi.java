package io.mtgscorer.api.config;

import io.mtgscorer.api.catalog.CatalogQuery;
import io.mtgscorer.api.rankings.CompareQuery;
import io.mtgscorer.api.rankings.RankingQuery;
import io.swagger.v3.oas.models.media.*;
import io.swagger.v3.oas.models.parameters.Parameter;
import io.swagger.v3.oas.models.responses.ApiResponse;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import org.springdoc.core.customizers.OpenApiCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** The live Spring contract describes the implemented map-based, strict query parser. */
@Configuration(proxyBeanMethods = false)
public class CatalogOpenApi {
  @Bean
  OpenApiCustomizer catalogContract() {
    return api -> {
      api.getPaths()
          .forEach(
              (path, item) -> {
                if (!path.startsWith("/api/v1/cards")
                    && !path.startsWith("/api/v1/snapshots")
                    && !path.startsWith("/api/v1/rankings")) return;
                var operation = item.getGet();
                boolean rankings = path.equals("/api/v1/rankings");
                boolean compare = path.equals("/api/v1/rankings/compare");
                Set<String> names =
                    compare
                        ? CompareQuery.PARAMETERS
                        : rankings
                            ? RankingQuery.PARAMETERS
                            : path.equals("/api/v1/cards")
                                ? CatalogQuery.CARD_PARAMETERS
                                : path.endsWith("/printings")
                                    ? CatalogQuery.PRINTING_PARAMETERS
                                    : path.startsWith("/api/v1/cards/")
                                        ? Set.of("catalog_snapshot_id")
                                        : Set.of();
                names.stream()
                    .sorted()
                    .forEach(
                        name ->
                            operation.addParametersItem(
                                compare
                                    ? compareParameter(name)
                                    : rankings ? rankingParameter(name) : parameter(name)));
                for (String status : List.of("400", "404", "503", "500")) {
                  operation
                      .getResponses()
                      .addApiResponse(
                          status,
                          new ApiResponse()
                              .description("Sanitized Problem Details with a stable code")
                              .content(
                                  new Content()
                                      .addMediaType(
                                          "application/problem+json",
                                          new MediaType()
                                              .schema(
                                                  new Schema<>()
                                                      .$ref(
                                                          "#/components/schemas/CatalogError")))));
                }
              });
      var problem = new ObjectSchema();
      for (String field : List.of("type", "title", "detail", "instance", "request_id"))
        problem.addProperty(field, new StringSchema());
      problem.addProperty("status", new IntegerSchema());
      problem.addProperty(
          "code",
          new StringSchema()
              ._enum(
                  List.of(
                      "invalid_query",
                      "invalid_cursor",
                      "snapshot_not_found",
                      "card_not_found",
                      "catalog_unavailable",
                      "rankings_unavailable",
                      "score_run_not_found",
                      "internal_error")));
      api.getComponents().addSchemas("CatalogError", problem);
      var adminProblem = new ObjectSchema();
      for (String field : List.of("type", "title", "detail", "instance", "request_id", "code"))
        adminProblem.addProperty(field, new StringSchema());
      adminProblem.addProperty("status", new IntegerSchema());
      api.getComponents().addSchemas("ImportError", adminProblem);
      api.getPaths()
          .forEach(
              (path, item) -> {
                if (!path.startsWith("/api/v1/admin/catalog-imports")) return;
                item.readOperations()
                    .forEach(
                        operation -> {
                          for (String status : List.of("400", "401", "404", "503", "500"))
                            operation
                                .getResponses()
                                .addApiResponse(
                                    status,
                                    new ApiResponse()
                                        .description("Sanitized Problem Details with a stable code")
                                        .content(
                                            new Content()
                                                .addMediaType(
                                                    "application/problem+json",
                                                    new MediaType()
                                                        .schema(
                                                            new Schema<>()
                                                                .$ref(
                                                                    "#/components/schemas/ImportError")))));
                        });
              });
      // A card outside the active catalog has no preview printing: an explicit null.
      Schema<?> ranked = api.getComponents().getSchemas().get("RankedCard");
      if (ranked != null)
        ranked
            .getProperties()
            .put(
                "preview_printing",
                new Schema<>()
                    .anyOf(
                        List.of(
                            new Schema<>().$ref("#/components/schemas/Printing"),
                            new Schema<>().types(Set.of("null"))))
                    .description("Null when the card is not in the active catalog."));
      // Record DTOs always serialize every component, including explicit nulls.
      api.getComponents()
          .getSchemas()
          .forEach(
              (name, schema) -> {
                if (schema.getProperties() != null && !name.equals("ProblemDetail"))
                  schema.setRequired(new ArrayList<>(schema.getProperties().keySet()));
              });
    };
  }

  /** Ranking-only parameters; q, type, color and limit share the catalog's bounds. */
  private Parameter rankingParameter(String name) {
    Schema<?> schema =
        switch (name) {
          case "format" ->
              new StringSchema()
                  .pattern("^[A-Za-z0-9][A-Za-z0-9 /.-]{0,39}$")
                  ._default(RankingQuery.DEFAULT_FORMAT);
          case "method" ->
              new StringSchema()
                  .pattern("^[a-z0-9][a-z0-9-]{0,63}$")
                  ._default(RankingQuery.DEFAULT_METHOD);
          case "sort" -> new StringSchema()._enum(RankingQuery.SORTS)._default("score");
          case "order" -> new StringSchema()._enum(RankingQuery.ORDERS);
          case "view" -> new StringSchema()._enum(RankingQuery.VIEWS)._default("all");
          case "limit" ->
              new IntegerSchema()
                  .minimum(BigDecimal.ONE)
                  .maximum(BigDecimal.valueOf(100))
                  ._default(RankingQuery.DEFAULT_LIMIT);
          case "offset" ->
              new IntegerSchema()
                  .minimum(BigDecimal.ZERO)
                  .maximum(BigDecimal.valueOf(RankingQuery.MAX_OFFSET))
                  ._default(0);
          case "score_run_id" -> new StringSchema().pattern("^scores-[0-9a-f]{64}$");
          default -> null;
        };
    if (schema == null) return parameter(name);
    Parameter parameter = new Parameter().name(name).in("query").required(false).schema(schema);
    if (name.equals("method"))
      parameter.description(
          "A score method in the run; without one, constructed-score, else max-ratio, when"
              + " present.");
    if (name.equals("sort"))
      parameter.description(
          "score orders by the selected method's first output; movement by places gained since"
              + " the previous run; price by the USD price; value by score per dollar.");
    if (name.equals("order"))
      parameter.description("Defaults to desc, except asc for name. Unknown values sort last.");
    if (name.equals("view"))
      parameter.description("risers and fallers keep cards that gained or lost places.");
    if (name.equals("score_run_id"))
      parameter.description("Pin a published run so every page shows the same results.");
    return parameter;
  }

  /** Compare-only parameters; q and color share the catalog's bounds. */
  private Parameter compareParameter(String name) {
    Schema<?> schema =
        switch (name) {
          case "format" ->
              new ArraySchema()
                  .items(new StringSchema().pattern("^[A-Za-z0-9][A-Za-z0-9 /.-]{0,39}$"))
                  .maxItems(CompareQuery.MAX_FORMATS);
          case "method" ->
              new StringSchema()
                  ._enum(CompareQuery.METHODS)
                  ._default(CompareQuery.METHODS.getFirst());
          case "every" -> new BooleanSchema()._default(false);
          case "sort" ->
              new StringSchema()
                  .pattern(
                      "^(best|count|name|[A-Za-z0-9][A-Za-z0-9 /.-]{0,39}:("
                          + String.join(
                              "|", CompareQuery.METRICS.keySet().stream().sorted().toList())
                          + "))$")
                  ._default("best");
          case "order" -> new StringSchema()._enum(RankingQuery.ORDERS);
          case "limit" ->
              new IntegerSchema()
                  .minimum(BigDecimal.ONE)
                  .maximum(BigDecimal.valueOf(200))
                  ._default(CompareQuery.DEFAULT_LIMIT);
          case "offset" -> rankingParameter("offset").getSchema();
          default -> null;
        };
    if (schema == null) return parameter(name);
    Parameter parameter = new Parameter().name(name).in("query").required(false).schema(schema);
    if (name.equals("format"))
      parameter
          .description("Formats to compare; without one, every format the method scored.")
          .style(Parameter.StyleEnum.FORM)
          .explode(true);
    if (name.equals("method"))
      parameter.description(
          "The grading every format ranks by; a format it scored no card in is not compared.");
    if (name.equals("every"))
      parameter.description("Keep only cards ranked in every compared format.");
    if (name.equals("sort"))
      parameter.description(
          "best orders by the highest score in any compared format, count by formats ranked,"
              + " and {format}:{metric} by one column.");
    return parameter;
  }

  private Parameter parameter(String name) {
    Schema<?> schema =
        switch (name) {
          case "q" -> new StringSchema().maxLength(100);
          case "set" ->
              new ArraySchema().items(new StringSchema().pattern("^[a-z0-9]{2,8}$")).maxItems(32);
          case "rarity" ->
              new ArraySchema()
                  .items(new StringSchema()._enum(CatalogQuery.RARITIES.stream().sorted().toList()))
                  .maxItems(6);
          case "game" -> new StringSchema()._enum(CatalogQuery.GAMES.stream().sorted().toList());
          case "color_identity" -> new StringSchema().pattern("^(C|[WUBRG]{1,5})$");
          case "color" ->
              new ArraySchema()
                  .items(new StringSchema()._enum(CatalogQuery.COLORS))
                  .maxItems(CatalogQuery.COLORS.size());
          case "type" -> new StringSchema()._enum(CatalogQuery.TYPES.stream().sorted().toList());
          case "sort" -> new StringSchema()._enum(List.of("name_asc"))._default("name_asc");
          case "limit" ->
              new IntegerSchema()
                  .minimum(BigDecimal.ONE)
                  .maximum(BigDecimal.valueOf(100))
                  ._default(24);
          case "cursor" -> new StringSchema().maxLength(4096);
          default -> new StringSchema().pattern("^[a-z0-9][a-z0-9-]{0,95}$");
        };
    Parameter parameter = new Parameter().name(name).in("query").required(false).schema(schema);
    if (name.equals("color"))
      parameter.description(
          "Card colors; a card matches any selected one. C selects known colorless cards.");
    if (name.equals("type")) parameter.description("A card type on any face's type line.");
    if (Set.of("set", "rarity", "color").contains(name))
      parameter.style(Parameter.StyleEnum.FORM).explode(true);
    return parameter;
  }
}
