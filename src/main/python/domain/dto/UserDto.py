from domain.interfaces.dataprovider.DatabaseConfig import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    """Modelo de dados do usuário"""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Demo limits tracking
    documents_generated = db.Column(db.Integer, default=0)
    chat_messages_sent = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        """Define a senha do usuário com hash"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica se a senha está correta"""
        return check_password_hash(self.password_hash, password)

    def can_generate_document(self):
        """Verifica se o usuário pode gerar mais documentos (limite demo: 5)"""
        return self.documents_generated < 5

    def can_send_chat_message(self):
        """Verifica se o usuário pode enviar mais mensagens no chat (limite demo: 5)"""
        return self.chat_messages_sent < 5

    def increment_documents_generated(self):
        """Incrementa o contador de documentos gerados"""
        self.documents_generated += 1

    def increment_chat_messages_sent(self):
        """Incrementa o contador de mensagens de chat enviadas"""
        self.chat_messages_sent += 1

    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'documents_generated': self.documents_generated,
            'chat_messages_sent': self.chat_messages_sent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

