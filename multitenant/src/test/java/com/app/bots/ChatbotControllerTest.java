package com.app.bots;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
import com.app.tenant.TenantContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.doThrow;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class ChatbotControllerTest {

    @Mock
    private ChatbotInstanceRepository repo;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void createsChatbotWithResponseStyle() throws Exception {
        TenantContext.set(UUID.randomUUID().toString());
        when(repo.save(any(ChatbotInstance.class))).thenAnswer(invocation -> invocation.getArgument(0));

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new ChatbotController(repo, new ObjectMapper(), principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/chatbots")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Sales Bot",
                                  "channel": "messenger",
                                  "personaJson": "{\\\"tone\\\":\\\"helpful\\\"}",
                                  "responseStyle": "balanced"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.responseStyle").value("balanced"))
                .andExpect(jsonPath("$.name").value("Sales Bot"))
                .andExpect(jsonPath("$.channel").value("messenger"));

        ArgumentCaptor<ChatbotInstance> captor = ArgumentCaptor.forClass(ChatbotInstance.class);
        verify(repo).save(captor.capture());
        assertEquals("balanced", captor.getValue().getResponseStyle());
        assertEquals("ACTIVE", captor.getValue().getStatus());
        assertEquals("helpful", captor.getValue().getPersona().get("tone").asText());
    }

    @Test
    void updatesChatbotResponseStyleForCurrentTenant() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        TenantContext.set(tenantId.toString());

        ChatbotInstance chatbot = new ChatbotInstance();
        chatbot.setId(chatbotId);
        chatbot.setTenantId(tenantId);
        chatbot.setName("Sales Bot");
        chatbot.setChannel("telegram");
        chatbot.setResponseStyle("natural");

        when(repo.findById(chatbotId)).thenReturn(Optional.of(chatbot));
        when(repo.save(any(ChatbotInstance.class))).thenAnswer(invocation -> invocation.getArgument(0));

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new ChatbotController(repo, new ObjectMapper(), principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(put("/api/chatbots/{id}", chatbotId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Sales Bot",
                                  "channel": "telegram",
                                  "personaJson": "{}",
                                  "responseStyle": "fast"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.responseStyle").value("fast"));

        ArgumentCaptor<ChatbotInstance> captor = ArgumentCaptor.forClass(ChatbotInstance.class);
        verify(repo).save(captor.capture());
        assertEquals("fast", captor.getValue().getResponseStyle());
        assertTrue(captor.getValue().getPersona().isObject());
    }

    @Test
    void rejectsUnsupportedResponseStyle() throws Exception {
        TenantContext.set(UUID.randomUUID().toString());

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new ChatbotController(repo, new ObjectMapper(), principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/chatbots")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Sales Bot",
                                  "channel": "messenger",
                                  "personaJson": "{}",
                                  "responseStyle": "turbo"
                                }
                                """))
                .andExpect(status().isBadRequest());
    }

    @Test
    void deniesTenantMemberOnTenantConfigEndpoint() throws Exception {
        TenantContext.set(UUID.randomUUID().toString());
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireTenantAdmin();

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new ChatbotController(repo, new ObjectMapper(), principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/chatbots")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Sales Bot",
                                  "channel": "messenger",
                                  "personaJson": "{}",
                                  "responseStyle": "balanced"
                                }
                                """))
                .andExpect(status().isForbidden());
    }

    @Test
    void allowsTenantAdminOnTenantConfigEndpoint() throws Exception {
        UUID tenantId = UUID.randomUUID();
        TenantContext.set(tenantId.toString());
        when(repo.save(any(ChatbotInstance.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(principalAccessor.requireTenantAdmin()).thenReturn(
                new AppPrincipal("user-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "admin@tenant.local")
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new ChatbotController(repo, new ObjectMapper(), principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/chatbots")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Sales Bot",
                                  "channel": "messenger",
                                  "personaJson": "{}",
                                  "responseStyle": "balanced"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.responseStyle").value("balanced"));
    }
}
