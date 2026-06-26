package com.app.general;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for internal API security header checks.
 * These verify the logic used by GeneralProductSearchController
 * and MarketPriceInsightController.
 */
class InternalApiSecurityTest {

    private static final String HEADER = "X-Internal-Api-Key";
    private static final String SECRET = "my-secret-key";

    @Test
    void noHeaderWithSecretConfiguredIsRejected() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        assertFalse(isAuthorized(request, SECRET));
    }

    @Test
    void wrongHeaderWithSecretConfiguredIsRejected() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader(HEADER, "wrong-key");
        assertFalse(isAuthorized(request, SECRET));
    }

    @Test
    void correctHeaderWithSecretConfiguredIsAccepted() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader(HEADER, SECRET);
        assertTrue(isAuthorized(request, SECRET));
    }

    @Test
    void noSecretConfiguredAllowsAll() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        assertTrue(isAuthorized(request, ""));
        assertTrue(isAuthorized(request, null));
    }

    @Test
    void noSecretConfiguredAllowsEvenWithHeader() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader(HEADER, "any-key");
        assertTrue(isAuthorized(request, ""));
    }

    /**
     * Simulates the controller check logic.
     */
    private boolean isAuthorized(MockHttpServletRequest request, String secret) {
        if (secret != null && !secret.isBlank()) {
            String headerKey = request.getHeader(HEADER);
            return headerKey != null && headerKey.trim().equals(secret.trim());
        }
        return true;
    }
}
