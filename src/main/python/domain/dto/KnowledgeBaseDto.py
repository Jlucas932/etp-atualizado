"""
Módulo de DTOs para a base de conhecimento RAG
"""

from dataclasses import dataclass
from typing import List, Optional
from .KbDto import KbDocument, KbChunk, LegalNormCache

# Re-exportar as classes existentes para compatibilidade
__all__ = ['KbDocument', 'KbChunk', 'LegalNormCache', 'KnowledgeBaseDocument']

@dataclass
class KnowledgeBaseDocument:
    """
    Estrutura de dados para documentos da base de conhecimento.
    Usado para indexação e processamento antes da persistência no banco.
    """
    id: str
    title: str
    section: str
    content: str
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> dict:
        """Converte para dicionário"""
        return {
            'id': self.id,
            'title': self.title,
            'section': self.section,
            'content': self.content,
            'embedding': self.embedding
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'KnowledgeBaseDocument':
        """Cria instância a partir de dicionário"""
        return cls(
            id=data['id'],
            title=data['title'],
            section=data['section'],
            content=data['content'],
            embedding=data.get('embedding')
        )