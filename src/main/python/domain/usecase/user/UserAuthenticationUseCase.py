from typing import Optional
from domain.interfaces.repositories.UserRepositoryInterface import UserRepositoryInterface
from domain.entities.User import User


class UserAuthenticationUseCase:
    """Use case for user authentication operations"""
    
    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password
        
        Args:
            username: Username to authenticate
            password: Password to verify
            
        Returns:
            User entity if authentication successful, None otherwise
        """
        user = self.user_repository.find_by_username(username)
        
        if user and user.check_password(password):
            return user
        
        return None
    
    def create_user(self, username: str, email: str, password: str) -> User:
        """
        Create a new user
        
        Args:
            username: Username for the new user
            email: Email for the new user
            password: Password for the new user
            
        Returns:
            Created user entity
            
        Raises:
            ValueError: If username or email already exists
        """
        # Check if username already exists
        if self.user_repository.exists_by_username(username):
            raise ValueError(f"Username '{username}' already exists")
        
        # Check if email already exists
        if self.user_repository.exists_by_email(email):
            raise ValueError(f"Email '{email}' already exists")
        
        # Create new user entity
        user = User(username=username, email=email)
        user.set_password(password)
        
        # Save to repository
        return self.user_repository.create(user)
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID
        
        Args:
            user_id: User ID to search for
            
        Returns:
            User entity if found, None otherwise
        """
        return self.user_repository.find_by_id(user_id)
    
    def update_user_counters(self, user_id: int, increment_documents: bool = False, increment_messages: bool = False) -> Optional[User]:
        """
        Update user counters for demo limits
        
        Args:
            user_id: User ID to update
            increment_documents: Whether to increment documents counter
            increment_messages: Whether to increment messages counter
            
        Returns:
            Updated user entity if found, None otherwise
        """
        user = self.user_repository.find_by_id(user_id)
        
        if user:
            if increment_documents:
                user.increment_documents_generated()
            
            if increment_messages:
                user.increment_chat_messages_sent()
            
            return self.user_repository.update(user)
        
        return None
    
    def can_user_generate_document(self, user_id: int) -> bool:
        """
        Check if user can generate more documents
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if user can generate documents, False otherwise
        """
        user = self.user_repository.find_by_id(user_id)
        return user.can_generate_document() if user else False
    
    def can_user_send_chat_message(self, user_id: int) -> bool:
        """
        Check if user can send more chat messages
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if user can send messages, False otherwise
        """
        user = self.user_repository.find_by_id(user_id)
        return user.can_send_chat_message() if user else False