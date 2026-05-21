package com.app.modelserver;

import com.app.modelserver.dto.ChatResponse;

import java.util.Locale;
import java.util.Map;
import java.util.Set;

public final class ChatbotMode {
    public static final String TENANT_SALES = "tenant_sales";
    public static final String GENERAL_COMPARE = "general_compare";
    public static final String MARKET_PRICE = "market_price";
    public static final String DEFAULT_RETRIEVAL_MODE = "keyword";

    private static final Set<String> ALLOWED = Set.of(TENANT_SALES, GENERAL_COMPARE, MARKET_PRICE);

    private ChatbotMode() {
    }

    public static String normalize(String mode) {
        String raw = mode == null ? "" : mode.trim().toLowerCase(Locale.ROOT);
        if (raw.isBlank()) {
            return TENANT_SALES;
        }
        return switch (raw) {
            case "sales", "tenant", "shop" -> TENANT_SALES;
            case "general", "general_consumer", "compare", "comparison" -> GENERAL_COMPARE;
            case "market", "price", "market_reference" -> MARKET_PRICE;
            default -> ALLOWED.contains(raw) ? raw : TENANT_SALES;
        };
    }

    public static boolean isTenantSales(String mode) {
        return TENANT_SALES.equals(normalize(mode));
    }

    public static String finalMode(ChatResponse response, String requestedMode) {
        if (response == null || response.debug() == null) {
            return normalize(requestedMode);
        }
        Object debugMode = response.debug().get("mode");
        return debugMode == null ? normalize(requestedMode) : normalize(String.valueOf(debugMode));
    }

    public static boolean allowsPurchaseRequest(String requestedMode, ChatResponse response) {
        return Boolean.TRUE.equals(response != null ? response.trigger_purchase_request() : null)
                && isTenantSales(requestedMode)
                && TENANT_SALES.equals(finalMode(response, requestedMode));
    }

    public static String debugMode(Map<String, Object> debug) {
        Object mode = debug == null ? null : debug.get("mode");
        return mode == null ? "" : String.valueOf(mode);
    }
}
