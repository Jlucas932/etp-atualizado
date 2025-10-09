from domain.interfaces.dataprovider.DatabaseConfig import db
from datetime import datetime
import json

class EtpSession(db.Model):
    """Modelo para sessões de geração de ETP"""
    __tablename__ = 'etp_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Status da sessão
    status = db.Column(db.String(50), default='active')  # active, completed, error
    
    # Dados das perguntas
    answers = db.Column(db.Text)  # JSON com as respostas
    answers_validated = db.Column(db.Boolean, default=False)
    
    # Campos para controle de conversa e requisitos
    necessity = db.Column(db.Text)  # Necessidade da contratação capturada
    conversation_stage = db.Column(db.String(50), default='collect_need')  # collect_need, suggest_requirements, review_requirements, legal_norms, done
    requirements_json = db.Column(db.Text)  # JSON com lista de requisitos [{"id":"R1","text":"...","justification":"..."}]
    requirements_version = db.Column(db.Integer, default=0)  # Versão da lista de requisitos para controle de edições incrementais
    
    # Conteúdo gerado
    generated_etp = db.Column(db.Text)  # ETP completo gerado
    preview_content = db.Column(db.Text)  # Preview do ETP
    preview_approved = db.Column(db.Boolean, default=False)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    document_analyses = db.relationship('DocumentAnalysis', backref='etp_session', lazy=True, cascade='all, delete-orphan')
    chat_sessions = db.relationship('ChatSession', backref='etp_session', lazy=True, cascade='all, delete-orphan')
    
    def get_answers(self):
        """Retorna as respostas como dicionário"""
        if self.answers:
            try:
                return json.loads(self.answers)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_answers(self, answers_dict):
        """Define as respostas a partir de um dicionário"""
        self.answers = json.dumps(answers_dict, ensure_ascii=False)
    
    def get_requirements(self):
        """Retorna os requisitos como lista"""
        if self.requirements_json:
            try:
                return json.loads(self.requirements_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_requirements(self, requirements_list):
        """Define os requisitos a partir de uma lista"""
        self.requirements_json = json.dumps(requirements_list, ensure_ascii=False)
    
    def add_requirement(self, req_text, justification=""):
        """Adiciona um novo requisito à lista"""
        requirements = self.get_requirements()
        req_id = f"R{len(requirements) + 1}"
        requirements.append({
            "id": req_id,
            "text": req_text,
            "justification": justification
        })
        self.set_requirements(requirements)
        return req_id
    
    def update_requirement(self, req_id, new_text=None, new_justification=None):
        """Atualiza um requisito específico"""
        requirements = self.get_requirements()
        for req in requirements:
            if req["id"] == req_id:
                if new_text:
                    req["text"] = new_text
                if new_justification:
                    req["justification"] = new_justification
                break
        self.set_requirements(requirements)
    
    def remove_requirements(self, req_ids):
        """Remove requisitos por IDs e renumera os restantes"""
        requirements = self.get_requirements()
        # Filtrar requisitos a remover
        filtered_reqs = [req for req in requirements if req["id"] not in req_ids]
        # Renumerar IDs
        for i, req in enumerate(filtered_reqs, 1):
            req["id"] = f"R{i}"
        self.set_requirements(filtered_reqs)
    
    def keep_only_requirements(self, req_ids):
        """Mantém apenas os requisitos especificados e renumera"""
        requirements = self.get_requirements()
        # Filtrar apenas os requisitos desejados
        kept_reqs = [req for req in requirements if req["id"] in req_ids]
        # Renumerar IDs
        for i, req in enumerate(kept_reqs, 1):
            req["id"] = f"R{i}"
        self.set_requirements(kept_reqs)
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'status': self.status,
            'answers': self.get_answers(),
            'answers_validated': self.answers_validated,
            'has_generated_etp': bool(self.generated_etp),
            'preview_approved': self.preview_approved,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class DocumentAnalysis(db.Model):
    """Modelo para análise de documentos"""
    __tablename__ = 'document_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), db.ForeignKey('etp_sessions.session_id'), nullable=False)
    
    # Informações do arquivo
    filename = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False)  # SHA-256 do arquivo
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50))
    
    # Análise
    extracted_text = db.Column(db.Text)
    analysis_result = db.Column(db.Text)  # JSON com resultado da análise
    confidence_score = db.Column(db.Float, default=0.0)
    
    # Status
    status = db.Column(db.String(50), default='processing')  # processing, completed, error
    error_message = db.Column(db.Text)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_analysis_result(self):
        """Retorna o resultado da análise como dicionário"""
        if self.analysis_result:
            try:
                return json.loads(self.analysis_result)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_analysis_result(self, result_dict):
        """Define o resultado da análise a partir de um dicionário"""
        self.analysis_result = json.dumps(result_dict, ensure_ascii=False)
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
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

