from abc import ABC, abstractmethod
from typing import Optional, List
from domain.entities.EtpSession import EtpSession


class EtpRepositoryInterface(ABC):
    """Interface for ETP Session repository operations"""
    
    @abstractmethod
    def create(self, etp_session: EtpSession) -> EtpSession:
        """
        Create a new ETP session
        
        Args:
            etp_session: EtpSession entity to create
            
        Returns:
            Created ETP session with assigned ID
        """
        pass
    
    @abstractmethod
    def find_by_id(self, session_entity_id: int) -> Optional[EtpSession]:
        """
        Find ETP session by entity ID
        
        Args:
            session_entity_id: Entity ID to search for
            
        Returns:
            EtpSession entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_session_id(self, session_id: str) -> Optional[EtpSession]:
        """
        Find ETP session by session ID
        
        Args:
            session_id: Session ID to search for
            
        Returns:
            EtpSession entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_user_id(self, user_id: int) -> List[EtpSession]:
        """
        Find ETP sessions by user ID
        
        Args:
            user_id: User ID to search for
            
        Returns:
            List of EtpSession entities for the user
        """
        pass
    
    @abstractmethod
    def find_by_status(self, status: str) -> List[EtpSession]:
        """
        Find ETP sessions by status
        
        Args:
            status: Status to search for (active, completed, error)
            
        Returns:
            List of EtpSession entities with the specified status
        """
        pass
    
    @abstractmethod
    def find_all(self) -> List[EtpSession]:
        """
        Get all ETP sessions
        
        Returns:
            List of all EtpSession entities
        """
        pass
    
    @abstractmethod
    def update(self, etp_session: EtpSession) -> EtpSession:
        """
        Update existing ETP session
        
        Args:
            etp_session: EtpSession entity with updated data
            
        Returns:
            Updated EtpSession entity
        """
        pass
    
    @abstractmethod
    def delete(self, session_entity_id: int) -> bool:
        """
        Delete ETP session by entity ID
        
        Args:
            session_entity_id: Entity ID of session to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def delete_by_session_id(self, session_id: str) -> bool:
        """
        Delete ETP session by session ID
        
        Args:
            session_id: Session ID of session to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def exists_by_session_id(self, session_id: str) -> bool:
        """
        Check if session ID already exists
        
        Args:
            session_id: Session ID to check
            
        Returns:
            True if session ID exists, False otherwise
        """
        pass