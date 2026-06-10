package com.app.messenger;

import lombok.Getter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Getter
@Component
@ConfigurationProperties("messenger")
public class MessengerProperties {

    private String verifyToken;
    private boolean demoMode = false;

    public void setVerifyToken(String verifyToken) {
        this.verifyToken = verifyToken;
    }

    public void setDemoMode(boolean demoMode) {
        this.demoMode = demoMode;
    }
}
