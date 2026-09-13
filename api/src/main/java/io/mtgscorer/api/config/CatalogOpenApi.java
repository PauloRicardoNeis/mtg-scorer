package io.mtgscorer.api.config;

import io.mtgscorer.api.catalog.CatalogQuery;
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
                if (!path.startsWith("/api/v1/cards") && !path.startsWith("/api/v1/snapshots"))
                  return;
                var operation = item.getGet();
                Set<String> names =
                    path.equals("/api/v1/cards")
                        ? CatalogQuery.CARD_PARAMETERS
                        : path.endsWith("/printings")
                            ? CatalogQuery.PRINTING_PARAMETERS
                            : path.startsWith("/api/v1/cards/")
                                ? Set.of("catalog_snapshot_id")
                                : Set.of();
                names.stream()
                    .sorted()
                    .forEach(name -> operation.addParametersItem(parameter(name)));
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
                      "internal_error")));
      api.getComponents().addSchemas("CatalogError", problem);
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
    if (name.equals("set") || name.equals("rarity"))
      parameter.style(Parameter.StyleEnum.FORM).explode(true);
    return parameter;
  }
}
