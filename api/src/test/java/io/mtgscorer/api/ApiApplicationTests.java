package io.mtgscorer.api;

import static org.assertj.core.api.Assertions.assertThat;

import io.swagger.v3.oas.annotations.Hidden;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.info.BuildProperties;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Import;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@SpringBootTest(
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = {
      "spring.web.error.path=/test/error",
      "spring.datasource.url=jdbc:postgresql://127.0.0.1:1/unavailable",
      "spring.flyway.enabled=false"
    })
@Import(ApiApplicationTests.FailureController.class)
class ApiApplicationTests {

  private final HttpClient client =
      HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();

  @LocalServerPort private int port;

  @Autowired private ObjectMapper mapper;

  @Autowired private BuildProperties build;

  @Test
  void infoReportsTheBuildAndOnlyImplementedCapabilities() throws Exception {
    HttpResponse<String> response = get("/api/v1/info");

    assertThat(response.statusCode()).isEqualTo(200);
    assertThat(response.headers().firstValue("Content-Type")).hasValue("application/json");
    JsonNode body = mapper.readTree(response.body());
    assertThat(body.path("name").asString()).isEqualTo("mtg-scorer-api");
    assertThat(body.path("version").asString()).isEqualTo(build.getVersion()).isNotBlank();
    assertThat(body.path("capabilities"))
        .isEqualTo(
            mapper.readTree(
                "[\"application-info\",\"health\",\"openapi\",\"catalog\",\"snapshots\"]"));
  }

  @Test
  void healthIsUpWithoutDatabaseOrPythonAndHidesInternalDetails() throws Exception {
    HttpResponse<String> response = get("/actuator/health/liveness");

    assertThat(response.statusCode()).isEqualTo(200);
    JsonNode body = mapper.readTree(response.body());
    assertThat(body.path("status").asString()).isEqualTo("UP");
    assertThat(body.has("components")).isFalse();
    assertThat(body.has("details")).isFalse();
    assertProblem(get("/actuator/env"), 404, "Not Found", "/actuator/env");
  }

  @Test
  void openApiDescribesOnlyImplementedEndpointsAndTheInfoSchema() throws Exception {
    HttpResponse<String> response = get("/v3/api-docs");

    assertThat(response.statusCode()).isEqualTo(200);
    JsonNode document = mapper.readTree(response.body());
    assertThat(document.path("openapi").asString()).startsWith("3.");
    assertThat(document.at("/info/title").asString()).isEqualTo("MTG Scorer API");
    assertThat(document.at("/info/version").asString()).isEqualTo(build.getVersion());
    assertThat(document.path("paths").propertyNames())
        .contains(
            "/api/v1/info",
            "/actuator/health",
            "/api/v1/cards",
            "/api/v1/cards/{oracle_id}",
            "/api/v1/cards/{oracle_id}/printings",
            "/api/v1/snapshots",
            "/api/v1/snapshots/{catalog_snapshot_id}");
    assertThat(
            document
                .at(
                    "/paths/~1api~1v1~1info/get/responses/200/content/application~1json/schema/$ref")
                .asString())
        .isEqualTo("#/components/schemas/InfoResponse");
    assertThat(document.at("/components/schemas/InfoResponse/properties").propertyNames())
        .containsExactlyInAnyOrder("name", "version", "capabilities");
  }

  @Test
  void swaggerEntryPointRedirectsToTheUi() throws Exception {
    HttpResponse<String> response = get("/swagger-ui.html");

    assertThat(response.statusCode()).isEqualTo(302);
    assertThat(response.headers().firstValue("Location")).hasValue("/swagger-ui/index.html");
  }

  @Test
  void swaggerUiServesItsAssetsAndPointsToOurSpecification() throws Exception {
    HttpResponse<String> page = get("/swagger-ui/index.html");
    assertThat(page.statusCode()).isEqualTo(200);
    assertThat(page.body()).contains("Swagger UI", "swagger-ui-bundle.js");
    assertThat(get("/swagger-ui/swagger-ui-bundle.js").statusCode()).isEqualTo(200);
    assertThat(get("/swagger-ui/swagger-ui.css").statusCode()).isEqualTo(200);

    HttpResponse<String> initializer = get("/swagger-ui/swagger-initializer.js");
    assertThat(initializer.statusCode()).isEqualTo(200);
    assertThat(initializer.body())
        .contains("/v3/api-docs/swagger-config")
        .doesNotContain("petstore");

    HttpResponse<String> config = get("/v3/api-docs/swagger-config");
    assertThat(config.statusCode()).isEqualTo(200);
    assertThat(mapper.readTree(config.body()).path("url").asString()).isEqualTo("/v3/api-docs");
  }

