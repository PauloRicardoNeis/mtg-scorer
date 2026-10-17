package io.mtgscorer.api;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.mtgscorer.api.error.CatalogProblem;
import io.mtgscorer.api.imports.CatalogImportController;
import org.junit.jupiter.api.Test;

class CatalogImportAuthorizationTests {
  @Test
  void missingOrShortServerCredentialDisablesBothEndpointsBeforeDatabaseAccess() {
    for (String token : new String[] {"", "short"}) {
      var controller = new CatalogImportController(null, token);
      assertThatThrownBy(() -> controller.request("Bearer " + token))
          .isInstanceOfSatisfying(
              CatalogProblem.class,
              p ->
                  org.assertj.core.api.Assertions.assertThat(p.code())
                      .isEqualTo("admin_unavailable"));
      assertThatThrownBy(() -> controller.get("Bearer " + token, "invalid"))
          .isInstanceOfSatisfying(
              CatalogProblem.class,
              p -> org.assertj.core.api.Assertions.assertThat(p.status()).isEqualTo(503));
    }
  }
}
