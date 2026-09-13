package io.mtgscorer.api.info;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.util.List;
import org.springframework.boot.info.BuildProperties;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Tag(name = "Application", description = "Application metadata")
public class InfoController {

  private final InfoResponse info;

  public InfoController(BuildProperties build) {
    this.info =
        new InfoResponse(
            build.getName(),
            build.getVersion(),
            List.of("application-info", "health", "openapi", "catalog", "snapshots"));
  }

  @GetMapping(value = "/api/v1/info", produces = MediaType.APPLICATION_JSON_VALUE)
  @Operation(summary = "Get application version and available capabilities")
  public InfoResponse info() {
    return info;
  }
}
