from abc import ABC, abstractmethod
from typing import Optional, List
from domain.entities.KnowledgeBase import KnowledgeBase


class KnowledgeBaseRepositoryInterface(ABC):
    """Interface for KnowledgeBase repository operations"""
    
    @abstractmethod
    def create(self, knowledge_base: KnowledgeBase) -> KnowledgeBase:
        """
        Create a new knowledge base entry
        
        Args:
            knowledge_base: KnowledgeBase entity to create
            
        Returns:
            Created knowledge base entry with assigned ID
        """
        pass
    
    @abstractmethod
    def find_by_id(self, knowledge_id: int) -> Optional[KnowledgeBase]:
        """
        Find knowledge base entry by ID
        
        Args:
            knowledge_id: Knowledge base ID to search for
            
        Returns:
            KnowledgeBase entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_file_hash(self, file_hash: str) -> Optional[KnowledgeBase]:
        """
        Find knowledge base entry by file hash
        
        Args:
            file_hash: File hash to search for
            
        Returns:
            KnowledgeBase entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_document_type(self, document_type: str) -> List[KnowledgeBase]:
        """
        Find knowledge base entries by document type
        
        Args:
            document_type: Document type to search for (ETP, contrato, etc.)
            
        Returns:
            List of KnowledgeBase entities with the specified document type
        """
        pass
    
    @abstractmethod
    def find_by_filename(self, filename: str) -> List[KnowledgeBase]:
        """
        Find knowledge base entries by filename
        
        Args:
            filename: Filename to search for
            
        Returns:
            List of KnowledgeBase entities with the specified filename
        """
        pass
    
    @abstractmethod
    def find_by_keyword(self, keyword: str) -> List[KnowledgeBase]:
        """
        Find knowledge base entries containing a specific keyword
        
        Args:
            keyword: Keyword to search for
            
        Returns:
            List of KnowledgeBase entities containing the keyword
        """
        pass
    
    @abstractmethod
    def find_by_processing_version(self, version: str) -> List[KnowledgeBase]:
        """
        Find knowledge base entries by processing version
        
        Args:
            version: Processing version to search for
            
        Returns:
            List of KnowledgeBase entities with the specified version
        """
        pass
    
    @abstractmethod
    def find_all(self) -> List[KnowledgeBase]:
        """
        Get all knowledge base entries
        
        Returns:
            List of all KnowledgeBase entities
        """
        pass
    
    @abstractmethod
    def update(self, knowledge_base: KnowledgeBase) -> KnowledgeBase:
        """
        Update existing knowledge base entry
        
        Args:
            knowledge_base: KnowledgeBase entity with updated data
            
        Returns:
            Updated KnowledgeBase entity
        """
        pass
    
    @abstractmethod
    def delete(self, knowledge_id: int) -> bool:
        """
        Delete knowledge base entry by ID
        
        Args:
            knowledge_id: ID of knowledge base entry to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def delete_by_file_hash(self, file_hash: str) -> bool:
        """
        Delete knowledge base entry by file hash
        
        Args:
            file_hash: File hash of entry to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def exists_by_file_hash(self, file_hash: str) -> bool:
        """
        Check if knowledge base entry with file hash already exists
        
        Args:
            file_hash: File hash to check
            
        Returns:
            True if file hash exists, False otherwise
        """
        pass
    
    @abstractmethod
    def search_by_content(self, search_term: str) -> List[KnowledgeBase]:
        """
        Search knowledge base entries by content
        
        Args:
            search_term: Term to search for in structured content
            
        Returns:
            List of KnowledgeBase entities matching the search term
        """
        pass