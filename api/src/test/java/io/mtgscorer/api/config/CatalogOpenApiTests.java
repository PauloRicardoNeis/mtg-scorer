package io.mtgscorer.api.config;

import static org.assertj.core.api.Assertions.assertThat;

import io.mtgscorer.api.catalog.CatalogQuery;
import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.PathItem;
import io.swagger.v3.oas.models.Paths;
import io.swagger.v3.oas.models.media.ObjectSchema;
import io.swagger.v3.oas.models.media.Schema;
import io.swagger.v3.oas.models.media.StringSchema;
import io.swagger.v3.oas.models.parameters.Parameter;
import io.swagger.v3.oas.models.responses.ApiResponse;
import io.swagger.v3.oas.models.responses.ApiResponses;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;

/** The documented contract mirrors the strict parser; springdoc only sees opaque maps. */
class CatalogOpenApiTests {
  private static final List<String> CATALOG_PATHS =
      List.of(
          "/api/v1/cards",
          "/api/v1/cards/{oracle_id}",
          "/api/v1/cards/{oracle_id}/printings",
          "/api/v1/snapshots",
          "/api/v1/snapshots/{catalog_snapshot_id}");

  private final OpenAPI api = customized();

  @Test
  void eachCatalogOperationDocumentsExactlyItsQueryParameters() {
    assertThat(parameterNames("/api/v1/cards"))
        .containsExactlyElementsOf(CatalogQuery.CARD_PARAMETERS.stream().sorted().toList());
    assertThat(parameterNames("/api/v1/cards/{oracle_id}/printings"))
        .containsExactlyElementsOf(CatalogQuery.PRINTING_PARAMETERS.stream().sorted().toList());
    assertThat(parameterNames("/api/v1/cards/{oracle_id}")).containsExactly("catalog_snapshot_id");
    assertThat(get("/api/v1/snapshots").getParameters()).isNull();
    assertThat(get("/api/v1/snapshots/{catalog_snapshot_id}").getParameters()).isNull();
    assertThat(get("/api/v1/cards").getParameters())
        .allSatisfy(
            parameter -> {
              assertThat(parameter.getIn()).isEqualTo("query");
              assertThat(parameter.getRequired()).isFalse();
            });
  }

  @Test
  void parameterSchemasStateTheParserBounds() {
    Map<String, Parameter> cards = parameters("/api/v1/cards");
    assertThat(cards.get("q").getSchema().getMaxLength()).isEqualTo(100);
    assertThat(cards.get("cursor").getSchema().getMaxLength()).isEqualTo(4096);
    Schema<?> limit = cards.get("limit").getSchema();
    assertThat(limit.getMinimum()).isEqualByComparingTo(BigDecimal.ONE);
    assertThat(limit.getMaximum()).isEqualByComparingTo(BigDecimal.valueOf(100));
    assertThat(limit.getDefault()).isEqualTo(24);
    assertThat(cards.get("sort").getSchema().getEnum()).containsExactly("name_asc");
    assertThat(cards.get("sort").getSchema().getDefault()).isEqualTo("name_asc");
    assertThat(cards.get("game").getSchema().getEnum())
        .containsExactlyElementsOf(CatalogQuery.GAMES.stream().sorted().toList());
    assertThat(cards.get("type").getSchema().getEnum())
        .containsExactlyElementsOf(CatalogQuery.TYPES.stream().sorted().toList());
    assertThat(cards.get("type").getDescription()).isNotBlank();
    assertThat(cards.get("color_identity").getSchema().getPattern())
        .isEqualTo("^(C|[WUBRG]{1,5})$");
  }

  @Test
  void filterListsAreExplodedArraysWithTheParserLimits() {
    Map<String, Parameter> cards = parameters("/api/v1/cards");
    assertThat(cards.get("set").getSchema().getMaxItems()).isEqualTo(32);
    assertThat(cards.get("rarity").getSchema().getMaxItems()).isEqualTo(6);
    assertThat(cards.get("rarity").getSchema().getItems().getEnum())
        .containsExactlyElementsOf(CatalogQuery.RARITIES.stream().sorted().toList());
    // Colors keep WUBRG order rather than sorting.
    assertThat(cards.get("color").getSchema().getItems().getEnum())
        .containsExactlyElementsOf(CatalogQuery.COLORS);
    assertThat(cards.get("color").getSchema().getMaxItems()).isEqualTo(CatalogQuery.COLORS.size());
    assertThat(cards.get("color").getDescription()).isNotBlank();
    for (String name : List.of("set", "rarity", "color")) {
      assertThat(cards.get(name).getStyle()).as(name).isEqualTo(Parameter.StyleEnum.FORM);
      assertThat(cards.get(name).getExplode()).as(name).isTrue();
    }
    assertThat(cards.get("q").getExplode()).isNull();
  }

