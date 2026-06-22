package com.app.crm;

import com.app.chat.Conversation;
import com.app.chat.ConversationRepository;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.purchases.PurchaseRequest;
import com.app.purchases.PurchaseRequestRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class CrmCustomerActivityServiceTest {

    private ConversationRepository conversationRepository;
    private LeadRepository leadRepository;
    private PurchaseRequestRepository purchaseRequestRepository;
    private CrmCustomerActivityService service;

    @BeforeEach
    void setUp() {
        conversationRepository = mock(ConversationRepository.class);
        leadRepository = mock(LeadRepository.class);
        purchaseRequestRepository = mock(PurchaseRequestRepository.class);
        service = new CrmCustomerActivityService(
                conversationRepository,
                leadRepository,
                purchaseRequestRepository
        );
    }

    @Test
    void activityReturnsConversationsLeadsAndPurchaseRequestsForUnifiedCustomer() {
        UUID tenantId = UUID.randomUUID();
        UUID unifiedCustomerId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();

        Conversation messengerConv = new Conversation();
        messengerConv.setId(UUID.randomUUID());
        messengerConv.setTenantId(tenantId);
        messengerConv.setChatbotId(chatbotId);
        messengerConv.setUserExternalId("messenger:page:p1:sender:s1");
        messengerConv.setUnifiedCustomerId(unifiedCustomerId);
        messengerConv.setStatus("ACTIVE");
        messengerConv.setCreatedAt(Instant.parse("2026-06-15T10:00:00Z"));

        Conversation telegramConv = new Conversation();
        telegramConv.setId(UUID.randomUUID());
        telegramConv.setTenantId(tenantId);
        telegramConv.setChatbotId(chatbotId);
        telegramConv.setUserExternalId("telegram:chat:42");
        telegramConv.setUnifiedCustomerId(unifiedCustomerId);
        telegramConv.setStatus("ACTIVE");
        telegramConv.setCreatedAt(Instant.parse("2026-06-15T11:00:00Z"));

        when(conversationRepository.findByTenantIdAndUnifiedCustomerId(tenantId, unifiedCustomerId))
                .thenReturn(List.of(messengerConv, telegramConv));

        Lead messengerLead = Lead.createNew(
                tenantId.toString(),
                "messenger",
                messengerConv.getId().toString(),
                "s1",
                "{}",
                ""
        );
        setField(messengerLead, "id", 1L);
        setField(messengerLead, "createdAt", Instant.parse("2026-06-15T10:05:00Z"));

        when(leadRepository.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(
                tenantId.toString(), messengerConv.getId().toString()))
                .thenReturn(Optional.of(messengerLead));
        when(leadRepository.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(
                tenantId.toString(), telegramConv.getId().toString()))
                .thenReturn(Optional.empty());

        PurchaseRequest purchaseRequest = new PurchaseRequest();
        purchaseRequest.setTenantId(tenantId.toString());
        purchaseRequest.setChannel("messenger");
        purchaseRequest.setConversationId(messengerConv.getId().toString());
        purchaseRequest.setLeadId(1L);
        purchaseRequest.setCustomerName("Nguyễn Văn A");
        purchaseRequest.setPhone("0987654321");
        purchaseRequest.setEmail("customer@example.com");
        purchaseRequest.setShippingAddress("Hà Nội");
        purchaseRequest.setStatus("NEW");
        purchaseRequest.setRequestedProductRef("SOFA-001");
        setField(purchaseRequest, "id", 100L);
        setField(purchaseRequest, "createdAt", Instant.parse("2026-06-15T10:10:00Z"));
        setField(purchaseRequest, "updatedAt", Instant.parse("2026-06-15T10:10:00Z"));

        when(purchaseRequestRepository.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(
                tenantId.toString(), messengerConv.getId().toString()))
                .thenReturn(Optional.of(purchaseRequest));
        when(purchaseRequestRepository.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(
                tenantId.toString(), telegramConv.getId().toString()))
                .thenReturn(Optional.empty());

        CrmCustomerActivityService.CrmCustomerActivityResponse response =
                service.getActivity(tenantId, unifiedCustomerId);

        assertEquals(unifiedCustomerId, response.unifiedCustomerId());
        assertEquals(tenantId, response.tenantId());
        assertEquals(2, response.conversations().size());
        assertEquals(1, response.leads().size());
        assertEquals(1, response.purchaseRequests().size());

        assertTrue(response.conversations().stream()
                .anyMatch(c -> "messenger:page:p1:sender:s1".equals(c.userExternalId())));
        assertTrue(response.conversations().stream()
                .anyMatch(c -> "telegram:chat:42".equals(c.userExternalId())));

        CrmCustomerActivityService.CrmLeadView leadView = response.leads().get(0);
        assertEquals("messenger", leadView.channel());
        assertEquals("HANDOFF", leadView.stage());

        CrmCustomerActivityService.CrmPurchaseRequestView prView = response.purchaseRequests().get(0);
        assertEquals("0987654321", prView.phone());
        assertEquals("customer@example.com", prView.email());
    }

    @Test
    void activityReturnsEmptyListsWhenNoConversations() {
        UUID tenantId = UUID.randomUUID();
        UUID unifiedCustomerId = UUID.randomUUID();

        when(conversationRepository.findByTenantIdAndUnifiedCustomerId(tenantId, unifiedCustomerId))
                .thenReturn(List.of());

        CrmCustomerActivityService.CrmCustomerActivityResponse response =
                service.getActivity(tenantId, unifiedCustomerId);

        assertEquals(0, response.conversations().size());
        assertEquals(0, response.leads().size());
        assertEquals(0, response.purchaseRequests().size());
    }

    @Test
    void activityIsTenantIsolated() {
        UUID tenantA = UUID.randomUUID();
        UUID tenantB = UUID.randomUUID();
        UUID unifiedCustomerId = UUID.randomUUID();

        Conversation tenantAConv = new Conversation();
        tenantAConv.setId(UUID.randomUUID());
        tenantAConv.setTenantId(tenantA);
        tenantAConv.setUnifiedCustomerId(unifiedCustomerId);
        tenantAConv.setStatus("ACTIVE");
        tenantAConv.setCreatedAt(Instant.now());

        when(conversationRepository.findByTenantIdAndUnifiedCustomerId(tenantA, unifiedCustomerId))
                .thenReturn(List.of(tenantAConv));
        when(conversationRepository.findByTenantIdAndUnifiedCustomerId(tenantB, unifiedCustomerId))
                .thenReturn(List.of());

        CrmCustomerActivityService.CrmCustomerActivityResponse responseA =
                service.getActivity(tenantA, unifiedCustomerId);
        CrmCustomerActivityService.CrmCustomerActivityResponse responseB =
                service.getActivity(tenantB, unifiedCustomerId);

        assertEquals(1, responseA.conversations().size());
        assertEquals(0, responseB.conversations().size());
    }

    private static void setField(Object target, String fieldName, Object value) {
        try {
            java.lang.reflect.Field field = target.getClass().getDeclaredField(fieldName);
            field.setAccessible(true);
            field.set(target, value);
        } catch (ReflectiveOperationException e) {
            throw new RuntimeException(e);
        }
    }
}
