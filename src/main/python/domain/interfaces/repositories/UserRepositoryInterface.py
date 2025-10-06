from abc import ABC, abstractmethod
from typing import Optional, List
from domain.entities.User import User


class UserRepositoryInterface(ABC):
    """Interface for User repository operations"""
    
    @abstractmethod
    def create(self, user: User) -> User:
        """
        Create a new user
        
        Args:
            user: User entity to create
            
        Returns:
            Created user with assigned ID
        """
        pass
    
    @abstractmethod
    def find_by_id(self, user_id: int) -> Optional[User]:
        """
        Find user by ID
        
        Args:
            user_id: User ID to search for
            
        Returns:
            User entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_username(self, username: str) -> Optional[User]:
        """
        Find user by username
        
        Args:
            username: Username to search for
            
        Returns:
            User entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_email(self, email: str) -> Optional[User]:
        """
        Find user by email
        
        Args:
            email: Email to search for
            
        Returns:
            User entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_all(self) -> List[User]:
        """
        Get all users
        
        Returns:
            List of all user entities
        """
        pass
    
    @abstractmethod
    def update(self, user: User) -> User:
        """
        Update existing user
        
        Args:
            user: User entity with updated data
            
        Returns:
            Updated user entity
        """
        pass
    
    @abstractmethod
    def delete(self, user_id: int) -> bool:
        """
        Delete user by ID
        
        Args:
            user_id: ID of user to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def exists_by_username(self, username: str) -> bool:
        """
        Check if username already exists
        
        Args:
            username: Username to check
            
        Returns:
            True if username exists, False otherwise
        """
        pass
    
    @abstractmethod
    def exists_by_email(self, email: str) -> bool:
        """
        Check if email already exists
        
        Args:
            email: Email to check
            
        Returns:
            True if email exists, False otherwise
        """
        pass