  @Test
  void unknownRoutesReturnProblemDetails() throws Exception {
    assertProblem(get("/api/v1/not-a-route"), 404, "Not Found", "/api/v1/not-a-route");
  }

  @Test
  void unavailableDatabaseIsNotAnEmptyCatalog() throws Exception {
    HttpResponse<String> response = get("/api/v1/cards");
    assertProblem(response, 503, "Service Unavailable", "/api/v1/cards");
    assertThat(mapper.readTree(response.body()).path("code").asString())
        .isEqualTo("catalog_unavailable");
    assertThat(mapper.readTree(response.body()).path("request_id").asString()).isNotBlank();
  }

  @Test
  void sqlProgrammingFailureIsAnInternalErrorNotUnavailableData() throws Exception {
    HttpResponse<String> response = get("/test/errors/sql");
    assertProblem(response, 500, "Internal Server Error", "/test/errors/sql");
    assertThat(mapper.readTree(response.body()).path("code").asString())
        .isEqualTo("internal_error");
    assertThat(response.body()).doesNotContain("sensitive", "SELECT");
  }

  @Test
  void unsupportedMethodsReturnProblemDetailsAndPreserveAllowHeader() throws Exception {
    HttpResponse<String> response =
        client.send(
            request("/api/v1/info").POST(HttpRequest.BodyPublishers.noBody()).build(),
            HttpResponse.BodyHandlers.ofString());

    assertProblem(response, 405, "Method Not Allowed", "/api/v1/info");
    assertThat(response.headers().firstValue("Allow").orElseThrow()).contains("GET");
  }

  @Test
  void unsupportedRepresentationsReturnProblemDetails() throws Exception {
    HttpResponse<String> response =
        client.send(
            request("/api/v1/info").header("Accept", "application/xml").GET().build(),
            HttpResponse.BodyHandlers.ofString());

    assertProblem(response, 406, "Not Acceptable", "/api/v1/info");
  }

  @Test
  void unexpectedErrorsReturnSanitizedProblemDetailsThroughTheServletContainer() throws Exception {
    HttpResponse<String> response = get("/test/errors/unexpected");

    assertProblem(response, 500, "Internal Server Error", "/test/errors/unexpected");
    assertThat(mapper.readTree(response.body()).path("detail").asString())
        .isEqualTo("An unexpected error occurred.");
    assertThat(response.body()).doesNotContain("sensitive", "IllegalStateException");
  }

  @Test
  void servletRejectionsUseTheSameProblemFormatWithoutLeakingMessages() throws Exception {
    HttpResponse<String> response = get("/test/errors/rejected");

    assertProblem(response, 400, "Bad Request", "/test/errors/rejected");
    assertThat(response.body()).doesNotContain("sensitive");
  }

  private HttpRequest.Builder request(String path) {
    return HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
        .timeout(Duration.ofSeconds(20));
  }

  private HttpResponse<String> get(String path) throws Exception {
    return client.send(request(path).GET().build(), HttpResponse.BodyHandlers.ofString());
  }

  private void assertProblem(
      HttpResponse<String> response, int status, String title, String instance) {
    assertThat(response.statusCode()).isEqualTo(status);
    assertThat(response.headers().firstValue("Content-Type")).hasValue("application/problem+json");
    JsonNode body = mapper.readTree(response.body());
    // RFC 9457 defaults an omitted type to about:blank.
    assertThat(body.path("type").asString("about:blank")).isEqualTo("about:blank");
    assertThat(body.path("title").asString()).isEqualTo(title);
    assertThat(body.path("status").asInt()).isEqualTo(status);
    assertThat(body.path("detail").asString()).isNotBlank();
    assertThat(body.path("instance").asString()).isEqualTo(instance);
    assertThat(body.has("trace")).isFalse();
    assertThat(body.has("exception")).isFalse();
  }

  @Hidden
  @RestController
  static class FailureController {

    @GetMapping("/test/errors/sql")
    void sqlFailure() {
      throw new org.springframework.jdbc.BadSqlGrammarException(
          "sensitive", "SELECT sensitive", new java.sql.SQLException("sensitive", "42601"));
    }

    @GetMapping("/test/errors/unexpected")
    void unexpected() {
      throw new IllegalStateException("sensitive internal failure");
    }

    @GetMapping("/test/errors/rejected")
    void rejected(HttpServletResponse response) throws IOException {
      response.sendError(400, "sensitive internal rejection");
    }
  }
}
