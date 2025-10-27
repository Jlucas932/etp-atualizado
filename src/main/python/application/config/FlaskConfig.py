import os
import logging
from dotenv import load_dotenv

# Load environment variables before any other imports
load_dotenv()

def validate_environment_variables():
    """Valida as variáveis de ambiente obrigatórias - PostgreSQL apenas"""
    required_vars = {
        'OPENAI_API_KEY': 'Chave da API OpenAI é obrigatória',
        'SECRET_KEY': 'Chave secreta do Flask é obrigatória',
        'DATABASE_URL': 'URL do banco PostgreSQL é obrigatória',
        'EMBEDDINGS_PROVIDER': 'Provedor de embeddings é obrigatório',
        'RAG_FAISS_PATH': 'Caminho do índice FAISS é obrigatório',
    }
    
    missing_vars = []
    for var, message in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var}: {message}")
    
    if missing_vars:
        raise ValueError(f"Variáveis de ambiente faltando:\n" + "\n".join(missing_vars))
    
    # Log configuration without sensitive data
    logging.info(f"✅ Configuração validada - DB: PostgreSQL, Embeddings: {os.getenv('EMBEDDINGS_PROVIDER')}")
    
def get_config_values():
    """Retorna valores de configuração validados - PostgreSQL apenas"""
    return {
        'db_vendor': 'postgresql',  # Sempre PostgreSQL
        'database_url': os.environ['DATABASE_URL'],  # Obrigatório
        'embeddings_provider': os.getenv('EMBEDDINGS_PROVIDER', 'openai'),
        'lexml_timeout': int(os.getenv('LEXML_TIMEOUT_SECONDS', '8')),
        'rag_topk': int(os.getenv('RAG_TOPK', '5')),
        'rag_faiss_path': os.getenv('RAG_FAISS_PATH', 'rag/index/faiss'),
        'legal_cache_ttl': int(os.getenv('LEGAL_CACHE_TTL_DAYS', '7')),
        'rate_limit_per_minute': int(os.getenv('RATE_LIMIT_PER_MINUTE', '30')),
    }

from flask import Flask, send_from_directory, request, g, current_app
from flask_cors import CORS
from application.config.LimiterConfig import limiter
from domain.interfaces.dataprovider.DatabaseConfig import init_database, db
from domain.dto.KnowledgeBaseDto import KbDocument, KbChunk
from rag.ingest_etps import ETPIngestor
from pathlib import Path

def auto_load_knowledge_base():
    """
    Verifica se a base de conhecimento está vazia e executa a ingestão automaticamente se necessário.
    Esta função deve ser chamada após a inicialização do banco de dados.
    """
    try:
        # Verificar se existem documentos na base
        document_count = db.session.query(KbDocument).count()
        chunk_count = db.session.query(KbChunk).count()
        
        if document_count > 0:
            # Base já populada
            logging.info(f"📚 Base de conhecimento já populada com {document_count} documentos e {chunk_count} chunks")
            return True
        
        # Base vazia, executar ingestão automática
        logging.info("⚡ Nenhum documento encontrado, rodando ingestão inicial...")
        
        # Criar instância do ingestor e executar ingestão inicial
        ingestor = ETPIngestor()
        success = ingestor.ingest_initial_docs()
        
        if success:
            # Verificar novamente após a ingestão
            final_document_count = db.session.query(KbDocument).count()
            final_chunk_count = db.session.query(KbChunk).count()
            logging.info(f"✅ Ingestão concluída: {final_document_count} documentos / {final_chunk_count} chunks")
            return True
        else:
            logging.error(f"❌ Erro na ingestão automática")
            return False
            
    except Exception as e:
        logging.error(f"❌ Erro verificando/carregando base de conhecimento: {str(e)}")
        return False

