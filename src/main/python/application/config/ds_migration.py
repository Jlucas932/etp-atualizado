import os
from typing import List, Dict
import logging

from domain.interfaces.dataprovider.DatabaseConfig import db
from .liquibase_config import executa_liquibase


def configurar_migracoes():
    """
    Configura e executa as migrações do banco de dados
    Esta função é chamada na inicialização da aplicação
    """
    try:
        print("Iniciando configuração de migrações...")
        
        # Verificar se deve executar migrações via Liquibase
        execute_liquibase = os.getenv('EXECUTE_LIQUIBASE', 'true').lower() == 'true'
        db_vendor = os.getenv('DB_VENDOR', 'sqlite')
        
        if execute_liquibase and db_vendor == 'postgresql':
            print("Executando migrações via Liquibase para PostgreSQL...")
            executa_liquibase()
        else:
            print(f"Pulando Liquibase. DB_VENDOR={db_vendor}, EXECUTE_LIQUIBASE={execute_liquibase}")
        
        # Para desenvolvimento com SQLite ou se Liquibase falhar, usar SQLAlchemy
        if db_vendor == 'sqlite' or not execute_liquibase:
            print("Executando criação de tabelas via SQLAlchemy...")
            configurar_tabelas_sqlalchemy()
            
        print("Configuração de migrações concluída com sucesso!")
        
    except Exception as e:
        logging.error(f"Erro na configuração de migrações: {e}")
        print(f"ERRO: Falha na configuração de migrações: {e}")
        
        # Fallback para SQLAlchemy em caso de erro
        print("Tentando fallback para SQLAlchemy...")
        try:
            configurar_tabelas_sqlalchemy()
            print("Fallback para SQLAlchemy executado com sucesso!")
        except Exception as fallback_error:
            logging.error(f"Erro no fallback SQLAlchemy: {fallback_error}")
            raise fallback_error


def configurar_tabelas_sqlalchemy():
    """
    Configura tabelas usando SQLAlchemy como fallback
    Exclui as tabelas gerenciadas por Liquibase se estiver em modo Liquibase
    """
    try:
        # Import dos modelos para garantir que estejam registrados
        from domain.dto.EtpDto import EtpSession, DocumentAnalysis, ChatSession, EtpTemplate
        from domain.dto.UserDto import User
        from domain.dto.KnowledgeBaseDto import KbDocument as OldKbDocument, KbChunk as OldKbChunk
        
        execute_liquibase = os.getenv('EXECUTE_LIQUIBASE', 'true').lower() == 'true'
        db_vendor = os.getenv('DB_VENDOR', 'sqlite')
        
        # Se estiver usando Liquibase para PostgreSQL, não criar as tabelas KB via SQLAlchemy
        if execute_liquibase and db_vendor == 'postgresql':
            # Remover as tabelas KB do metadata para que não sejam criadas por db.create_all()
            tables_to_skip = ['kb_document', 'kb_chunk', 'legal_norm_cache']
            
            # Cria apenas as tabelas que não são gerenciadas por Liquibase
            for table_name, table in db.metadata.tables.items():
                if table_name not in tables_to_skip:
                    if not db.engine.dialect.has_table(db.engine.connect(), table_name):
                        table.create(db.engine)
                        print(f"Tabela criada via SQLAlchemy: {table_name}")
        else:
            # Criar todas as tabelas via SQLAlchemy (desenvolvimento/SQLite)
            db.create_all()
            print("Todas as tabelas criadas via SQLAlchemy")
            
    except Exception as e:
        logging.error(f"Erro na configuração SQLAlchemy: {e}")
        raise


def verificar_status_migracao() -> Dict[str, any]:
    """
    Verifica o status das migrações e tabelas
    Retorna informações sobre o estado atual do banco
    """
    status = {
        'db_vendor': os.getenv('DB_VENDOR', 'sqlite'),
        'execute_liquibase': os.getenv('EXECUTE_LIQUIBASE', 'true').lower() == 'true',
        'tables_exist': {},
        'migration_status': 'unknown'
    }
    
    try:
        # Verificar se as tabelas KB existem
        kb_tables = ['kb_document', 'kb_chunk', 'legal_norm_cache']
        
        with db.engine.connect() as connection:
            for table_name in kb_tables:
                try:
                    from sqlalchemy import text
                    result = connection.execute(text(f"SELECT 1 FROM {table_name} LIMIT 1"))
                    status['tables_exist'][table_name] = True
                except:
                    status['tables_exist'][table_name] = False
        
        # Verificar se todas as tabelas KB existem
        all_kb_tables_exist = all(status['tables_exist'].values())
        status['migration_status'] = 'completed' if all_kb_tables_exist else 'pending'
        
    except Exception as e:
        logging.error(f"Erro ao verificar status de migração: {e}")
        status['migration_status'] = 'error'
        status['error'] = str(e)
    
    return status


def listar_tabelas_disponiveis() -> List[str]:
    """
    Lista todas as tabelas disponíveis no banco de dados
    """
    try:
        from sqlalchemy import text
        with db.engine.connect() as connection:
            if os.getenv('DB_VENDOR', 'sqlite') == 'postgresql':
                result = connection.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """))
            else:
                result = connection.execute(text("""
                    SELECT name 
                    FROM sqlite_master 
                    WHERE type='table' 
                    ORDER BY name
                """))
            
            return [row[0] for row in result.fetchall()]
            
    except Exception as e:
        logging.error(f"Erro ao listar tabelas: {e}")
        return []