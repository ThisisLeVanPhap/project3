package com.app.modelserver;

import com.app.modelserver.dto.ChatResponse;

public final class PythonChatFallbacks {

    private static final String UNAVAILABLE_MESSAGE =
            "Sorry, the chatbot service is unavailable right now. Please try again in a moment.";
    private static final String TIMEOUT_MESSAGE =
            "Sorry, the chatbot is taking longer than expected. Please try again in a moment.";
    private static final String UPSTREAM_4XX_MESSAGE =
            "Sorry, this chatbot request could not be processed for the current tenant configuration.";
    private static final String UPSTREAM_5XX_MESSAGE =
            "Sorry, the chatbot service had an internal error. Please try again in a moment.";

    private PythonChatFallbacks() {
    }

    public static ChatResponse forFailure(String baseModel, String adapter, UpstreamFailureCategory category) {
        return new ChatResponse(messageFor(category), 0, defaultString(baseModel), defaultString(adapter), false, null, null);
    }

    private static String messageFor(UpstreamFailureCategory category) {
        return switch (category) {
            case UNAVAILABLE -> UNAVAILABLE_MESSAGE;
            case TIMEOUT -> TIMEOUT_MESSAGE;
            case UPSTREAM_4XX -> UPSTREAM_4XX_MESSAGE;
            case UPSTREAM_5XX -> UPSTREAM_5XX_MESSAGE;
        };
    }

    public static boolean isKnownFailureMessage(String message) {
        String value = defaultString(message);
        return UNAVAILABLE_MESSAGE.equals(value)
                || TIMEOUT_MESSAGE.equals(value)
                || UPSTREAM_4XX_MESSAGE.equals(value)
                || UPSTREAM_5XX_MESSAGE.equals(value);
    }

    private static String defaultString(String value) {
        return value == null ? "" : value;
    }
}
