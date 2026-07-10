package com.app.modelserver;

import com.app.bots.ChatbotInstance;
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
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PythonChatClientTest {

    @Test
    void returnsUnavailableFallbackOnConnectionFailure() throws Exception {
        int port = freePort();
        PythonChatClient client = new PythonChatClient(WebClient.builder(), properties(200, 200));

        ChatResponse response = client.chat("http://127.0.0.1:" + port, request(), false, false);

        assertEquals("Dịch vụ chatbot đang chưa sẵn sàng. Bạn thử gửi lại sau một chút nhé.", response.reply());
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

            assertEquals("Chatbot đang phản hồi lâu hơn bình thường. Bạn thử gửi lại sau một chút nhé.", response.reply());
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

            assertEquals("Dịch vụ chatbot vừa gặp lỗi nội bộ. Bạn thử gửi lại sau một chút nhé.", response.reply());
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

            assertEquals("Yêu cầu này chưa xử lý được với cấu hình chatbot hiện tại.", response.reply());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void sendsNormalizedModeAndRetrievalModeToPython() throws Exception {
        AtomicReference<String> requestBody = new AtomicReference<>("");
        HttpServer server = server(exchange -> {
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            writeJson(exchange, 200, """
                    {"reply":"ok","latency_ms":1,"model":"m","adapter":null,"trigger_purchase_request":true,"debug":{"mode":"general_compare"}}
                    """);
        });
        try {
            ChatbotInstance bot = new ChatbotInstance();
            bot.setBaseModel("base-model");
            bot.setAdapterPath("adapter-path");
            bot.setProvider("local");
            bot.setMode("general_consumer");

            PythonChatClient client = new PythonChatClient(WebClient.builder(), properties(2_000, 10_000));

            ChatResponse response = client.chat(
                    baseUrl(server),
                    "compare these sofas",
                    List.of("hello"),
                    bot,
                    "conv-1",
                    "web",
                    "tenant-1",
                    false,
                    false
            );

            assertEquals("general_compare", response.debug().get("mode"));
            assertTrue(requestBody.get().contains("\"mode\":\"general_compare\""));
            assertTrue(requestBody.get().contains("\"retrieval_mode\":\"keyword\""));
            assertTrue(requestBody.get().contains("\"sales_mode\":null"));
            assertTrue(requestBody.get().contains("\"tenant_id\":\"tenant-1\""));
        } finally {
            server.stop(0);
        }
    }

    @Test
    void sendsActiveSalesModeForTenantSalesChat() throws Exception {
        AtomicReference<String> requestBody = new AtomicReference<>("");
        HttpServer server = server(exchange -> {
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            writeJson(exchange, 200, """
                    {"reply":"ok","latency_ms":1,"model":"m","adapter":null,"trigger_purchase_request":false,"debug":{"mode":"tenant_sales","sales_mode":"active"}}
                    """);
        });
        try {
            ChatbotInstance bot = new ChatbotInstance();
            bot.setBaseModel("base-model");
            bot.setProvider("claude");
            bot.setMode("tenant_sales");

            PythonChatClient client = new PythonChatClient(WebClient.builder(), properties(2_000, 10_000));

            ChatResponse response = client.chat(
                    baseUrl(server),
                    "toi muon mua GHS-41380",
                    List.of(),
                    bot,
                    "conv-1",
                    "messenger",
                    "tenant-1",
                    false,
                    false
            );

            assertEquals("tenant_sales", response.debug().get("mode"));
            assertTrue(requestBody.get().contains("\"mode\":\"tenant_sales\""));
            assertTrue(requestBody.get().contains("\"sales_mode\":\"active\""));
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
                        "tenant_sales",  // mode
                        "keyword",
                        null,
                        null
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
