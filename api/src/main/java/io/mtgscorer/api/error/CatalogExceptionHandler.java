package io.mtgscorer.api.error;

import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import java.sql.SQLException;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.QueryTimeoutException;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class CatalogExceptionHandler {
  private static final Logger LOG = LoggerFactory.getLogger(CatalogExceptionHandler.class);

  @ExceptionHandler(CatalogProblem.class)
  ProblemDetail catalog(CatalogProblem error, HttpServletRequest request) {
    return problem(error.status(), error.code(), error.getMessage(), request);
  }

  @ExceptionHandler(DataAccessException.class)
  ProblemDetail database(DataAccessException error, HttpServletRequest request) {
    boolean unavailable =
        error instanceof DataAccessResourceFailureException
            || error instanceof QueryTimeoutException;
    for (Throwable cause = error; cause != null; cause = cause.getCause()) {
      if (cause instanceof SQLException sql && sql.getSQLState() != null) {
        String state = sql.getSQLState();
        unavailable |=
            state.startsWith("08")
                || state.startsWith("53")
                || state.startsWith("57")
                || state.equals("42501")
                || state.equals("42P01");
      }
    }
    ProblemDetail result =
        problem(
            unavailable ? 503 : 500,
            unavailable ? "catalog_unavailable" : "internal_error",
            unavailable
                ? "The catalog is temporarily unavailable. Retry shortly."
                : "An unexpected error occurred.",
            request);
    LOG.error(
        "catalog database failure request={}", result.getProperties().get("request_id"), error);
    return result;
  }

  static ProblemDetail problem(int status, String code, String detail, HttpServletRequest request) {
    ProblemDetail result =
        ProblemDetail.forStatusAndDetail(
            org.springframework.http.HttpStatusCode.valueOf(status), detail);
    result.setInstance(URI.create(request.getRequestURI()));
    result.setProperty("code", code);
    result.setProperty("request_id", UUID.randomUUID().toString());
    return result;
  }
}
