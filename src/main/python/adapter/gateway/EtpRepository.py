from typing import Optional, List
from domain.interfaces.repositories.EtpRepositoryInterface import EtpRepositoryInterface
from domain.entities.EtpSession import EtpSession
from domain.dto.EtpDto import EtpSession as EtpSessionDto
from domain.interfaces.dataprovider.DatabaseConfig import db


class EtpRepository(EtpRepositoryInterface):
    """Concrete implementation of EtpRepository using SQLAlchemy"""
    
    def create(self, etp_session: EtpSession) -> EtpSession:
        """Create a new ETP session"""
        etp_dto = EtpSessionDto(
            session_id=etp_session.session_id,
            user_id=etp_session.user_id,
            status=etp_session.status,
            answers_validated=etp_session.answers_validated,
            generated_etp=etp_session.generated_etp,
            preview_content=etp_session.preview_content,
            preview_approved=etp_session.preview_approved
        )
        
        etp_dto.set_answers(etp_session.answers)
        
        db.session.add(etp_dto)
        db.session.commit()
        
        return self._dto_to_entity(etp_dto)
    
    def find_by_id(self, session_entity_id: int) -> Optional[EtpSession]:
        """Find ETP session by entity ID"""
        etp_dto = EtpSessionDto.query.get(session_entity_id)
        if etp_dto:
            return self._dto_to_entity(etp_dto)
        return None
    
    def find_by_session_id(self, session_id: str) -> Optional[EtpSession]:
        """Find ETP session by session ID"""
        etp_dto = EtpSessionDto.query.filter_by(session_id=session_id).first()
        if etp_dto:
            return self._dto_to_entity(etp_dto)
        return None
    
    def find_by_user_id(self, user_id: int) -> List[EtpSession]:
        """Find ETP sessions by user ID"""
        etp_dtos = EtpSessionDto.query.filter_by(user_id=user_id).all()
        return [self._dto_to_entity(etp_dto) for etp_dto in etp_dtos]
    
    def find_by_status(self, status: str) -> List[EtpSession]:
        """Find ETP sessions by status"""
        etp_dtos = EtpSessionDto.query.filter_by(status=status).all()
        return [self._dto_to_entity(etp_dto) for etp_dto in etp_dtos]
    
    def find_all(self) -> List[EtpSession]:
        """Get all ETP sessions"""
        etp_dtos = EtpSessionDto.query.all()
        return [self._dto_to_entity(etp_dto) for etp_dto in etp_dtos]
    
    def update(self, etp_session: EtpSession) -> EtpSession:
        """Update existing ETP session"""
        etp_dto = EtpSessionDto.query.get(etp_session.id)
        if not etp_dto:
            raise ValueError(f"ETP session with ID {etp_session.id} not found")
        
        etp_dto.session_id = etp_session.session_id
        etp_dto.user_id = etp_session.user_id
        etp_dto.status = etp_session.status
        etp_dto.answers_validated = etp_session.answers_validated
        etp_dto.generated_etp = etp_session.generated_etp
        etp_dto.preview_content = etp_session.preview_content
        etp_dto.preview_approved = etp_session.preview_approved
        etp_dto.updated_at = etp_session.updated_at
        
        etp_dto.set_answers(etp_session.answers)
        
        db.session.commit()
        
        return self._dto_to_entity(etp_dto)
    
    def delete(self, session_entity_id: int) -> bool:
        """Delete ETP session by entity ID"""
        etp_dto = EtpSessionDto.query.get(session_entity_id)
        if etp_dto:
            db.session.delete(etp_dto)
            db.session.commit()
            return True
        return False
    
    def delete_by_session_id(self, session_id: str) -> bool:
        """Delete ETP session by session ID"""
        etp_dto = EtpSessionDto.query.filter_by(session_id=session_id).first()
        if etp_dto:
            db.session.delete(etp_dto)
            db.session.commit()
            return True
        return False
    
    def exists_by_session_id(self, session_id: str) -> bool:
        """Check if session ID already exists"""
        return EtpSessionDto.query.filter_by(session_id=session_id).first() is not None
    
    def _dto_to_entity(self, etp_dto: EtpSessionDto) -> EtpSession:
        """Convert DTO to domain entity"""
        return EtpSession(
            session_id=etp_dto.session_id,
            user_id=etp_dto.user_id,
            status=etp_dto.status,
            answers=etp_dto.get_answers(),
            answers_validated=etp_dto.answers_validated,
            generated_etp=etp_dto.generated_etp,
            preview_content=etp_dto.preview_content,
            preview_approved=etp_dto.preview_approved,
            session_entity_id=etp_dto.id,
            created_at=etp_dto.created_at,
            updated_at=etp_dto.updated_at
        )