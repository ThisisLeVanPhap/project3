package com.app.modelserver;

import com.app.modelserver.dto.ChatResponse;

public final class PythonChatFallbacks {

    private static final String UNAVAILABLE_MESSAGE =
            "Dịch vụ chatbot đang chưa sẵn sàng. Bạn thử gửi lại sau một chút nhé.";
    private static final String TIMEOUT_MESSAGE =
            "Chatbot đang phản hồi lâu hơn bình thường. Bạn thử gửi lại sau một chút nhé.";
    private static final String UPSTREAM_4XX_MESSAGE =
            "Yêu cầu này chưa xử lý được với cấu hình chatbot hiện tại.";
    private static final String UPSTREAM_5XX_MESSAGE =
            "Dịch vụ chatbot vừa gặp lỗi nội bộ. Bạn thử gửi lại sau một chút nhé.";

    private PythonChatFallbacks() {
    }

    public static ChatResponse forFailure(String baseModel, String adapter, UpstreamFailureCategory category) {
        return new ChatResponse(messageFor(category), 0, defaultString(baseModel), defaultString(adapter), false, null, null, null);
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
