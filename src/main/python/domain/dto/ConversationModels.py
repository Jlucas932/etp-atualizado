"""ORM models for conversation persistence (ETP Dynamic Chat)."""
import uuid
from datetime import datetime
from domain.interfaces.dataprovider.DatabaseConfig import db


class Conversation(db.Model):
    """SQLAlchemy ORM model for etp_conversations table."""
    
    __tablename__ = "etp_conversations"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(64), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, default="Novo Documento")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship to messages
    messages = db.relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="Message.created_at"
    )

    def __repr__(self):
        return f"<Conversation {self.id} title='{self.title}'>"


class Message(db.Model):
    """SQLAlchemy ORM model for etp_messages table."""
    
    __tablename__ = "etp_messages"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = db.Column(
        db.String(36),
        db.ForeignKey("etp_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role = db.Column(db.String(20), nullable=False)  # user|assistant|system
    content = db.Column(db.Text, nullable=False)
    stage = db.Column(db.String(64), nullable=True)
    payload = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to conversation
    conversation = db.relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.id} role={self.role}>"
