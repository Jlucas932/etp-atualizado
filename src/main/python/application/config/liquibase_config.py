import configparser
import os
from typing import Dict, Any

from domain.interfaces.dataprovider.DatabaseConfig import db


def get_configuracao_liquibase() -> Dict[str, Any]:
    """Retorna configuração do Liquibase baseada nas variáveis de ambiente - PostgreSQL obrigatório"""
    db_vendor = 'postgresql'  # Apenas PostgreSQL suportado
    db_url = os.environ['DATABASE_URL']  # DATABASE_URL obrigatório
    
    # Parse da URL PostgreSQL para extrair componentes
    # Exemplo: postgresql+psycopg2://user:pass@host:port/database
    import re
    match = re.match(r'postgresql(\+psycopg2)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
    if match:
        _, username, password, host, port, database = match.groups()
    else:
        raise ValueError("DATABASE_URL deve estar no formato PostgreSQL válido: postgresql+psycopg2://user:pass@host:port/database")
    
    config = {
        'pyliquibase': {
            'path': 'src/main/resources/migration/configuration/master.json',
            'database_vendor_name': db_vendor,
            'default_schema': 'public',
            'context': 'desenvolvimento',
            'create_schema': []
        },
        'command': {
            'url': db_url,
            'username': username,
            'password': password,
            'driver': 'org.postgresql.Driver'
        }
    }
    
    return config


def pre_liquibase_callback_conexao(sql_criador_de_schema: str):
    """Callback para executar SQL antes do Liquibase (criação de schemas)"""
    try:
        with db.engine.connect() as connection:
            connection.execute(sql_criador_de_schema)
            connection.commit()
    except Exception as e:
        print(f"Erro ao executar callback pré-Liquibase: {e}")
        raise


def executa_liquibase() -> None:
    """Executa as migrações do Liquibase"""
    try:
        from hal_pyliquibase import Pyliquibase
        
        path_config_liquibase = preparar_arquivo_configuracao_liquibase()
        config_liquibase = get_configuracao_liquibase()
        
        schemas = config_liquibase['pyliquibase'].get("create_schema", [])
        database_vendor_name = config_liquibase['pyliquibase']["database_vendor_name"]
        context = config_liquibase['pyliquibase']['context']
        
        liquibase = Pyliquibase(
            defaultsFile=path_config_liquibase, logLevel='INFO'
        )
        
        # PostgreSQL sempre executa schemas se definidos
        if schemas:
            liquibase.pre_execute(
                database_vendor_name, pre_liquibase_callback_conexao, schemas
            )
        
        liquibase.execute('update')
        print("Migrações Liquibase executadas com sucesso!")
        
    except ImportError:
        print("AVISO: hal_pyliquibase não encontrado. Pulando migrações Liquibase.")
        print("Para habilitar migrações, instale: pip install hal_pyliquibase")
    except Exception as e:
        print(f"Erro na execução do Liquibase: {e}")
        raise
    finally:
        if 'path_config_liquibase' in locals():
            remover_configuracoes_liquibase(path_config_liquibase)


def preparar_arquivo_configuracao_liquibase() -> str:
    """Prepara o arquivo de configuração do Liquibase"""
    config_liquibase = get_configuracao_liquibase()
    config_file = configparser.RawConfigParser()
    
    config_file['DEFAULT'] = {}
    config_file['DEFAULT']["changeLogFile"] = config_liquibase['pyliquibase']['path']
    config_file['DEFAULT']["liquibase.liquibaseSchemaName"] = config_liquibase['pyliquibase']['default_schema']
    config_file['DEFAULT']["contexts"] = config_liquibase['pyliquibase']['context']
    
    for key, value in config_liquibase['command'].items():
        config_file['DEFAULT'][f'liquibase.command.{key}'] = str(value)
    
    path_config_liquibase = 'src/main/resources/migration/database/liquibase.properties'
    
    # Criar diretório se não existir
    os.makedirs(os.path.dirname(path_config_liquibase), exist_ok=True)
    
    with open(path_config_liquibase, 'w', encoding='UTF-8') as file:
        config_file.write(file)
    
    return path_config_liquibase




def remover_configuracoes_liquibase(path_config_liquibase: str):
    """Remove o arquivo temporário de configuração do Liquibase"""
    if os.path.exists(path_config_liquibase):
        try:
            os.remove(path_config_liquibase)
        except Exception as e:
            print(f"Erro ao remover configuração do Liquibase: {e}")