"""Repositories for Conversation and Message CRUD operations."""
from typing import List, Optional
from sqlalchemy import desc
from domain.dto.ConversationModels import Conversation, Message
from domain.interfaces.dataprovider.DatabaseConfig import db


class ConversationRepo:
    """Repository for Conversation CRUD operations."""

    @staticmethod
    def create(user_id: str, title: str = "Novo Documento") -> Conversation:
        """Create a new conversation."""
        conv = Conversation(user_id=user_id, title=title)
        db.session.add(conv)
        db.session.flush()
        return conv

    @staticmethod
    def get(conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID."""
        return db.session.get(Conversation, conversation_id)

    @staticmethod
    def rename(conversation_id: str, title: str) -> Optional[Conversation]:
        """Rename a conversation."""
        conv = db.session.get(Conversation, conversation_id)
        if not conv:
            return None
        conv.title = title
        db.session.flush()
        return conv

    @staticmethod
    def list_by_user(user_id: str, limit: int = 100) -> List[Conversation]:
        """List conversations for a user, ordered by updated_at DESC."""
        return (
            db.session.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .all()
        )

    @staticmethod
    def delete(conversation_id: str) -> bool:
        """Delete a conversation."""
        conv = db.session.get(Conversation, conversation_id)
        if not conv:
            return False
        db.session.delete(conv)
        db.session.flush()
        return True

    @staticmethod
    def assert_owner(conversation_id: str, user_id: str) -> bool:
        """
        Check if the given user_id owns the conversation.
        Returns True if user is owner, False otherwise.
        Used for LGPD compliance - users can only access their own conversations.
        """
        conv = db.session.get(Conversation, conversation_id)
        if not conv or str(conv.user_id) != str(user_id):
            return False
        return True


class MessageRepo:
    """Repository for Message CRUD operations."""

    @staticmethod
    def add(
        conversation_id: str,
        role: str,
        content: str,
        stage: Optional[str] = None,
        payload: Optional[dict] = None
    ) -> Message:
        """Add a new message to a conversation."""
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            stage=stage,
            payload=payload
        )
        db.session.add(msg)
        db.session.flush()
        
        # Update conversation's updated_at timestamp
        conv = db.session.get(Conversation, conversation_id)
        if conv:
            from datetime import datetime
            conv.updated_at = datetime.utcnow()
            db.session.flush()
        
        return msg

    @staticmethod
    def create(*args, **kwargs) -> Message:
        """Alias for add() to maintain backward compatibility."""
        return MessageRepo.add(*args, **kwargs)

    @staticmethod
    def list_for_conversation(
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        """List all messages for a conversation, ordered by created_at."""
        query = (
            db.session.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def get_by_conversation(conversation_id: str, limit: Optional[int] = None) -> List[Message]:
        """Alias for list_for_conversation() to maintain backward compatibility."""
        return MessageRepo.list_for_conversation(conversation_id, limit)

    @staticmethod
    def get_last_message(conversation_id: str) -> Optional[Message]:
        """Get the last message from a conversation."""
        return (
            db.session.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .first()
        )
