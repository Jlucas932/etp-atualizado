from domain.interfaces.dataprovider.DatabaseConfig import db
from datetime import datetime
import json
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Column, Float
from sqlalchemy.dialects.postgresql import JSONB

class KbDocument(db.Model):
    """Modelo para documentos da base de conhecimento"""
    __tablename__ = 'kb_document'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    etp_id = db.Column(db.Integer, db.ForeignKey('etp_sessions.id'), nullable=True)
    objective_slug = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    chunks = db.relationship('KbChunk', backref='kb_document', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<KbDocument {self.filename}>'
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'filename': self.filename,
            'etp_id': self.etp_id,
            'objective_slug': self.objective_slug,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'chunks_count': len(self.chunks)
        }


class KbChunk(db.Model):
    """Modelo para chunks (fragmentos) da base de conhecimento"""
    __tablename__ = 'kb_chunk'
    
    id = db.Column(db.Integer, primary_key=True)
    kb_document_id = db.Column(db.Integer, db.ForeignKey('kb_document.id'), nullable=False, index=True)
    section_type = db.Column(db.String(50), nullable=False, index=True)
    content_text = db.Column(db.Text, nullable=False)
    objective_slug = db.Column(db.String(100), nullable=False, index=True)
    citations_json = db.Column(db.Text, nullable=True)  # JSON string para citações
    embedding = Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<KbChunk {self.id} - {self.section_type}>'

    @property
    def content(self):
        """Propriedade para compatibilidade - mapeia para content_text"""
        return self.content_text
    
    @content.setter
    def content(self, value):
        """Setter para compatibilidade - mapeia para content_text"""
        self.content_text = value
    
    def get_citations(self):
        """Retorna as citações como dicionário"""
        if self.citations_json:
            try:
                return json.loads(self.citations_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_citations(self, citations_dict):
        """Define as citações a partir de um dicionário"""
        self.citations_json = json.dumps(citations_dict, ensure_ascii=False)
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'kb_document_id': self.kb_document_id,
            'section_type': self.section_type,
            'content_text': self.content_text,
            'objective_slug': self.objective_slug,
            'citations': self.get_citations(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def content_preview(self, max_chars=200):
        """Retorna uma prévia do conteúdo do chunk"""
        if len(self.content_text) <= max_chars:
            return self.content_text
        return self.content_text[:max_chars] + "..."


class LegalNormCache(db.Model):
    """Modelo para cache de normas legais"""
    __tablename__ = 'legal_norm_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    norm_urn = db.Column(db.String(500), nullable=False, unique=True, index=True)
    norm_label = db.Column(db.String(1000), nullable=False)
    sphere = db.Column(db.String(50), nullable=False, index=True)  # federal, estadual, municipal
    status = db.Column(db.String(50), nullable=False, index=True)  # active, revoked, modified
    source_json = db.Column(db.Text, nullable=True)  # JSON string para dados da fonte
    last_verified_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<LegalNormCache {self.norm_urn}>'
    
    def get_source_data(self):
        """Retorna os dados da fonte como dicionário"""
        if self.source_json:
            try:
                return json.loads(self.source_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_source_data(self, source_dict):
        """Define os dados da fonte a partir de um dicionário"""
        self.source_json = json.dumps(source_dict, ensure_ascii=False)
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'norm_urn': self.norm_urn,
            'norm_label': self.norm_label,
            'sphere': self.sphere,
            'status': self.status,
            'source_data': self.get_source_data(),
            'last_verified_at': self.last_verified_at.isoformat() if self.last_verified_at else None
        }
    
    def is_recent(self, days=30):
        """Verifica se a norma foi verificada recentemente"""
        if not self.last_verified_at:
            return False
        from datetime import timedelta
        return (datetime.utcnow() - self.last_verified_at) <= timedelta(days=days)