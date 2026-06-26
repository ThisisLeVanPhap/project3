package com.app;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.core.env.Environment;

@SpringBootApplication
@ConfigurationPropertiesScan(basePackages = "com.app")
public class ApiApplication {

    private static final Logger log = LoggerFactory.getLogger(ApiApplication.class);

    public static void main(String[] args) {
        SpringApplication app = new SpringApplication(ApiApplication.class);
        app.addListeners((org.springframework.boot.context.event.ApplicationReadyEvent event) -> {
            Environment env = event.getApplicationContext().getEnvironment();
            String secret = env.getProperty("INTERNAL_API_SECRET", "");
            if (secret.isBlank()) {
                log.warn("INTERNAL_API_SECRET is not configured; /api/internal/ endpoints are OPEN in dev mode. "
                        + "Set INTERNAL_API_SECRET in production.");
            } else {
                log.info("INTERNAL_API_SECRET is configured; /api/internal/ endpoints are protected.");
            }
        });
        app.run(args);
    }
}
