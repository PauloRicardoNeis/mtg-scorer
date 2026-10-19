package io.mtgscorer.api.config;

import static org.assertj.core.api.Assertions.assertThat;

import io.mtgscorer.api.rankings.RankingQuery;
import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.PathItem;
import io.swagger.v3.oas.models.Paths;
import io.swagger.v3.oas.models.media.ObjectSchema;
import io.swagger.v3.oas.models.media.Schema;
import io.swagger.v3.oas.models.parameters.Parameter;
import io.swagger.v3.oas.models.responses.ApiResponse;
import io.swagger.v3.oas.models.responses.ApiResponses;
import java.math.BigDecimal;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;

/** The rankings contract mirrors RankingQuery; springdoc only sees an opaque map. */
class RankingOpenApiTests {
  private final OpenAPI api = customized();

  private Map<String, Parameter> parameters() {
    return api.getPaths().get("/api/v1/rankings").getGet().getParameters().stream()
        .collect(Collectors.toMap(Parameter::getName, parameter -> parameter));
  }

  @Test
  void theRankingOperationDocumentsExactlyItsQueryParameters() {
    assertThat(
            api.getPaths().get("/api/v1/rankings").getGet().getParameters().stream()
                .map(Parameter::getName))
        .containsExactlyElementsOf(RankingQuery.PARAMETERS.stream().sorted().toList());
    assertThat(parameters().values())
        .allSatisfy(parameter -> assertThat(parameter.getRequired()).isFalse());
  }

  @Test
  void rankingOnlyParametersStateTheirDefaultsAndBounds() {
    var parameters = parameters();
    assertThat(parameters.get("format").getSchema().getDefault())
        .isEqualTo(RankingQuery.DEFAULT_FORMAT);
    assertThat(parameters.get("format").getSchema().getPattern())
        .isEqualTo("^[A-Za-z0-9][A-Za-z0-9 ]{0,39}$");
    assertThat(parameters.get("method").getSchema().getDefault())
        .isEqualTo(RankingQuery.DEFAULT_METHOD);
    assertThat(parameters.get("method").getDescription()).isNotBlank();
    assertThat(parameters.get("sort").getSchema().getEnum())
        .containsExactlyElementsOf(RankingQuery.SORTS);
    assertThat(parameters.get("sort").getSchema().getDefault()).isEqualTo("score");
    assertThat(parameters.get("sort").getDescription()).isNotBlank();
    Schema<?> offset = parameters.get("offset").getSchema();
    assertThat(offset.getMinimum()).isEqualByComparingTo(BigDecimal.ZERO);
    assertThat(offset.getMaximum()).isEqualByComparingTo(BigDecimal.valueOf(10_000));
    assertThat(parameters.get("score_run_id").getSchema().getPattern())
        .isEqualTo("^scores-[0-9a-f]{64}$");
    assertThat(parameters.get("score_run_id").getDescription()).isNotBlank();
    assertThat(parameters.get("format").getDescription()).isNull();
  }

  @Test
  void sharedFiltersKeepTheCatalogsBounds() {
    var parameters = parameters();
    assertThat(parameters.get("q").getSchema().getMaxLength()).isEqualTo(100);
    assertThat(parameters.get("limit").getSchema().getDefault())
        .isEqualTo(RankingQuery.DEFAULT_LIMIT);
    assertThat(parameters.get("color").getExplode()).isTrue();
    assertThat(parameters.get("type").getDescription()).isNotBlank();
  }

  @Test
  void rankingProblemsAreDocumentedWithTheirStableCodes() {
    assertThat(api.getPaths().get("/api/v1/rankings").getGet().getResponses().keySet())
        .contains("400", "404", "503", "500");
    Schema<?> code =
        (Schema<?>)
            api.getComponents().getSchemas().get("CatalogError").getProperties().get("code");
    assertThat(code.getEnum().stream().map(Object::toString))
        .contains("rankings_unavailable", "score_run_not_found");
  }

  @Test
  void aPreviewPrintingIsAPrintingOrAnExplicitNull() {
    Schema<?> preview =
        (Schema<?>)
            api.getComponents()
                .getSchemas()
                .get("RankedCard")
                .getProperties()
                .get("preview_printing");

    assertThat(preview.getAnyOf()).hasSize(2);
    assertThat(preview.getAnyOf().get(0).get$ref()).isEqualTo("#/components/schemas/Printing");
    assertThat(preview.getAnyOf().get(1).getTypes()).isEqualTo(Set.of("null"));
    assertThat(api.getComponents().getSchemas().get("RankedCard").getRequired())
        .contains("preview_printing");
  }

  private static OpenAPI customized() {
    var api = new OpenAPI().paths(new Paths()).components(new Components());
    api.getPaths()
        .addPathItem(
            "/api/v1/rankings",
            new PathItem()
                .get(
                    new Operation()
                        .responses(
                            new ApiResponses()
                                .addApiResponse("200", new ApiResponse().description("OK")))));
    api.getComponents()
        .addSchemas(
            "RankedCard",
            new ObjectSchema()
                .addProperty("name", new Schema<>().type("string"))
                .addProperty(
                    "preview_printing", new Schema<>().$ref("#/components/schemas/Printing")));
    new CatalogOpenApi().catalogContract().customise(api);
    return api;
  }
}
