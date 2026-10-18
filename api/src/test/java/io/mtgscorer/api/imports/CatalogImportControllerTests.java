package io.mtgscorer.api.imports;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.mtgscorer.api.error.CatalogExceptionHandler;
import io.mtgscorer.api.error.CatalogProblem;
import io.mtgscorer.api.imports.CatalogImportModels.ImportJob;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Stream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

@ExtendWith(MockitoExtension.class)
class CatalogImportControllerTests {
  private static final String PATH = "/api/v1/admin/catalog-imports";
  // A test-only credential at the 32-character minimum.
  private static final String TOKEN = "test-token-0123456789abcdef01234";
  private static final UUID JOB = UUID.fromString("b0000000-0000-4000-8000-0000000000e1");
  private static final ImportJob QUEUED =
      new ImportJob(
          JOB,
          PATH + "/" + JOB,
          "queued",
          "queued",
          "2026-05-01T12:00:00+00:00",
          null,
          "2026-05-01T12:00:00+00:00",
          null,
          null,
          null,
          null,
          null,
          Map.of(),
          Map.of(),
          null,
          null);

  @Mock private CatalogImportService service;
  private MockMvc mvc;

  @BeforeEach
  void setUp() {
    mvc = mvc(TOKEN);
  }

  @Test
  void queuingAnImportPointsToItsStatus() throws Exception {
    when(service.request()).thenReturn(QUEUED);

    mvc.perform(post(PATH).header("Authorization", "Bearer " + TOKEN))
        .andExpect(status().isAccepted())
        .andExpect(header().string("Location", PATH + "/" + JOB))
        .andExpect(jsonPath("$.job_id").value(JOB.toString()))
        .andExpect(jsonPath("$.state").value("queued"));
  }

  @Test
  void statusAcceptsAJobIdInAnyHexCase() throws Exception {
    when(service.status(JOB)).thenReturn(QUEUED);

    mvc.perform(
            get(PATH + "/{job_id}", JOB.toString().toUpperCase())
                .header("Authorization", "Bearer " + TOKEN))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.status_url").value(PATH + "/" + JOB));
  }

  @Test
  void malformedJobIdsAreRejectedAfterAuthorization() throws Exception {
    for (String id : new String[] {"not-a-uuid", "1-1-1-1-1"}) {
      mvc.perform(get(PATH + "/{job_id}", id).header("Authorization", "Bearer " + TOKEN))
          .andExpect(status().isBadRequest())
          .andExpect(jsonPath("$.code").value("invalid_query"))
          .andExpect(jsonPath("$.detail").value("Invalid import job ID."));
      // Without a credential, the ID is not even looked at.
      mvc.perform(get(PATH + "/{job_id}", id))
          .andExpect(status().isUnauthorized())
          .andExpect(jsonPath("$.code").value("unauthorized"));
    }
    verifyNoInteractions(service);
  }

  @Test
  void anUnknownJobIsAProblemDetail() throws Exception {
    when(service.status(JOB))
        .thenThrow(new CatalogProblem(404, "import_not_found", "Import job not found."));

    mvc.perform(get(PATH + "/{job_id}", JOB).header("Authorization", "Bearer " + TOKEN))
        .andExpect(status().isNotFound())
        .andExpect(content().contentType("application/problem+json"))
        .andExpect(jsonPath("$.code").value("import_not_found"))
        .andExpect(jsonPath("$.instance").value(PATH + "/" + JOB));
  }

  static Stream<Arguments> rejectedCredentials() {
    return Stream.of(
        Arguments.of("missing", null),
        Arguments.of("empty", ""),
        Arguments.of("scheme only", "Bearer"),
        Arguments.of("token without scheme", TOKEN),
        Arguments.of("other scheme", "Basic " + TOKEN),
        Arguments.of("other token", "Bearer " + TOKEN.toUpperCase()),
        Arguments.of("token prefix", "Bearer " + TOKEN.substring(0, 31)),
        Arguments.of("trailing space", "Bearer " + TOKEN + " "));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("rejectedCredentials")
  void bothEndpointsRequireTheExactBearerCredential(String name, String authorization)
      throws Exception {
    for (var request : new MockHttpServletRequestBuilder[] {post(PATH), get(PATH + "/" + JOB)}) {
      if (authorization != null) request.header("Authorization", authorization);
      mvc.perform(request)
          .andExpect(status().isUnauthorized())
          .andExpect(content().contentType("application/problem+json"))
          .andExpect(jsonPath("$.code").value("unauthorized"))
          .andExpect(jsonPath("$.detail").value("A valid administrative credential is required."));
    }
    verifyNoInteractions(service);
  }

  @Test
  void aServerCredentialShorterThan32CharactersDisablesAdministration() throws Exception {
    String shortToken = TOKEN.substring(1);
    var disabled = mvc(shortToken);

    disabled
        .perform(post(PATH).header("Authorization", "Bearer " + shortToken))
        .andExpect(status().isServiceUnavailable())
        .andExpect(jsonPath("$.code").value("admin_unavailable"));
    assertThatThrownBy(
            () ->
                new CatalogImportController(service, shortToken)
                    .get("Bearer " + shortToken, JOB.toString()))
        .isInstanceOfSatisfying(
            CatalogProblem.class, problem -> assertThat(problem.status()).isEqualTo(503));
    verifyNoInteractions(service);
  }

  private MockMvc mvc(String token) {
    return MockMvcBuilders.standaloneSetup(new CatalogImportController(service, token))
        .setControllerAdvice(new CatalogExceptionHandler())
        .build();
  }
}
