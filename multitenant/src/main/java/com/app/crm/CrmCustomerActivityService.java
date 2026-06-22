package com.app.crm;

import com.app.chat.Conversation;
import com.app.chat.ConversationRepository;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.purchases.PurchaseRequest;
import com.app.purchases.PurchaseRequestRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class CrmCustomerActivityService {

    private final ConversationRepository conversationRepository;
    private final LeadRepository leadRepository;
    private final PurchaseRequestRepository purchaseRequestRepository;

    public CrmCustomerActivityService(
            ConversationRepository conversationRepository,
            LeadRepository leadRepository,
            PurchaseRequestRepository purchaseRequestRepository
    ) {
        this.conversationRepository = conversationRepository;
        this.leadRepository = leadRepository;
        this.purchaseRequestRepository = purchaseRequestRepository;
    }

    @Transactional(readOnly = true)
    public CrmCustomerActivityResponse getActivity(UUID tenantId, UUID unifiedCustomerId) {
        List<Conversation> conversations = conversationRepository
                .findByTenantIdAndUnifiedCustomerId(tenantId, unifiedCustomerId);

        List<CrmConversationView> conversationViews = conversations.stream()
                .map(conv -> new CrmConversationView(
                        conv.getId(),
                        conv.getTenantId(),
                        conv.getChatbotId(),
                        conv.getUserExternalId(),
                        conv.getUnifiedCustomerId(),
                        conv.getStatus(),
                        conv.getTitle(),
                        conv.getCreatedAt()
                ))
                .collect(Collectors.toList());

        List<CrmLeadView> leadViews = conversations.stream()
                .flatMap(conv -> {
                    List<Lead> leads = leadRepository.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(
                            tenantId.toString(),
                            conv.getId().toString()
                    ).stream().toList();
                    return leads.stream();
                })
                .map(lead -> new CrmLeadView(
                        lead.getId(),
                        lead.getTenantId(),
                        lead.getChannel(),
                        lead.getConversationId(),
                        lead.getCustomerHandle(),
                        lead.getStatus(),
                        lead.getStage(),
                        lead.getShippingStatus(),
                        lead.getCreatedAt()
                ))
                .collect(Collectors.toList());

        List<CrmPurchaseRequestView> purchaseRequestViews = conversations.stream()
                .flatMap(conv -> {
                    List<PurchaseRequest> requests = purchaseRequestRepository
                            .findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(
                                    tenantId.toString(),
                                    conv.getId().toString()
                            ).stream().toList();
                    return requests.stream();
                })
                .map(pr -> new CrmPurchaseRequestView(
                        pr.getId(),
                        pr.getTenantId(),
                        pr.getChannel(),
                        pr.getConversationId(),
                        pr.getLeadId(),
                        pr.getCustomerName(),
                        pr.getPhone(),
                        pr.getEmail(),
                        pr.getShippingAddress(),
                        pr.getStatus(),
                        pr.getRequestedProductRef(),
                        pr.getCreatedAt(),
                        pr.getUpdatedAt()
                ))
                .collect(Collectors.toList());

        return new CrmCustomerActivityResponse(
                unifiedCustomerId,
                tenantId,
                conversationViews,
                leadViews,
                purchaseRequestViews
        );
    }

    public record CrmConversationView(
            UUID conversationId,
            UUID tenantId,
            UUID chatbotId,
            String userExternalId,
            UUID unifiedCustomerId,
            String status,
            String title,
            Instant createdAt
    ) {
    }

    public record CrmLeadView(
            Long id,
            String tenantId,
            String channel,
            String conversationId,
            String customerHandle,
            String status,
            String stage,
            String shippingStatus,
            Instant createdAt
    ) {
    }

    public record CrmPurchaseRequestView(
            Long id,
            String tenantId,
            String channel,
            String conversationId,
            Long leadId,
            String customerName,
            String phone,
            String email,
            String shippingAddress,
            String status,
            String requestedProductRef,
            Instant createdAt,
            Instant updatedAt
    ) {
    }

    public record CrmCustomerActivityResponse(
            UUID unifiedCustomerId,
            UUID tenantId,
            List<CrmConversationView> conversations,
            List<CrmLeadView> leads,
            List<CrmPurchaseRequestView> purchaseRequests
    ) {
    }
}
