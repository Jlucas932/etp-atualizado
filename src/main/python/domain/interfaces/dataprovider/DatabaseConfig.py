import os
from flask_sqlalchemy import SQLAlchemy

# Instância global do SQLAlchemy
db = SQLAlchemy()

def init_database(app, basedir):
    """Inicializa e configura o banco de dados"""
    
    # Configurar database usando DATABASE_URL (obrigatório)
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required. PostgreSQL connection must be configured.")
    
    # Configurar PostgreSQL usando DATABASE_URL
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print(f"✅ Configurando PostgreSQL: {database_url}")
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Inicializar banco
    db.init_app(app)
    
    # Importar modelos para garantir que sejam registrados
    from domain.dto.UserDto import User
    from domain.dto.EtpOrm import EtpSession
    from domain.dto.EtpDto import DocumentAnalysis, ChatSession, EtpTemplate
    # Importar novos modelos KB (substituem os antigos do KnowledgeBaseDto)
    from domain.dto.KbDto import KbDocument, KbChunk, LegalNormCache

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

