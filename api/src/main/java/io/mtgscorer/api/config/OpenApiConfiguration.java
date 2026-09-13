package io.mtgscorer.api.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.boot.info.BuildProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class OpenApiConfiguration {

  @Bean
  OpenAPI openApi(BuildProperties build) {
    return new OpenAPI()
        .info(
            new Info()
                .title("MTG Scorer API")
                .version(build.getVersion())
                .description(
                    "Guest catalog and immutable snapshot queries over Python-published data. No tournament evidence or scores."));
  }
}
