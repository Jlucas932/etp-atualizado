import os
from flask_sqlalchemy import SQLAlchemy

# Instância global do SQLAlchemy
db = SQLAlchemy()

def init_database(app, basedir):
    """Inicializa e configura o banco de dados"""
    
    # Configurar database usando DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise RuntimeError(
            "❌ DATABASE_URL não configurada. "
            "Configure no docker-compose.yml ou arquivo .env. "
            "Exemplo: postgresql+psycopg2://user:pass@host:5432/db"
        )
    
    if not database_url.startswith('postgresql'):
        raise RuntimeError(
            f"❌ DATABASE_URL deve ser PostgreSQL. "
            f"Recebido: {database_url.split('://')[0]}. "
            f"SQLite não é mais suportado para conversas persistentes."
        )
    
    # Configurar PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    masked_url = database_url.split('@')[0].split('://')[0] + "://***@" + database_url.split('@')[1] if '@' in database_url else "***"
    print(f"✅ Configurando PostgreSQL: {masked_url}")
    print(f"ℹ️  Banco de dados: PostgreSQL (produção)")
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Inicializar banco
    db.init_app(app)
    
    # Importar modelos para garantir que sejam registrados
    from domain.dto.UserDto import User
    from domain.dto.EtpOrm import EtpSession, EtpDocument
    # Importar novos modelos KB (substituem os antigos do KnowledgeBaseDto)
    from domain.dto.KbDto import KbDocument, KbChunk, LegalNormCache
    # Importar modelos de conversação para chat persistente
    from domain.dto.ConversationModels import Conversation, Message

    with app.app_context():
        print("🔧 Criando tabelas usando SQLAlchemy...")
        db.create_all()
        print("✅ Tabelas criadas com sucesso!")
        seed_demo_users()

    print(f"✅ Banco de dados configurado com sucesso!")

    return db

def seed_demo_users():
    """Popula o banco com os usuários demo pré-definidos"""
    from domain.dto.UserDto import User
    
    demo_users = [
        {
            "username": "demo_user1",
            "email": "demo1@example.com",
            "password": "demo123"
        },
        {
            "username": "demo_user2",
            "email": "demo2@example.com",
            "password": "demo123"
        },
        {
            "username": "demo_user3",
            "email": "demo3@example.com",
            "password": "demo123"
        },
        {
            "username": "demo_user4",
            "email": "demo4@example.com",
            "password": "demo123"
        },
        {
            "username": "demo_user5",
            "email": "demo5@example.com",
            "password": "demo123"
        },
        {
            "username": "demo_user6",
            "email": "demo6@example.com",
            "password": "demo123"
        }
    ]
    
    created_count = 0
    for user_data in demo_users:
        # Verificar se o usuário já existe
        existing_user = User.query.filter_by(username=user_data['username']).first()
        
        if not existing_user:
            user = User(
                username=user_data['username'],
                email=user_data['email']
            )
            user.set_password(user_data['password'])
            
            db.session.add(user)
            created_count += 1
    
    if created_count > 0:
        db.session.commit()
        print(f"✅ {created_count} usuários demo criados")
    else:
        print("ℹ️ Usuários demo já existem no banco")

