from datetime import datetime
from typing import Optional, Dict, List


class KnowledgeBase:
    """Pure domain entity for KnowledgeBase without ORM dependencies"""
    
    def __init__(self,
                 filename: str,
                 file_hash: str,
                 document_type: Optional[str] = None,
                 structured_content: Optional[Dict] = None,
                 keywords: Optional[List[str]] = None,
                 sections: Optional[Dict] = None,
                 processing_version: str = '1.0',
                 knowledge_id: Optional[int] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self.id = knowledge_id
        self.filename = filename
        self.file_hash = file_hash
        self.document_type = document_type  # ETP, contrato, etc.
        self.structured_content = structured_content or {}
        self.keywords = keywords or []
        self.sections = sections or {}
        self.processing_version = processing_version
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def get_structured_content(self) -> Dict:
        """Retorna o conteúdo estruturado como dicionário"""
        return self.structured_content or {}
    
    def set_structured_content(self, content_dict: Dict) -> None:
        """Define o conteúdo estruturado a partir de um dicionário"""
        self.structured_content = content_dict
        self.updated_at = datetime.utcnow()

    def get_keywords(self) -> List[str]:
        """Retorna as palavras-chave como lista"""
        return self.keywords or []
    
    def set_keywords(self, keywords_list: List[str]) -> None:
        """Define as palavras-chave a partir de uma lista"""
        self.keywords = keywords_list
        self.updated_at = datetime.utcnow()

    def add_keyword(self, keyword: str) -> None:
        """Adiciona uma palavra-chave"""
        if keyword not in self.keywords:
            self.keywords.append(keyword)
            self.updated_at = datetime.utcnow()

    def remove_keyword(self, keyword: str) -> None:
        """Remove uma palavra-chave"""
        if keyword in self.keywords:
            self.keywords.remove(keyword)
            self.updated_at = datetime.utcnow()

    def get_sections(self) -> Dict:
        """Retorna as seções como dicionário"""
        return self.sections or {}
    
    def set_sections(self, sections_dict: Dict) -> None:
        """Define as seções a partir de um dicionário"""
        self.sections = sections_dict
        self.updated_at = datetime.utcnow()

    def add_section(self, section_name: str, section_content: str) -> None:
        """Adiciona uma seção"""
        if not self.sections:
            self.sections = {}
        self.sections[section_name] = section_content
        self.updated_at = datetime.utcnow()

    def remove_section(self, section_name: str) -> None:
        """Remove uma seção"""
        if self.sections and section_name in self.sections:
            del self.sections[section_name]
            self.updated_at = datetime.utcnow()

    def update_processing_version(self, version: str) -> None:
        """Atualiza a versão de processamento"""
        self.processing_version = version
        self.updated_at = datetime.utcnow()

    def has_content(self) -> bool:
        """Verifica se possui conteúdo estruturado"""
        return bool(self.structured_content)

    def has_keywords(self) -> bool:
        """Verifica se possui palavras-chave"""
        return bool(self.keywords)

    def has_sections(self) -> bool:
        """Verifica se possui seções"""
        return bool(self.sections)

    def to_dict(self) -> Dict:
        """Converte a entidade para dicionário"""
        return {
            'id': self.id,
            'filename': self.filename,
            'file_hash': self.file_hash,
            'document_type': self.document_type,
            'structured_content': self.get_structured_content(),
            'keywords': self.get_keywords(),
            'sections': self.get_sections(),
            'processing_version': self.processing_version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self) -> str:
        return f'<KnowledgeBase {self.filename} ({self.document_type})>'