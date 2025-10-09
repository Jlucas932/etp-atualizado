from abc import ABC, abstractmethod
from typing import Optional, List
from domain.entities.ChatSession import ChatSession


class ChatRepositoryInterface(ABC):
    """Interface for ChatSession repository operations"""
    
    @abstractmethod
    def create(self, chat_session: ChatSession) -> ChatSession:
        """
        Create a new chat session
        
        Args:
            chat_session: ChatSession entity to create
            
        Returns:
            Created chat session with assigned ID
        """
        pass
    
    @abstractmethod
    def find_by_id(self, chat_id: int) -> Optional[ChatSession]:
        """
        Find chat session by ID
        
        Args:
            chat_id: Chat session ID to search for
            
        Returns:
            ChatSession entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_session_id(self, session_id: str) -> List[ChatSession]:
        """
        Find chat sessions by session ID
        
        Args:
            session_id: Session ID to search for
            
        Returns:
            List of ChatSession entities for the session
        """
        pass
    
    @abstractmethod
    def find_by_status(self, status: str) -> List[ChatSession]:
        """
        Find chat sessions by status
        
        Args:
            status: Status to search for (active, completed)
            
        Returns:
            List of ChatSession entities with the specified status
        """
        pass
    
    @abstractmethod
    def find_active_sessions(self) -> List[ChatSession]:
        """
        Find all active chat sessions
        
        Returns:
            List of active ChatSession entities
        """
        pass
    
    @abstractmethod
    def find_completed_sessions(self) -> List[ChatSession]:
        """
        Find all completed chat sessions
        
        Returns:
            List of completed ChatSession entities
        """
        pass
    
    @abstractmethod
    def find_all(self) -> List[ChatSession]:
        """
        Get all chat sessions
        
        Returns:
            List of all ChatSession entities
        """
        pass
    
    @abstractmethod
    def update(self, chat_session: ChatSession) -> ChatSession:
        """
        Update existing chat session
        
        Args:
            chat_session: ChatSession entity with updated data
            
        Returns:
            Updated ChatSession entity
        """
        pass
    
    @abstractmethod
    def delete(self, chat_id: int) -> bool:
        """
        Delete chat session by ID
        
        Args:
            chat_id: ID of chat session to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def delete_by_session_id(self, session_id: str) -> bool:
        """
        Delete all chat sessions for a specific session
        
        Args:
            session_id: Session ID to delete chat sessions for
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def count_messages_by_session(self, session_id: str) -> int:
        """
        Count total messages for a session
        
        Args:
            session_id: Session ID to count messages for
            
        Returns:
            Total number of messages across all chat sessions for the session
        """
        pass