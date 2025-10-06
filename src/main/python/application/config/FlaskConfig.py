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

from flask import Flask, send_from_directory, request, Response
from flask_cors import CORS
from application.config.LimiterConfig import limiter
from domain.interfaces.dataprovider.DatabaseConfig import init_database, db
from domain.dto.KnowledgeBaseDto import KbDocument, KbChunk
from rag.ingest_etps import ETPIngestor
from pathlib import Path
import time

# Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
    
    # Métricas
    http_requests_total = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )
    http_request_duration_seconds = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint']
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("⚠️  prometheus_client não instalado - métricas desabilitadas")

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
    
    # Inicialização do app Flask
    app = Flask(__name__, static_folder=static_path, template_folder=template_path)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')
    
    # Configurar CORS via variável de ambiente (só se CORS_ORIGINS estiver definido)
    cors_origins = os.getenv('CORS_ORIGINS')
    if cors_origins:
        if cors_origins == '*':
            # Modo permissivo (desenvolvimento)
            logging.warning("⚠️  CORS configurado para aceitar todas as origens (*) - NÃO recomendado para produção!")
            CORS(app, origins="*", supports_credentials=True)
        else:
            # Modo restritivo (produção)
            # Formato: "https://app.example.com,https://admin.example.com"
            origins_list = [origin.strip() for origin in cors_origins.split(',')]
            logging.info(f"✅ CORS configurado para origens específicas: {origins_list}")
            CORS(app, 
                 origins=origins_list,
                 supports_credentials=True,
                 allow_headers=['Content-Type', 'Authorization'],
                 methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    else:
        logging.info("ℹ️  CORS não configurado (CORS_ORIGINS não definido)")
    
    # Configurar limites de upload via variável de ambiente
    # Se MAX_CONTENT_LENGTH vier em MB, converter para bytes
    # Se vier em bytes (>1024), usar direto
    max_content_length_str = os.getenv('MAX_CONTENT_LENGTH', '16')
    max_content_length_int = int(max_content_length_str)
    
    if max_content_length_int < 1024:
        # Valor em MB, converter para bytes
        max_content_bytes = max_content_length_int * 1024 * 1024
        logging.info(f"✅ Limite de upload configurado: {max_content_length_int} MB ({max_content_bytes} bytes)")
    else:
        # Valor já em bytes
        max_content_bytes = max_content_length_int
        max_content_mb = max_content_bytes / (1024 * 1024)
        logging.info(f"✅ Limite de upload configurado: {max_content_bytes} bytes ({max_content_mb:.1f} MB)")
    
    app.config['MAX_CONTENT_LENGTH'] = max_content_bytes
    
    # Configurar banco de dados
    init_database(app, basedir)
    
    # Carregar base de conhecimento automaticamente se necessário
    with app.app_context():
        auto_load_knowledge_base()
    
    # Inicializar rate limiting
    limiter.init_app(app)
    
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
    
    # Endpoint /metrics para Prometheus (protegido por token)
    @app.route('/metrics')
    def metrics():
        if not PROMETHEUS_AVAILABLE:
            return {"error": "Prometheus metrics not available"}, 503
        
        # Verificar token de autorização
        auth_header = request.headers.get('Authorization', '')
        expected_token = os.getenv('METRICS_TOKEN')
        
        if not expected_token:
            return {"error": "METRICS_TOKEN not configured"}, 500
        
        if not auth_header.startswith('Bearer '):
            return {"error": "Unauthorized - Bearer token required"}, 401
        
        token = auth_header[7:]  # Remove "Bearer "
        if token != expected_token:
            return {"error": "Unauthorized - Invalid token"}, 401
        
        # Retornar métricas
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
    
    # Hooks para coletar métricas
    if PROMETHEUS_AVAILABLE:
        @app.before_request
        def before_request_metrics():
            request._start_time = time.time()
        
        @app.after_request
        def after_request_metrics(response):
            if hasattr(request, '_start_time'):
                duration = time.time() - request._start_time
                endpoint = request.endpoint or 'unknown'
                
                # Registrar métricas
                http_requests_total.labels(
                    method=request.method,
                    endpoint=endpoint,
                    status=response.status_code
                ).inc()
                
                http_request_duration_seconds.labels(
                    method=request.method,
                    endpoint=endpoint
                ).observe(duration)
            
            return response
    
    # Servir arquivos estáticos
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
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