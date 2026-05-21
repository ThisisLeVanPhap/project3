package com.app.modelserver;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "python.llm")
public class LlmProperties {
    private String baseUrl;
    private String pythonBin;
    private String modelServerDir;

    private String host = "127.0.0.1";
    private int portRangeStart = 8101;
    private int portRangeEnd = 8199;
    private String healthPath = "/healthz";
    private String uvicornModule = "app.server:app";
    private int connectTimeoutMs = 2_000;
    private int responseTimeoutMs = 120_000;
    private int startupTimeoutMs = 120_000;
}
