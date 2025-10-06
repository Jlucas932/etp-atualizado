from typing import Optional, List
from domain.interfaces.repositories.UserRepositoryInterface import UserRepositoryInterface
from domain.entities.User import User
from domain.dto.UserDto import User as UserDto
from domain.interfaces.dataprovider.DatabaseConfig import db


class UserRepository(UserRepositoryInterface):
    """Concrete implementation of UserRepository using SQLAlchemy"""
    
    def create(self, user: User) -> User:
        """Create a new user"""
        user_dto = UserDto(
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            documents_generated=user.documents_generated,
            chat_messages_sent=user.chat_messages_sent
        )
        
        db.session.add(user_dto)
        db.session.commit()
        
        return self._dto_to_entity(user_dto)
    
    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID"""
        user_dto = UserDto.query.get(user_id)
        if user_dto:
            return self._dto_to_entity(user_dto)
        return None
    
    def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username"""
        user_dto = UserDto.query.filter_by(username=username).first()
        if user_dto:
            return self._dto_to_entity(user_dto)
        return None
    
    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email"""
        user_dto = UserDto.query.filter_by(email=email).first()
        if user_dto:
            return self._dto_to_entity(user_dto)
        return None
    
    def find_all(self) -> List[User]:
        """Get all users"""
        user_dtos = UserDto.query.all()
        return [self._dto_to_entity(user_dto) for user_dto in user_dtos]
    
    def update(self, user: User) -> User:
        """Update existing user"""
        user_dto = UserDto.query.get(user.id)
        if not user_dto:
            raise ValueError(f"User with ID {user.id} not found")
        
        user_dto.username = user.username
        user_dto.email = user.email
        user_dto.password_hash = user.password_hash
        user_dto.documents_generated = user.documents_generated
        user_dto.chat_messages_sent = user.chat_messages_sent
        user_dto.updated_at = user.updated_at
        
        db.session.commit()
        
        return self._dto_to_entity(user_dto)
    
    def delete(self, user_id: int) -> bool:
        """Delete user by ID"""
        user_dto = UserDto.query.get(user_id)
        if user_dto:
            db.session.delete(user_dto)
            db.session.commit()
            return True
        return False
    
    def exists_by_username(self, username: str) -> bool:
        """Check if username already exists"""
        return UserDto.query.filter_by(username=username).first() is not None
    
    def exists_by_email(self, email: str) -> bool:
        """Check if email already exists"""
        return UserDto.query.filter_by(email=email).first() is not None
    
    def _dto_to_entity(self, user_dto: UserDto) -> User:
        """Convert DTO to domain entity"""
        return User(
            username=user_dto.username,
            email=user_dto.email,
            password_hash=user_dto.password_hash,
            user_id=user_dto.id,
            documents_generated=user_dto.documents_generated,
            chat_messages_sent=user_dto.chat_messages_sent,
            created_at=user_dto.created_at,
            updated_at=user_dto.updated_at
        )