class KnowledgeBase(db.Model):
    """Modelo para base de conhecimento de documentos"""
    __tablename__ = 'knowledge_base'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Informações do documento
    filename = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), unique=True, nullable=False)
    document_type = db.Column(db.String(100))  # ETP, contrato, etc.
    
    # Conteúdo estruturado
    structured_content = db.Column(db.Text)  # JSON com conteúdo estruturado
    keywords = db.Column(db.Text)  # JSON com palavras-chave
    sections = db.Column(db.Text)  # JSON com seções identificadas
    
    # Metadados
    processing_version = db.Column(db.String(20), default='1.0')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_structured_content(self):
        """Retorna o conteúdo estruturado como dicionário"""
        if self.structured_content:
            try:
                return json.loads(self.structured_content)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_structured_content(self, content_dict):
        """Define o conteúdo estruturado a partir de um dicionário"""
        self.structured_content = json.dumps(content_dict, ensure_ascii=False)
    
    def get_keywords(self):
        """Retorna as palavras-chave como lista"""
        if self.keywords:
            try:
                return json.loads(self.keywords)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_keywords(self, keywords_list):
        """Define as palavras-chave a partir de uma lista"""
        self.keywords = json.dumps(keywords_list, ensure_ascii=False)
    
    def get_sections(self):
        """Retorna as seções como dicionário"""
        if self.sections:
            try:
                return json.loads(self.sections)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_sections(self, sections_dict):
        """Define as seções a partir de um dicionário"""
        self.sections = json.dumps(sections_dict, ensure_ascii=False)
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
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

class ChatSession(db.Model):
    """Modelo para sessões de chat"""
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), db.ForeignKey('etp_sessions.session_id'), nullable=False)
    
    # Dados da conversa
    messages = db.Column(db.Text)  # JSON com mensagens
    context = db.Column(db.Text)  # Contexto da conversa
    
    # Campos para controle de conversa e requisitos
    necessity = db.Column(db.Text)  # Necessidade da contratação capturada
    conversation_stage = db.Column(db.String(50), default='collect_need')  # collect_need, suggest_requirements, review_requirements, legal_norms, done
    requirements_json = db.Column(db.Text)  # JSON com lista de requisitos [{"id":"R1","text":"...","justification":"..."}]
    
    # Status
    status = db.Column(db.String(50), default='active')  # active, completed
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_messages(self):
        """Retorna as mensagens como lista"""
        if self.messages:
            try:
                return json.loads(self.messages)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_messages(self, messages_list):
        """Define as mensagens a partir de uma lista"""
        self.messages = json.dumps(messages_list, ensure_ascii=False)
    
    def add_message(self, role, content):
        """Adiciona uma mensagem à conversa"""
        messages = self.get_messages()
        messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        })
        self.set_messages(messages)
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'messages': self.get_messages(),
            'context': self.context,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class EtpTemplate(db.Model):
    """Modelo para templates de ETP"""
    __tablename__ = 'etp_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Estrutura do template
    template_structure = db.Column(db.Text)  # JSON com estrutura
    default_content = db.Column(db.Text)  # Conteúdo padrão
    
    # Configurações
    is_active = db.Column(db.Boolean, default=True)
    version = db.Column(db.String(20), default='1.0')
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_template_structure(self):
        """Retorna a estrutura do template como dicionário"""
        if self.template_structure:
            try:
                return json.loads(self.template_structure)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_template_structure(self, structure_dict):
        """Define a estrutura do template a partir de um dicionário"""
        self.template_structure = json.dumps(structure_dict, ensure_ascii=False)
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'template_structure': self.get_template_structure(),
            'default_content': self.default_content,
            'is_active': self.is_active,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

