package dev.mtgscorer.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.boot.test.web.server.LocalServerPort;

@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class MtgScorerApiApplicationTests {

    @LocalServerPort private int port;

    @Test
    void searchesThePublishedCatalogThroughTheVersionedApi()
            throws IOException, InterruptedException {
        var request = HttpRequest.newBuilder()
                .uri(URI.create(
                        "http://localhost:%d/api/v1/cards?rarity=rare&sort=buildaround"
                                .formatted(port)))
                .GET()
                .build();

        var response = HttpClient.newHttpClient()
                .send(request, HttpResponse.BodyHandlers.ofString());

        assertEquals(200, response.statusCode());
        assertTrue(response.body().contains("\"contractVersion\":\"card-catalog-v1\""));
        assertTrue(response.body().contains("\"catalogKind\":\"DEMONSTRATION\""));
        assertTrue(response.body().contains("\"name\":\"Example Engine\""));
        assertTrue(response.body().contains("\"total\":1"));
    }

    @Test
    void returnsNotFoundForAnUnknownOracleId() throws IOException, InterruptedException {
        var request = HttpRequest.newBuilder()
                .uri(URI.create("http://localhost:%d/api/v1/cards/missing".formatted(port)))
                .GET()
                .build();

        var response = HttpClient.newHttpClient()
                .send(request, HttpResponse.BodyHandlers.discarding());

        assertEquals(404, response.statusCode());
    }
}
