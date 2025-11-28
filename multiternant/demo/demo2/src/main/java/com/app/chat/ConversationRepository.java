package com.app.chat;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.UUID;

public interface ConversationRepository extends JpaRepository<Conversation, UUID> {}
