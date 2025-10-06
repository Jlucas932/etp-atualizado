"""
Alembic environment configuration for AutoDocIA v2.0

Suporta múltiplos SGBDs (PostgreSQL, MySQL, SQL Server, SQLite) e
usa naming_convention para nomes de constraints portáveis.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, MetaData
from alembic import context

# Adicionar src/main/python ao path para importar modelos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importar Base do SQLAlchemy e modelos
from domain.interfaces.dataprovider.DatabaseConfig import db

# Importar todos os modelos para que sejam detectados pelo autogenerate
from domain.dto.UserDto import User
from domain.dto.EtpDto import EtpSession, DocumentAnalysis, ChatSession, EtpTemplate
from domain.dto.KbDto import KbDocument, KbChunk, LegalNormCache

# Configurar naming_convention para nomes de constraints portáveis
# Isso garante que índices, FKs e constraints tenham nomes consistentes
# entre diferentes SGBDs
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Aplicar naming_convention ao metadata
target_metadata = db.metadata
target_metadata.naming_convention = naming_convention

# Sobrescrever sqlalchemy.url com DATABASE_URL do ambiente
database_url = os.getenv('DATABASE_URL')
if database_url:
    config.set_main_option('sqlalchemy.url', database_url)
else:
    raise ValueError(
        "DATABASE_URL environment variable is required for migrations.\n"
        "Set it in .env or export it before running alembic commands."
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render tipos como genéricos para portabilidade
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Configurar engine com pool_pre_ping para robustez
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = config.get_main_option('sqlalchemy.url')
    
    # Adicionar pool_pre_ping
    configuration['sqlalchemy.pool_pre_ping'] = 'True'
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Alembic não precisa de pool persistente
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Render tipos como genéricos para portabilidade
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
