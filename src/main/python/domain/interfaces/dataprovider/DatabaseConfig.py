import os
import logging
from flask_sqlalchemy import SQLAlchemy
from domain.usecase.utils.security_utils import mask_database_url

# Instância global do SQLAlchemy
db = SQLAlchemy()

def init_database(app, basedir):
    """
    Inicializa e configura o banco de dados com suporte multi-SGBD.
    
    Suporta:
    - PostgreSQL (psycopg2)
    - MySQL/MariaDB (pymysql)
    - SQL Server (pyodbc)
    - SQLite (para desenvolvimento)
    
    Configurações de pool de conexões são lidas de variáveis de ambiente.
    """
    
    # Configurar database usando DATABASE_URL (obrigatório)
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable is required.\n"
            "Examples:\n"
            "  PostgreSQL: postgresql+psycopg2://user:pass@host:5432/db\n"
            "  MySQL:      mysql+pymysql://user:pass@host:3306/db\n"
            "  SQL Server: mssql+pyodbc://user:pass@host:1433/db?driver=ODBC+Driver+17+for+SQL+Server\n"
            "  SQLite:     sqlite:///./data/autodoc.db"
        )
    
    # Detectar dialeto do banco a partir da URL
    dialect = database_url.split(':')[0].split('+')[0].lower()
    
    # Configurar URI do banco
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Configurar opções de engine (pool de conexões)
    engine_options = app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {}).copy()

    # Pool size (número de conexões persistentes)
    pool_size = int(os.getenv('DB_POOL_SIZE', str(engine_options.get('pool_size', 5))))
    engine_options['pool_size'] = pool_size

    # Max overflow (conexões adicionais temporárias)
    max_overflow = int(os.getenv('DB_MAX_OVERFLOW', str(engine_options.get('max_overflow', 10))))
    engine_options['max_overflow'] = max_overflow

    # Pool recycle (segundos antes de reciclar conexão)
    pool_recycle = int(os.getenv('DB_POOL_RECYCLE', str(engine_options.get('pool_recycle', 3600))))
    engine_options['pool_recycle'] = pool_recycle

    # Garantir opções essenciais independentemente de env
    engine_options['pool_pre_ping'] = True
    engine_options['future'] = True

    # Configurações específicas por dialeto
    if dialect == 'sqlite':
        # SQLite não suporta pool, desabilitar
        engine_options['pool_pre_ping'] = False
        engine_options.pop('pool_size', None)
        engine_options.pop('max_overflow', None)
        logging.info("✅ Configurando SQLite: %s", mask_database_url(database_url))
    elif dialect in ('postgresql', 'postgres'):
        logging.info("✅ Configurando PostgreSQL: %s", mask_database_url(database_url))
    elif dialect == 'mysql':
        logging.info("✅ Configurando MySQL: %s", mask_database_url(database_url))
    elif dialect == 'mssql':
        logging.info("✅ Configurando SQL Server: %s", mask_database_url(database_url))
    else:
        logging.warning("⚠️  Dialeto desconhecido '%s', usando configuração genérica", dialect)
    
    # Aplicar engine options
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options

    # Log de configuração de pool (sem expor credenciais)
    if dialect != 'sqlite':
        logging.info(
            "   Pool: size=%s, overflow=%s, recycle=%ss, pre_ping=%s, future=%s",
            engine_options.get('pool_size'),
            engine_options.get('max_overflow'),
            engine_options.get('pool_recycle'),
            engine_options.get('pool_pre_ping'),
            engine_options.get('future'),
        )
    
    # Inicializar banco
    db.init_app(app)
    
    # Importar modelos para garantir que sejam registrados
    from domain.dto.UserDto import User
    from domain.dto.EtpDto import EtpSession, DocumentAnalysis, ChatSession, EtpTemplate
    # Importar novos modelos KB (substituem os antigos do KnowledgeBaseDto)
    from domain.dto.KbDto import KbDocument, KbChunk, LegalNormCache
    
    with app.app_context():
        # create_all e seed controlados por flags
        create_all_flag = os.getenv('DB_CREATE_ALL', 'false').lower() == 'true'
        seed_flag = os.getenv('SEED_DEMO_USERS', 'false').lower() == 'true'

        if dialect == 'sqlite' or create_all_flag:
            logging.info("🔧 Criando tabelas com SQLAlchemy (dialeto: %s, DB_CREATE_ALL=%s)", dialect, create_all_flag)
            db.create_all()
            logging.info("✅ Tabelas criadas com sucesso!")
        else:
            logging.info(
                "ℹ️  DB_CREATE_ALL desabilitado para dialeto '%s' — assumindo migrações gerenciadas externamente.",
                dialect,
            )

        if seed_flag:
            logging.info("🌱 Populando usuários demo (SEED_DEMO_USERS habilitado)")
            seed_demo_users()
        else:
            logging.info("ℹ️  SEED_DEMO_USERS desabilitado — nenhuma seed executada.")

    logging.info("✅ Banco de dados configurado com sucesso!")
    
    return db

def seed_demo_users():
    """Popula o banco com usuários demo seguros."""
    from domain.dto.UserDto import User
    from werkzeug.security import generate_password_hash

    demo_users = (
        ("demo_user1", "demo1@example.com", "demo123"),
        ("demo_user2", "demo2@example.com", "demo123"),
        ("demo_user3", "demo3@example.com", "demo123"),
        ("demo_user4", "demo4@example.com", "demo123"),
    )

    logging.info("👤 Verificando usuários demo pré-configurados...")

    created_any = False

    for username, email, plain_password in demo_users:
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            continue

        hashed_password = generate_password_hash(plain_password)
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        created_any = True

    if created_any:
        db.session.commit()
        logging.info("✅ Usuários demo criados/atualizados com sucesso.")
    else:
        logging.info("ℹ️  Usuários demo já existentes — nenhuma alteração realizada.")

