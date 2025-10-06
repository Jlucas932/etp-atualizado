from datetime import datetime
from typing import Optional, Dict, List


class ChatSession:
    """Pure domain entity for ChatSession without ORM dependencies"""
    
    def __init__(self,
                 session_id: str,
                 messages: Optional[List[Dict]] = None,
                 context: Optional[str] = None,
                 status: str = 'active',
                 chat_id: Optional[int] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self.id = chat_id
        self.session_id = session_id
        self.messages = messages or []
        self.context = context
        self.status = status  # active, completed
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def get_messages(self) -> List[Dict]:
        """Retorna as mensagens como lista"""
        return self.messages or []
    
    def set_messages(self, messages_list: List[Dict]) -> None:
        """Define as mensagens a partir de uma lista"""
        self.messages = messages_list
        self.updated_at = datetime.utcnow()

    def add_message(self, role: str, content: str) -> None:
        """Adiciona uma mensagem à conversa"""
        if not self.messages:
            self.messages = []
        
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        }
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def add_user_message(self, content: str) -> None:
        """Adiciona uma mensagem do usuário"""
        self.add_message('user', content)

    def add_assistant_message(self, content: str) -> None:
        """Adiciona uma mensagem do assistente"""
        self.add_message('assistant', content)

    def add_system_message(self, content: str) -> None:
        """Adiciona uma mensagem do sistema"""
        self.add_message('system', content)

    def get_last_message(self) -> Optional[Dict]:
        """Retorna a última mensagem da conversa"""
        if self.messages:
            return self.messages[-1]
        return None

    def get_messages_by_role(self, role: str) -> List[Dict]:
        """Retorna mensagens filtradas por role"""
        return [msg for msg in self.messages if msg.get('role') == role]

    def get_user_messages(self) -> List[Dict]:
        """Retorna apenas mensagens do usuário"""
        return self.get_messages_by_role('user')

    def get_assistant_messages(self) -> List[Dict]:
        """Retorna apenas mensagens do assistente"""
        return self.get_messages_by_role('assistant')

    def set_context(self, context: str) -> None:
        """Define o contexto da conversa"""
        self.context = context
        self.updated_at = datetime.utcnow()

    def append_context(self, additional_context: str) -> None:
        """Adiciona contexto adicional"""
        if self.context:
            self.context += f"\n{additional_context}"
        else:
            self.context = additional_context
        self.updated_at = datetime.utcnow()

    def complete_session(self) -> None:
        """Marca a sessão como completa"""
        self.status = 'completed'
        self.updated_at = datetime.utcnow()

    def is_active(self) -> bool:
        """Verifica se a sessão está ativa"""
        return self.status == 'active'

    def is_completed(self) -> bool:
        """Verifica se a sessão foi completada"""
        return self.status == 'completed'

    def has_messages(self) -> bool:
        """Verifica se possui mensagens"""
        return bool(self.messages)

    def message_count(self) -> int:
        """Retorna o número total de mensagens"""
        return len(self.messages) if self.messages else 0

    def to_dict(self) -> Dict:
        """Converte a entidade para dicionário"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'messages': self.get_messages(),
            'context': self.context,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self) -> str:
        return f'<ChatSession {self.session_id} ({self.message_count()} messages)>'