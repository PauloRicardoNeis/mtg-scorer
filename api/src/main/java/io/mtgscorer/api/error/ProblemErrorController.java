package io.mtgscorer.api.error;

import io.swagger.v3.oas.annotations.Hidden;
import jakarta.servlet.RequestDispatcher;
import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import org.springframework.boot.webmvc.error.ErrorController;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Keeps servlet error dispatches consistent with Spring MVC's Problem Details responses. */
@Hidden
@RestController
public class ProblemErrorController implements ErrorController {

  @RequestMapping("${spring.web.error.path:${error.path:/error}}")
  public ProblemDetail error(HttpServletRequest request) {
    Object statusAttribute = request.getAttribute(RequestDispatcher.ERROR_STATUS_CODE);
    HttpStatus status = statusAttribute instanceof Integer code ? HttpStatus.resolve(code) : null;
    if (status == null || !status.isError()) {
      status = HttpStatus.INTERNAL_SERVER_ERROR;
    }

    String detail =
        status.is5xxServerError()
            ? "An unexpected error occurred."
            : "The request could not be completed.";
    ProblemDetail problem = ProblemDetail.forStatusAndDetail(status, detail);
    Object originalUri = request.getAttribute(RequestDispatcher.ERROR_REQUEST_URI);
    problem.setInstance(
        URI.create(originalUri instanceof String path ? path : request.getRequestURI()));
    problem.setProperty("code", status.is5xxServerError() ? "internal_error" : "invalid_query");
    problem.setProperty("request_id", java.util.UUID.randomUUID().toString());
    return problem;
  }
}
