from datetime import datetime
from typing import Optional, Dict


class DocumentAnalysis:
    """Pure domain entity for DocumentAnalysis without ORM dependencies"""
    
    def __init__(self,
                 session_id: str,
                 filename: str,
                 file_hash: str,
                 file_size: Optional[int] = None,
                 file_type: Optional[str] = None,
                 extracted_text: Optional[str] = None,
                 analysis_result: Optional[Dict] = None,
                 confidence_score: float = 0.0,
                 status: str = 'processing',
                 error_message: Optional[str] = None,
                 analysis_id: Optional[int] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self.id = analysis_id
        self.session_id = session_id
        self.filename = filename
        self.file_hash = file_hash
        self.file_size = file_size
        self.file_type = file_type
        self.extracted_text = extracted_text
        self.analysis_result = analysis_result or {}
        self.confidence_score = confidence_score
        self.status = status  # processing, completed, error
        self.error_message = error_message
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def get_analysis_result(self) -> Dict:
        """Retorna o resultado da análise como dicionário"""
        return self.analysis_result or {}
    
    def set_analysis_result(self, result_dict: Dict) -> None:
        """Define o resultado da análise a partir de um dicionário"""
        self.analysis_result = result_dict
        self.updated_at = datetime.utcnow()

    def set_extracted_text(self, text: str) -> None:
        """Define o texto extraído do documento"""
        self.extracted_text = text
        self.updated_at = datetime.utcnow()

    def set_confidence_score(self, score: float) -> None:
        """Define o score de confiança da análise"""
        self.confidence_score = max(0.0, min(1.0, score))  # Garantir entre 0 e 1
        self.updated_at = datetime.utcnow()

    def complete_processing(self) -> None:
        """Marca o processamento como completo"""
        self.status = 'completed'
        self.updated_at = datetime.utcnow()

    def mark_error(self, error_message: str) -> None:
        """Marca o processamento com erro"""
        self.status = 'error'
        self.error_message = error_message
        self.updated_at = datetime.utcnow()

    def is_processing(self) -> bool:
        """Verifica se ainda está em processamento"""
        return self.status == 'processing'

    def is_completed(self) -> bool:
        """Verifica se o processamento foi completado"""
        return self.status == 'completed'

    def has_error(self) -> bool:
        """Verifica se houve erro no processamento"""
        return self.status == 'error'

    def to_dict(self) -> Dict:
        """Converte a entidade para dicionário"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'filename': self.filename,
            'file_hash': self.file_hash,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'analysis_result': self.get_analysis_result(),
            'confidence_score': self.confidence_score,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self) -> str:
        return f'<DocumentAnalysis {self.filename} ({self.status})>'