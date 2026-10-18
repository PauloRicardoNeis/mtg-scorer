package io.mtgscorer.api.error;

import static org.assertj.core.api.Assertions.assertThat;

import jakarta.servlet.RequestDispatcher;
import java.net.URI;
import java.util.UUID;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.http.ProblemDetail;
import org.springframework.mock.web.MockHttpServletRequest;

class ProblemErrorControllerTests {
  private final ProblemErrorController controller = new ProblemErrorController();

  @Test
  void clientErrorsKeepTheirStatusWithAGenericDetail() {
    ProblemDetail problem = controller.error(dispatch(404, "/api/v1/cards/missing"));

    assertThat(problem.getType()).isEqualTo(URI.create("about:blank"));
    assertThat(problem.getStatus()).isEqualTo(404);
    assertThat(problem.getTitle()).isEqualTo("Not Found");
    assertThat(problem.getDetail()).isEqualTo("The request could not be completed.");
    assertThat(problem.getInstance()).isEqualTo(URI.create("/api/v1/cards/missing"));
    assertThat(problem.getProperties()).containsEntry("code", "invalid_query");
    assertThat(UUID.fromString((String) problem.getProperties().get("request_id"))).isNotNull();
  }

  @Test
  void serverErrorsKeepTheirStatusAsSanitizedInternalErrors() {
    ProblemDetail problem = controller.error(dispatch(503, "/api/v1/cards"));

    assertThat(problem.getStatus()).isEqualTo(503);
    assertThat(problem.getDetail()).isEqualTo("An unexpected error occurred.");
    assertThat(problem.getProperties()).containsEntry("code", "internal_error");
  }

  static Stream<Arguments> unusableStatuses() {
    return Stream.of(
        Arguments.of("missing", null),
        Arguments.of("text", "404"),
        Arguments.of("long", 404L),
        Arguments.of("success", 200),
        Arguments.of("redirect", 302),
        Arguments.of("unknown", 999));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("unusableStatuses")
  void anUnusableStatusIsAnInternalError(String name, Object status) {
    ProblemDetail problem = controller.error(dispatch(status, "/api/v1/info"));

    assertThat(problem.getType()).isEqualTo(URI.create("about:blank"));
    assertThat(problem.getStatus()).isEqualTo(500);
    assertThat(problem.getTitle()).isEqualTo("Internal Server Error");
    assertThat(problem.getProperties()).containsEntry("code", "internal_error");
  }

  @Test
  void withoutTheOriginalUriTheInstanceIsTheErrorPath() {
    assertThat(controller.error(dispatch(400, null)).getInstance()).isEqualTo(URI.create("/error"));
    assertThat(controller.error(dispatch(400, URI.create("/api"))).getInstance())
        .isEqualTo(URI.create("/error"));
  }

  private static MockHttpServletRequest dispatch(Object status, Object originalUri) {
    var request = new MockHttpServletRequest("GET", "/error");
    if (status != null) request.setAttribute(RequestDispatcher.ERROR_STATUS_CODE, status);
    if (originalUri != null) request.setAttribute(RequestDispatcher.ERROR_REQUEST_URI, originalUri);
    return request;
  }
}