  @Test
  void documentedPatternsAgreeWithTheParser() {
    var setCode =
        Pattern.compile(parameters("/api/v1/cards").get("set").getSchema().getItems().getPattern());
    for (String code : List.of("m11", "2x2", "abcdefgh", "M11", "m", "abcdefghi", "m-1"))
      assertThat(setCode.matcher(code).matches())
          .as(code)
          .isEqualTo(accepts(Map.of("set", List.of(code))));

    var snapshot =
        Pattern.compile(
            parameters("/api/v1/cards").get("catalog_snapshot_id").getSchema().getPattern());
    for (String id : List.of("catalog-abc", "c", "Catalog", "-catalog", "c" + "-".repeat(96)))
      assertThat(snapshot.matcher(id).matches())
          .as(id)
          .isEqualTo(accepts(Map.of("catalog_snapshot_id", List.of(id))));
  }

  @Test
  void catalogOperationsReferenceTheStableProblemSchema() {
    for (String path : CATALOG_PATHS) {
      var responses = get(path).getResponses();
      assertThat(responses).as(path).containsKeys("200", "400", "404", "503", "500");
      for (String status : List.of("400", "404", "503", "500"))
        assertThat(problemRef(responses.get(status)))
            .isEqualTo("#/components/schemas/CatalogError");
    }
    Schema<?> error = api.getComponents().getSchemas().get("CatalogError");
    assertThat(error.getProperties())
        .containsOnlyKeys("type", "title", "status", "detail", "instance", "request_id", "code");
    assertThat(error.getProperties().get("code").getEnum())
        .containsExactly(
            "invalid_query",
            "invalid_cursor",
            "snapshot_not_found",
            "card_not_found",
            "catalog_unavailable",
            "internal_error");
  }

  @Test
  void administrativeOperationsDocumentTheirOwnProblems() {
    for (Operation operation :
        List.of(
            api.getPaths().get("/api/v1/admin/catalog-imports").getPost(),
            api.getPaths().get("/api/v1/admin/catalog-imports/{job_id}").getGet())) {
      for (String status : List.of("400", "401", "404", "503", "500"))
        assertThat(problemRef(operation.getResponses().get(status)))
            .isEqualTo("#/components/schemas/ImportError");
      assertThat(operation.getParameters()).isNull();
    }
    Schema<?> error = api.getComponents().getSchemas().get("ImportError");
    assertThat(error.getProperties().get("code").getEnum()).isNull();
  }

  @Test
  void otherOperationsAreLeftAlone() {
    Operation info = get("/api/v1/info");
    assertThat(info.getParameters()).isNull();
    assertThat(info.getResponses()).containsOnlyKeys("200");
  }

  @Test
  void recordSchemasRequireEveryComponentButProblemDetailDoesNot() {
    Map<String, Schema> schemas = api.getComponents().getSchemas();
    assertThat(schemas.get("CardPage").getRequired())
        .containsExactly("catalog_snapshot_id", "items", "next_cursor");
    assertThat(schemas.get("CatalogError").getRequired())
        .containsExactlyInAnyOrderElementsOf(schemas.get("CatalogError").getProperties().keySet());
    assertThat(schemas.get("ProblemDetail").getRequired()).isNull();
    assertThat(schemas.get("Opaque").getRequired()).isNull();
  }

  private static OpenAPI customized() {
    var api = new OpenAPI().paths(new Paths()).components(new Components());
    for (String path : CATALOG_PATHS)
      api.getPaths().addPathItem(path, new PathItem().get(operation()));
    api.getPaths().addPathItem("/api/v1/info", new PathItem().get(operation()));
    api.getPaths().addPathItem("/api/v1/admin/catalog-imports", new PathItem().post(operation()));
    api.getPaths()
        .addPathItem("/api/v1/admin/catalog-imports/{job_id}", new PathItem().get(operation()));
    api.getComponents()
        .addSchemas(
            "CardPage",
            new ObjectSchema()
                .addProperty("catalog_snapshot_id", new StringSchema())
                .addProperty("items", new ObjectSchema())
                .addProperty("next_cursor", new StringSchema()))
        .addSchemas(
            "ProblemDetail",
            new ObjectSchema()
                .addProperty("type", new StringSchema())
                .addProperty("title", new StringSchema()))
        .addSchemas("Opaque", new StringSchema());
    new CatalogOpenApi().catalogContract().customise(api);
    return api;
  }

  private static Operation operation() {
    return new Operation()
        .responses(new ApiResponses().addApiResponse("200", new ApiResponse().description("OK")));
  }

  private Operation get(String path) {
    return api.getPaths().get(path).getGet();
  }

  private List<String> parameterNames(String path) {
    return get(path).getParameters().stream().map(Parameter::getName).toList();
  }

  private Map<String, Parameter> parameters(String path) {
    return get(path).getParameters().stream()
        .collect(Collectors.toMap(Parameter::getName, parameter -> parameter));
  }

  private static String problemRef(ApiResponse response) {
    return response.getContent().get("application/problem+json").getSchema().get$ref();
  }

  private static boolean accepts(Map<String, List<String>> query) {
    try {
      CatalogQuery.parse(query, false);
      return true;
    } catch (RuntimeException rejected) {
      return false;
    }
  }
}
