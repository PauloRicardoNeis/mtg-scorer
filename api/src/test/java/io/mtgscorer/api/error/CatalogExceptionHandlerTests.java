package io.mtgscorer.api.error;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.sql.SQLException;
import java.util.UUID;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.DataRetrievalFailureException;
import org.springframework.dao.QueryTimeoutException;
import org.springframework.http.ProblemDetail;
import org.springframework.jdbc.BadSqlGrammarException;
import org.springframework.jdbc.CannotGetJdbcConnectionException;
import org.springframework.mock.web.MockHttpServletRequest;

class CatalogExceptionHandlerTests {
  private final CatalogExceptionHandler handler = new CatalogExceptionHandler();
  private final MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/cards");

  @Test
  void catalogProblemsKeepTheirStatusCodeAndDetail() {
    ProblemDetail problem =
        handler.catalog(
            new CatalogProblem(404, "card_not_found", "Card not found in this catalog."), request);

    assertThat(problem.getType()).isEqualTo(URI.create("about:blank"));
    assertThat(problem.getStatus()).isEqualTo(404);
    assertThat(problem.getTitle()).isEqualTo("Not Found");
    assertThat(problem.getDetail()).isEqualTo("Card not found in this catalog.");
    assertThat(problem.getInstance()).isEqualTo(URI.create("/api/v1/cards"));
    assertThat(problem.getProperties()).containsEntry("code", "card_not_found");
    assertThat(UUID.fromString((String) problem.getProperties().get("request_id"))).isNotNull();
  }

  @Test
  void factoriesUseTheStableQueryAndCursorCodes() {
    var query = CatalogProblem.query("Invalid rarity.");
    assertThat(query.status()).isEqualTo(400);
    assertThat(query.code()).isEqualTo("invalid_query");
    assertThat(query.getMessage()).isEqualTo("Invalid rarity.");

    var cursor = CatalogProblem.cursor();
    assertThat(cursor.status()).isEqualTo(400);
    assertThat(cursor.code()).isEqualTo("invalid_cursor");
    assertThat(cursor.getMessage()).isEqualTo("The cursor does not match this request.");
  }

  @Test
  void everyProblemHasItsOwnRequestId() {
    var first = handler.catalog(CatalogProblem.cursor(), request).getProperties().get("request_id");
    var second =
        handler.catalog(CatalogProblem.cursor(), request).getProperties().get("request_id");

    assertThat(first).isNotEqualTo(second);
  }

  static Stream<Arguments> unavailable() {
    return Stream.of(
        Arguments.of("resource failure", new DataAccessResourceFailureException("sensitive")),
        Arguments.of("no connection", new CannotGetJdbcConnectionException("sensitive")),
        Arguments.of("query timeout", new QueryTimeoutException("sensitive")),
        Arguments.of("connection exception", wrapping(sql("08006"))),
        Arguments.of("insufficient resources", wrapping(sql("53300"))),
        Arguments.of("query canceled", wrapping(sql("57014"))),
        Arguments.of("admin shutdown", wrapping(sql("57P01"))),
        Arguments.of("insufficient privilege", wrapping(sql("42501"))),
        Arguments.of("missing relation", wrapping(sql("42P01"))),
        Arguments.of(
            "nested connection failure",
            wrapping(new IllegalStateException("sensitive", sql("08001")))));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("unavailable")
  void transientAndDeploymentFailuresAreAnUnavailableCatalog(
      String name, DataAccessException error) {
    ProblemDetail problem = handler.database(error, request);

    assertThat(problem.getType()).isEqualTo(URI.create("about:blank"));
    assertThat(problem.getStatus()).isEqualTo(503);
    assertThat(problem.getProperties()).containsEntry("code", "catalog_unavailable");
    assertThat(problem.getDetail())
        .isEqualTo("The catalog is temporarily unavailable. Retry shortly.");
    assertThat(problem.getInstance()).isEqualTo(URI.create("/api/v1/cards"));
  }

  static Stream<Arguments> internal() {
    return Stream.of(
        Arguments.of("syntax error", new BadSqlGrammarException("task", "SELECT", sql("42601"))),
        Arguments.of("unique violation", wrapping(sql("23505"))),
        Arguments.of("undefined column", wrapping(sql("42703"))),
        Arguments.of("no SQL state", wrapping(new SQLException("sensitive"))),
        Arguments.of("no SQL cause", wrapping(new IllegalStateException("sensitive"))),
        Arguments.of("no cause", new DataRetrievalFailureException("sensitive")));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("internal")
  void otherDatabaseFailuresAreSanitizedInternalErrors(String name, DataAccessException error) {
    ProblemDetail problem = handler.database(error, request);

    assertThat(problem.getType()).isEqualTo(URI.create("about:blank"));
    assertThat(problem.getStatus()).isEqualTo(500);
    assertThat(problem.getProperties()).containsEntry("code", "internal_error");
    assertThat(problem.getDetail()).isEqualTo("An unexpected error occurred.");
  }

  private static SQLException sql(String state) {
    return new SQLException("sensitive", state);
  }

  private static DataAccessException wrapping(Throwable cause) {
    return new DataRetrievalFailureException("sensitive", cause);
  }
}