def create_api():
    """Cria e configura a aplicação Flask"""
    
    # Validar variáveis de ambiente obrigatórias
    validate_environment_variables()
    
    # Configurar logging seguro (sem chaves de API)
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/app.log', mode='a')
        ]
    )
    
    # Caminho absoluto da pasta atual
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    # Encontrar a pasta static corretamente
    # De: src/main/python/application/config/
    # Para: static/ (na raiz do projeto)
    static_path = os.path.join(basedir, '..', '..', '..', '..', '..', 'static')
    static_path = os.path.abspath(static_path)
    
    # Encontrar a pasta templates corretamente
    # De: src/main/python/application/config/
    # Para: templates/ (na raiz do projeto)
    template_path = os.path.join(basedir, '..', '..', '..', '..', '..', 'templates')
    template_path = os.path.abspath(template_path)
    
    print(f"📁 Pasta static configurada: {static_path}")
    print(f"📁 Pasta templates configurada: {template_path}")
    print(f"📄 Verificando index.html: {os.path.exists(os.path.join(static_path, 'index.html'))}")
    
    # Criar diretório de prévias se não existir
    STATIC_PREVIEWS_DIR = os.path.join(static_path, 'previews')
    os.makedirs(STATIC_PREVIEWS_DIR, exist_ok=True)
    print(f"📁 Pasta de prévias configurada: {STATIC_PREVIEWS_DIR}")
    
    # Inicialização do app Flask
    app = Flask(__name__, static_folder=static_path, template_folder=template_path)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')
    
    # Configurar CORS para permitir requisições do frontend
    CORS(app, origins="*")
    
    # Configurar banco de dados
    init_database(app, basedir)
    
    # Carregar base de conhecimento automaticamente se necessário
    with app.app_context():
        auto_load_knowledge_base()
    
    # Inicializar rate limiting
    limiter.init_app(app)
    
    # Exempt static routes from rate limiting
    @app.before_request
    def _exempt_static_from_limiter():
        """Exempt static file routes from rate limiting to avoid 429 errors"""
        # Só GET; nada de POST/PUT etc.
        if request.method != 'GET':
            return
        path = request.path or '/'
        static_like = (
            path.startswith('/static')
            or path.startswith('/fonts')
            or path in (
                '/styles.css',
                '/script.js',
                '/requirements_renderer.js',
                '/favicon.ico',
                '/favicon_etp.ico',
                '/login.html',
            )
        )
        if static_like:
            g._rate_limiting_exempt = True
    
    @limiter.request_filter
    def _skip_if_flagged():
        """Filter to check if request should be exempt from rate limiting"""
        # Se a flag foi setada no before_request, o limiter ignora
        return bool(getattr(g, '_rate_limiting_exempt', False))
    
    # Importar blueprints só depois das extensões serem inicializadas
    from adapter.entrypoint.etp.EtpController import etp_bp
    from adapter.entrypoint.etp.EtpDynamicController import etp_dynamic_bp
    from adapter.entrypoint.user.UserController import user_bp
    from adapter.entrypoint.chat.ChatController import chat_bp
    from adapter.entrypoint.health.HealthController import health_bp
    from adapter.entrypoint.admin.AdminController import admin_bp
    from adapter.entrypoint.kb.KbController import kb_blueprint
    
    # Registrar blueprints (rotas)
    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(user_bp, url_prefix='/api')
    app.register_blueprint(etp_bp, url_prefix='/api/etp')
    app.register_blueprint(etp_dynamic_bp, url_prefix='/api/etp-dynamic')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(kb_blueprint)  # KB blueprint already has url_prefix='/api/kb' defined
    app.register_blueprint(admin_bp)  # Admin blueprint already has url_prefix='/administracao' defined
    
    # Rotas de favicon dedicadas (e isentas)
    @app.route('/favicon.ico')
    @limiter.exempt
    def favicon():
        return send_from_directory(
            current_app.static_folder, 'favicon.ico', mimetype='image/x-icon'
        )
    
    @app.route('/favicon_etp.ico')
    @limiter.exempt
    def favicon_etp():
        return send_from_directory(
            current_app.static_folder, 'favicon_etp.ico', mimetype='image/x-icon'
        )
    
    # Servir arquivos estáticos
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    @limiter.exempt
    def serve(path):
        static_folder_path = app.static_folder
        
        print(f"🔍 Tentando servir: {path}")
        print(f"📁 Static folder: {static_folder_path}")
        
        if static_folder_path is None:
            return "Static folder not configured", 404

        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            print(f"✅ Arquivo encontrado: {path}")
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, 'index.html')
            print(f"🔍 Procurando index.html em: {index_path}")
            print(f"📄 Index.html existe: {os.path.exists(index_path)}")
            
            if os.path.exists(index_path):
                print("✅ Servindo index.html")
                return send_from_directory(static_folder_path, 'index.html')
            else:
                # Listar arquivos na pasta static para debug
                if os.path.exists(static_folder_path):
                    files = os.listdir(static_folder_path)
                    print(f"📂 Arquivos na pasta static: {files}")
                else:
                    print("❌ Pasta static não existe!")
                
                return f"index.html not found. Static folder: {static_folder_path}", 404
    
    return app