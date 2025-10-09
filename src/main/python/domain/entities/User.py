from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional


class User:
    """Pure domain entity for User without ORM dependencies"""
    
    def __init__(self, 
                 username: str,
                 email: str,
                 password_hash: str = None,
                 user_id: Optional[int] = None,
                 documents_generated: int = 0,
                 chat_messages_sent: int = 0,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self.id = user_id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.documents_generated = documents_generated
        self.chat_messages_sent = chat_messages_sent
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def set_password(self, password: str) -> None:
        """Define a senha do usuário com hash"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica se a senha está correta"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def can_generate_document(self) -> bool:
        """Verifica se o usuário pode gerar mais documentos (limite demo: 5)"""
        return self.documents_generated < 5

    def can_send_chat_message(self) -> bool:
        """Verifica se o usuário pode enviar mais mensagens no chat (limite demo: 5)"""
        return self.chat_messages_sent < 5

    def increment_documents_generated(self) -> None:
        """Incrementa o contador de documentos gerados"""
        self.documents_generated += 1
        self.updated_at = datetime.utcnow()

    def increment_chat_messages_sent(self) -> None:
        """Incrementa o contador de mensagens de chat enviadas"""
        self.chat_messages_sent += 1
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Converte a entidade para dicionário"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'documents_generated': self.documents_generated,
            'chat_messages_sent': self.chat_messages_sent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self) -> str:
        return f'<User {self.username}>'