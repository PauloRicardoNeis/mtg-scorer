package io.mtgscorer.api.info;

import io.swagger.v3.oas.annotations.media.Schema;
import java.util.List;

@Schema(description = "Application identity and capabilities implemented by this API build.")
public record InfoResponse(
    @Schema(example = "mtg-scorer-api") String name,
    @Schema(description = "API artifact version from the Maven build.", example = "0.1.0-SNAPSHOT")
        String version,
    @Schema(description = "Available capabilities; does not advertise planned functionality.")
        List<String> capabilities) {}
