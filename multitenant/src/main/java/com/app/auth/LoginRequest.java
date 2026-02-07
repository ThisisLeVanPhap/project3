package com.app.auth;

public record LoginRequest(
        String name,
        String code
) {}
