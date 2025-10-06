from abc import ABC, abstractmethod
from typing import Optional, List
from domain.entities.DocumentAnalysis import DocumentAnalysis


class DocumentAnalysisRepositoryInterface(ABC):
    """Interface for DocumentAnalysis repository operations"""
    
    @abstractmethod
    def create(self, document_analysis: DocumentAnalysis) -> DocumentAnalysis:
        """
        Create a new document analysis
        
        Args:
            document_analysis: DocumentAnalysis entity to create
            
        Returns:
            Created document analysis with assigned ID
        """
        pass
    
    @abstractmethod
    def find_by_id(self, analysis_id: int) -> Optional[DocumentAnalysis]:
        """
        Find document analysis by ID
        
        Args:
            analysis_id: Analysis ID to search for
            
        Returns:
            DocumentAnalysis entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_session_id(self, session_id: str) -> List[DocumentAnalysis]:
        """
        Find document analyses by session ID
        
        Args:
            session_id: Session ID to search for
            
        Returns:
            List of DocumentAnalysis entities for the session
        """
        pass
    
    @abstractmethod
    def find_by_file_hash(self, file_hash: str) -> Optional[DocumentAnalysis]:
        """
        Find document analysis by file hash
        
        Args:
            file_hash: File hash to search for
            
        Returns:
            DocumentAnalysis entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_status(self, status: str) -> List[DocumentAnalysis]:
        """
        Find document analyses by status
        
        Args:
            status: Status to search for (processing, completed, error)
            
        Returns:
            List of DocumentAnalysis entities with the specified status
        """
        pass
    
    @abstractmethod
    def find_by_filename(self, filename: str) -> List[DocumentAnalysis]:
        """
        Find document analyses by filename
        
        Args:
            filename: Filename to search for
            
        Returns:
            List of DocumentAnalysis entities with the specified filename
        """
        pass
    
    @abstractmethod
    def find_all(self) -> List[DocumentAnalysis]:
        """
        Get all document analyses
        
        Returns:
            List of all DocumentAnalysis entities
        """
        pass
    
    @abstractmethod
    def update(self, document_analysis: DocumentAnalysis) -> DocumentAnalysis:
        """
        Update existing document analysis
        
        Args:
            document_analysis: DocumentAnalysis entity with updated data
            
        Returns:
            Updated DocumentAnalysis entity
        """
        pass
    
    @abstractmethod
    def delete(self, analysis_id: int) -> bool:
        """
        Delete document analysis by ID
        
        Args:
            analysis_id: ID of analysis to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def delete_by_session_id(self, session_id: str) -> bool:
        """
        Delete all document analyses for a session
        
        Args:
            session_id: Session ID to delete analyses for
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def exists_by_file_hash(self, file_hash: str) -> bool:
        """
        Check if document with file hash already exists
        
        Args:
            file_hash: File hash to check
            
        Returns:
            True if file hash exists, False otherwise
        """
        pass