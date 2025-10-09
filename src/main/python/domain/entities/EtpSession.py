from datetime import datetime
from typing import Optional, Dict, List
import json


class EtpSession:
    """Pure domain entity for EtpSession without ORM dependencies"""
    
    def __init__(self,
                 session_id: str,
                 user_id: Optional[int] = None,
                 status: str = 'active',
                 answers: Optional[Dict] = None,
                 answers_validated: bool = False,
                 generated_etp: Optional[str] = None,
                 preview_content: Optional[str] = None,
                 preview_approved: bool = False,
                 session_entity_id: Optional[int] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self.id = session_entity_id
        self.session_id = session_id
        self.user_id = user_id
        self.status = status  # active, completed, error
        self.answers = answers or {}
        self.answers_validated = answers_validated
        self.generated_etp = generated_etp
        self.preview_content = preview_content
        self.preview_approved = preview_approved
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def get_answers(self) -> Dict:
        """Retorna as respostas como dicionário"""
        return self.answers or {}
    
    def set_answers(self, answers_dict: Dict) -> None:
        """Define as respostas a partir de um dicionário"""
        self.answers = answers_dict
        self.updated_at = datetime.utcnow()

    def validate_answers(self) -> None:
        """Marca as respostas como validadas"""
        self.answers_validated = True
        self.updated_at = datetime.utcnow()

    def set_generated_etp(self, etp_content: str) -> None:
        """Define o conteúdo do ETP gerado"""
        self.generated_etp = etp_content
        self.updated_at = datetime.utcnow()

    def set_preview_content(self, preview: str) -> None:
        """Define o conteúdo do preview"""
        self.preview_content = preview
        self.updated_at = datetime.utcnow()

    def approve_preview(self) -> None:
        """Aprova o preview do ETP"""
        self.preview_approved = True
        self.updated_at = datetime.utcnow()

    def complete_session(self) -> None:
        """Marca a sessão como completada"""
        self.status = 'completed'
        self.updated_at = datetime.utcnow()

    def mark_error(self) -> None:
        """Marca a sessão com erro"""
        self.status = 'error'
        self.updated_at = datetime.utcnow()

    def has_generated_etp(self) -> bool:
        """Verifica se o ETP foi gerado"""
        return bool(self.generated_etp)

    def to_dict(self) -> Dict:
        """Converte a entidade para dicionário"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'status': self.status,
            'answers': self.get_answers(),
            'answers_validated': self.answers_validated,
            'has_generated_etp': self.has_generated_etp(),
            'preview_approved': self.preview_approved,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self) -> str:
        return f'<EtpSession {self.session_id}>'