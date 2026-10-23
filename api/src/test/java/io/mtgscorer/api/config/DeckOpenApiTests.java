package io.mtgscorer.api.config;

import static org.assertj.core.api.Assertions.assertThat;

import io.mtgscorer.api.decks.DeckQuery;
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

/** A card's decks mirror DeckQuery; springdoc only sees an opaque map. */
class DeckOpenApiTests {
  private static final String PATH = "/api/v1/cards/{oracle_id}/decks";
  private static final String DECK = "/api/v1/decks/{score_run_id}/{position}";
  private final OpenAPI api = customized();

  private Map<String, Parameter> parameters() {
    return api.getPaths().get(PATH).getGet().getParameters().stream()
        .collect(Collectors.toMap(Parameter::getName, parameter -> parameter));
  }

  @Test
  void theDeckOperationDocumentsExactlyItsQueryParameters() {
    assertThat(api.getPaths().get(PATH).getGet().getParameters().stream().map(Parameter::getName))
        .containsExactlyElementsOf(DeckQuery.PARAMETERS.stream().sorted().toList());
    assertThat(api.getPaths().get(PATH).getGet().getResponses().keySet())
        .contains("400", "404", "500");
  }

  @Test
  void deckParametersStateTheirOwnDefaultsAndBounds() {
    var parameters = parameters();
    Schema<?> format = parameters.get("format").getSchema();
    assertThat(format.getPattern()).isEqualTo("^[A-Za-z0-9][A-Za-z0-9 /.-]{0,39}$");
    assertThat(format.getDefault()).isNull();
    assertThat(parameters.get("format").getDescription()).isNotBlank();
    assertThat(parameters.get("limit").getSchema().getDefault()).isEqualTo(DeckQuery.DEFAULT_LIMIT);
    assertThat(parameters.get("limit").getSchema().getMaximum())
        .isEqualByComparingTo(BigDecimal.valueOf(DeckQuery.MAX_LIMIT));
    assertThat(parameters.get("offset").getSchema().getMaximum())
        .isEqualByComparingTo(BigDecimal.valueOf(DeckQuery.MAX_OFFSET));
    assertThat(parameters.get("score_run_id").getSchema().getPattern())
        .isEqualTo("^scores-[0-9a-f]{64}$");
    assertThat(parameters.get("score_run_id").getDescription()).isNotBlank();
  }

  @Test
  void aDeckIsReadInOneCatalogAndCanBeMissing() {
    var operation = api.getPaths().get(DECK).getGet();
    assertThat(operation.getParameters().stream().map(Parameter::getName))
        .containsExactly("catalog_snapshot_id");
    assertThat(operation.getResponses().keySet()).contains("400", "404", "503", "500");
    Schema<?> code =
        (Schema<?>)
            api.getComponents().getSchemas().get("CatalogError").getProperties().get("code");
    assertThat(code.getEnum().stream().map(Object::toString)).contains("deck_not_found");
  }

  @Test
  void aPagesRunIsARunOrAnExplicitNull() {
    Schema<?> page = api.getComponents().getSchemas().get("CardDeckPage");
    Schema<?> run = (Schema<?>) page.getProperties().get("run");

    assertThat(run.getAnyOf()).hasSize(2);
    assertThat(run.getAnyOf().get(0).get$ref()).isEqualTo("#/components/schemas/DeckRun");
    assertThat(run.getAnyOf().get(1).getTypes()).isEqualTo(Set.of("null"));
    assertThat(page.getRequired()).contains("run", "items");
  }

  private static OpenAPI customized() {
    var api = new OpenAPI().paths(new Paths()).components(new Components());
    for (String path : java.util.List.of(PATH, DECK))
      api.getPaths()
          .addPathItem(
              path,
              new PathItem()
                  .get(
                      new Operation()
                          .responses(
                              new ApiResponses()
                                  .addApiResponse("200", new ApiResponse().description("OK")))));
    api.getComponents()
        .addSchemas(
            "CardDeckPage",
            new ObjectSchema()
                .addProperty("run", new Schema<>().$ref("#/components/schemas/DeckRun"))
                .addProperty("items", new Schema<>().type("array")));
    new CatalogOpenApi().catalogContract().customise(api);
    return api;
  }
}
