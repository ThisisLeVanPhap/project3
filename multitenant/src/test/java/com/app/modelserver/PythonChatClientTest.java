package com.app.modelserver;

import com.app.modelserver.dto.ChatRequest;
import com.app.modelserver.dto.ChatResponse;
import com.app.modelserver.dto.GenerationConfig;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.util.List;
import static org.junit.jupiter.api.Assertions.assertEquals;

class PythonChatClientTest {

    @Test
    void returnsUnavailableFallbackOnConnectionFailure() throws Exception {
        int port = freePort();
        PythonChatClient client = new PythonChatClient(WebClient.builder(), properties(200, 200));

        ChatResponse response = client.chat("http://127.0.0.1:" + port, request(), false, false);

        assertEquals("Sorry, the chatbot service is unavailable right now. Please try again in a moment.", response.reply());
        assertEquals("base-model", response.model());
        assertEquals("adapter-path", response.adapter());
    }

    @Test
    void returnsTimeoutFallbackOnSlowUpstream() throws Exception {
        HttpServer server = server(exchange -> {
            sleep(500);
            writeJson(exchange, 200, "{\"reply\":\"late\",\"latency_ms\":1,\"model\":\"m\",\"adapter\":\"a\"}");
        });
        try {
            PythonChatClient client = new PythonChatClient(WebClient.builder(), properties(200, 200));

            ChatResponse response = client.chat(baseUrl(server), request(), true, false);

            assertEquals("Sorry, the chatbot is taking longer than expected. Please try again in a moment.", response.reply());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void returnsServerErrorFallbackOnUpstream500() throws Exception {
        HttpServer server = server(exchange -> writeJson(exchange, 500, "{\"detail\":\"boom\"}"));
        try {
            PythonChatClient client = new PythonChatClient(WebClient.builder(), properties(200, 2_000));

            ChatResponse response = client.chat(baseUrl(server), request(), false, true);

            assertEquals("Sorry, the chatbot service had an internal error. Please try again in a moment.", response.reply());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void returnsTenantConfigFallbackOnUpstream422() throws Exception {
        HttpServer server = server(exchange -> writeJson(exchange, 422, "{\"detail\":\"kb missing\"}"));
        try {
            PythonChatClient client = new PythonChatClient(WebClient.builder(), properties(200, 2_000));

            ChatResponse response = client.chat(baseUrl(server), request(), false, false);

            assertEquals("Sorry, this chatbot request could not be processed for the current tenant configuration.", response.reply());
        } finally {
            server.stop(0);
        }
    }

    private static ChatRequest request() {
        return new ChatRequest(
                "hello",
                List.of("hi"),
                new GenerationConfig(
                        "base-model",
                        "adapter-path",
                        null,
                        null,
                        null,
                        null,
                        null,
                        null,
                        null,
                        List.of(),
                        "local",   // provider
                        null,      // api_model
                        null,      // api_key
                        null,      // api_base_url
                        "tenant_sales"  // mode
                ),
                "conv-1",
                "web",
                "tenant-1",
                "tenant_sales"  // mode
        );
    }

    private static LlmProperties properties(int connectTimeoutMs, int responseTimeoutMs) {
        LlmProperties props = new LlmProperties();
        props.setConnectTimeoutMs(connectTimeoutMs);
        props.setResponseTimeoutMs(responseTimeoutMs);
        props.setStartupTimeoutMs(1_000);
        return props;
    }

    private static HttpServer server(ExchangeHandler handler) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/chat", exchange -> {
            try {
                handler.handle(exchange);
            } finally {
                exchange.close();
            }
        });
        server.start();
        return server;
    }

    private static String baseUrl(HttpServer server) {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    private static int freePort() throws IOException {
        try (ServerSocket socket = new ServerSocket(0)) {
            return socket.getLocalPort();
        }
    }

    private static void writeJson(HttpExchange exchange, int status, String body) throws IOException {
        exchange.getRequestBody().readAllBytes();
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream output = exchange.getResponseBody()) {
            output.write(bytes);
        }
    }

    private static void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted during test sleep", e);
        }
    }

    @FunctionalInterface
    private interface ExchangeHandler {
        void handle(HttpExchange exchange) throws IOException;
    }
}
