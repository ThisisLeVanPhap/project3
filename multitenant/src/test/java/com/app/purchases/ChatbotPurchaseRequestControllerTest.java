package com.app.purchases;

import com.app.common.ApiExceptionHandler;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.time.Instant;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ChatbotPurchaseRequestControllerTest {

    @Test
    void rejectsMissingServiceToken() throws Exception {
        PurchaseRequestService service = mock(PurchaseRequestService.class);
        MockMvc mvc = mvc(service);

        mvc.perform(post("/api/chatbot/purchase-requests")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validPayload()))
                .andExpect(status().isUnauthorized());

        verifyNoInteractions(service);
    }

    @Test
    void createsPurchaseRequestWithValidBearerToken() throws Exception {
        PurchaseRequestService service = mock(PurchaseRequestService.class);
        PurchaseRequest purchaseRequest = purchaseRequest(123L);
        when(service.createFromChatbotHandoff(any(ChatbotPurchaseRequestCreateRequest.class)))
                .thenReturn(new PurchaseRequestService.ChatbotCreateResult(purchaseRequest, true));
        MockMvc mvc = mvc(service);

        mvc.perform(post("/api/chatbot/purchase-requests")
                        .header("Authorization", "Bearer test-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validPayload()))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(123))
                .andExpect(jsonPath("$.handoff_id").value("handoff-1"))
                .andExpect(jsonPath("$.idempotency_key").value("idem-1"))
                .andExpect(jsonPath("$.status").value("NEW"))
                .andExpect(jsonPath("$.created").value(true))
                .andExpect(jsonPath("$.purchase_request.id").value(123))
                .andExpect(jsonPath("$.purchase_request.handoff_id").value("handoff-1"))
                .andExpect(jsonPath("$.purchase_request.product_sku").value("GHO-607"))
                .andExpect(jsonPath("$.purchase_request.email").value("a@example.com"));

        verify(service).createFromChatbotHandoff(any(ChatbotPurchaseRequestCreateRequest.class));
    }

    @Test
    void returnsOkForDuplicateIdempotency() throws Exception {
        PurchaseRequestService service = mock(PurchaseRequestService.class);
        PurchaseRequest purchaseRequest = purchaseRequest(123L);
        when(service.createFromChatbotHandoff(any(ChatbotPurchaseRequestCreateRequest.class)))
                .thenReturn(new PurchaseRequestService.ChatbotCreateResult(purchaseRequest, false));
        MockMvc mvc = mvc(service);

        mvc.perform(post("/api/chatbot/purchase-requests")
                        .header("X-Service-Token", "test-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validPayload()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.created").value(false))
                .andExpect(jsonPath("$.purchase_request.id").value(123));
    }

    private static MockMvc mvc(PurchaseRequestService service) {
        return MockMvcBuilders
                .standaloneSetup(new ChatbotPurchaseRequestController(service, "test-token"))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    private static String validPayload() {
        return """
                {
                  "handoff_id": "handoff-1",
                  "idempotency_key": "idem-1",
                  "tenant_id": "8e0f40c4-83de-4d44-bf0f-5e53769595e0",
                  "conversation_id": "conv-1",
                  "channel": "web",
                  "customer_name": "Nguyen Van A",
                  "phone": "0912345678",
                  "email": "a@example.com",
                  "shipping_address": "12 Nguyen Trai",
                  "notes": "Call before delivery",
                  "requested_product_ref": "Rem cuon tranh cao cap GHO-607",
                  "product_sku": "GHO-607",
                  "product_url": "https://store.example/products/gho-607",
                  "price": 700000,
                  "quantity": 1
                }
                """;
    }

    private static PurchaseRequest purchaseRequest(Long id) throws Exception {
        PurchaseRequest purchaseRequest = new PurchaseRequest();
        purchaseRequest.setTenantId("8e0f40c4-83de-4d44-bf0f-5e53769595e0");
        purchaseRequest.setChannel("web");
        purchaseRequest.setConversationId("conv-1");
        purchaseRequest.setHandoffId("handoff-1");
        purchaseRequest.setIdempotencyKey("idem-1");
        purchaseRequest.setCustomerName("Nguyen Van A");
        purchaseRequest.setPhone("0912345678");
        purchaseRequest.setEmail("a@example.com");
        purchaseRequest.setShippingAddress("12 Nguyen Trai");
        purchaseRequest.setNotes("Call before delivery");
        purchaseRequest.setRequestedProductRef("Rem cuon tranh cao cap GHO-607");
        purchaseRequest.setProductSku("GHO-607");
        purchaseRequest.setProductUrl("https://store.example/products/gho-607");
        purchaseRequest.setPrice(new BigDecimal("700000"));
        purchaseRequest.setQuantity(1);
        purchaseRequest.setStatus("NEW");

        setField(purchaseRequest, "id", id);
        setField(purchaseRequest, "createdAt", Instant.parse("2026-04-01T10:07:10Z"));
        return purchaseRequest;
    }

    private static void setField(PurchaseRequest purchaseRequest, String fieldName, Object value) throws Exception {
        Field field = PurchaseRequest.class.getDeclaredField(fieldName);
        field.setAccessible(true);
        field.set(purchaseRequest, value);
    }
}
