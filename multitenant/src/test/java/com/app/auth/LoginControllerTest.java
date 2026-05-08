package com.app.auth;

import jakarta.servlet.http.HttpSession;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class LoginControllerTest {

    @Mock
    private TenantMemberRepository tenantMemberRepository;

    private final PasswordEncoder passwordEncoder = PasswordEncoderFactories.createDelegatingPasswordEncoder();

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void logsInTenantAdminFromRealMemberAccount() throws Exception {
        TenantMember admin = tenantMember(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "admin@tenant.local",
                "Admin User",
                "TENANT_ADMIN",
                "{noop}admin123",
                "ACTIVE"
        );
        when(tenantMemberRepository.findAllByEmailIgnoreCase("admin@tenant.local")).thenReturn(List.of(admin));

        MockMvc mvc = mvc();

        mvc.perform(post("/api/login/tenant")
                        .contentType("application/json")
                        .content("""
                                {"name":"admin@tenant.local","code":"admin123"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.role").value("TENANT_ADMIN"))
                .andExpect(jsonPath("$.tenantId").value(admin.getTenantId().toString()))
                .andExpect(jsonPath("$.email").value("admin@tenant.local"))
                .andExpect(jsonPath("$.displayName").value("Admin User"));
    }

    @Test
    void logsInTenantMemberFromRealMemberAccountAndExposesMe() throws Exception {
        TenantMember member = tenantMember(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "member@tenant.local",
                "Member User",
                "TENANT_MEMBER",
                "{noop}member123",
                "ACTIVE"
        );
        when(tenantMemberRepository.findAllByEmailIgnoreCase("member@tenant.local")).thenReturn(List.of(member));

        MockMvc mvc = mvc();

        MvcResult login = mvc.perform(post("/api/login/tenant")
                        .contentType("application/json")
                        .content("""
                                {"name":"member@tenant.local","code":"member123"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.role").value("TENANT_MEMBER"))
                .andReturn();

        HttpSession session = login.getRequest().getSession(false);

        mvc.perform(get("/api/me").session((MockHttpSession) session))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userId").value(member.getId().toString()))
                .andExpect(jsonPath("$.role").value("TENANT_MEMBER"))
                .andExpect(jsonPath("$.tenantId").value(member.getTenantId().toString()))
                .andExpect(jsonPath("$.displayName").value("Member User"))
                .andExpect(jsonPath("$.email").value("member@tenant.local"));
    }

    @Test
    void rejectsInvalidTenantMemberCredentials() throws Exception {
        TenantMember member = tenantMember(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "member@tenant.local",
                "Member User",
                "TENANT_MEMBER",
                "{noop}member123",
                "ACTIVE"
        );
        when(tenantMemberRepository.findAllByEmailIgnoreCase("member@tenant.local")).thenReturn(List.of(member));

        MockMvc mvc = mvc();

        mvc.perform(post("/api/login/tenant")
                        .contentType("application/json")
                        .content("""
                                {"name":"member@tenant.local","code":"wrongpass"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.message").value("Invalid tenant member credentials"))
                .andExpect(jsonPath("$.tenantId").value(nullValue()));
    }

    @Test
    void rejectsAmbiguousTenantMemberCredentialsForDuplicateEmail() throws Exception {
        String encoded = passwordEncoder.encode("shared123");
        TenantMember first = tenantMember(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "shared@tenant.local",
                "First User",
                "TENANT_MEMBER",
                encoded,
                "ACTIVE"
        );
        TenantMember second = tenantMember(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "shared@tenant.local",
                "Second User",
                "TENANT_ADMIN",
                encoded,
                "ACTIVE"
        );
        when(tenantMemberRepository.findAllByEmailIgnoreCase("shared@tenant.local")).thenReturn(List.of(first, second));

        MockMvc mvc = mvc();

        mvc.perform(post("/api/login/tenant")
                        .contentType("application/json")
                        .content("""
                                {"name":"shared@tenant.local","code":"shared123"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.message").value("Ambiguous tenant member login"));
    }

    private MockMvc mvc() {
        return MockMvcBuilders
                .standaloneSetup(
                        new LoginController(tenantMemberRepository, passwordEncoder),
                        new MeController(new SessionPrincipalAccessor())
                )
                .addFilters(new SessionAuthenticationFilter())
                .build();
    }

    private static TenantMember tenantMember(
            UUID id,
            UUID tenantId,
            String email,
            String displayName,
            String role,
            String passwordHash,
            String status
    ) {
        TenantMember member = new TenantMember();
        member.setId(id);
        member.setTenantId(tenantId);
        member.setEmail(email);
        member.setDisplayName(displayName);
        member.setRole(role);
        member.setPasswordHash(passwordHash);
        member.setStatus(status);
        return member;
    }
}
