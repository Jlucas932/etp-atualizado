import os
import logging
import re
from typing import Optional
from dotenv import load_dotenv

# Load environment variables before any other imports
load_dotenv()

# Diretório de logs configurável e consistente com o container
LOG_DIR = os.getenv('LOG_DIR', '/opt/az/logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

def validate_environment_variables():
    """Valida variáveis de ambiente obrigatórias (multi-SGBD compatível)"""
    required_vars = {
        'OPENAI_API_KEY': 'Chave da API OpenAI é obrigatória',
        'SECRET_KEY': 'Chave secreta do Flask é obrigatória',
        'DATABASE_URL': 'URL do banco de dados é obrigatória',
        'EMBEDDINGS_PROVIDER': 'Provedor de embeddings é obrigatório',
    }
    
    missing_vars = []
    for var, message in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var}: {message}")
    
    if missing_vars:
        raise ValueError("Variáveis de ambiente faltando:\n" + "\n".join(missing_vars))

    if not os.getenv('RAG_FAISS_PATH'):
        logging.info("ℹ️  RAG_FAISS_PATH não definido — fallback BM25 habilitado.")

    logging.info("✅ Configuração validada — DB e embeddings OK.")
    
def get_config_values():
    """Retorna valores de configuração validados (multi-SGBD compatível)"""
    return {
        'db_vendor': os.getenv('DB_VENDOR', 'postgresql'),
        'database_url': os.environ['DATABASE_URL'],
        'embeddings_provider': os.getenv('EMBEDDINGS_PROVIDER', 'openai'),
        'lexml_timeout': int(os.getenv('LEXML_TIMEOUT_SECONDS', '8')),
        'rag_topk': int(os.getenv('RAG_TOPK', '5')),
        'rag_faiss_path': os.getenv('RAG_FAISS_PATH'),
        'legal_cache_ttl': int(os.getenv('LEGAL_CACHE_TTL_DAYS', '7')),
        'rate_limit_per_minute': int(os.getenv('RATE_LIMIT_PER_MINUTE', '30')),
    }

from flask import Flask, send_from_directory, request, Response
from flask_cors import CORS
from application.config.LimiterConfig import limiter
from domain.interfaces.dataprovider.DatabaseConfig import init_database, db
from domain.dto.KbDto import KbDocument, KbChunk
from domain.usecase.utils.security_utils import mask_database_url
from rag.ingest_etps import ETPIngestor
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


def _coerce_positive_int(value: Optional[str], default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _parse_max_content_length(raw_value: Optional[str]) -> int:
    """Converte MAX_CONTENT_LENGTH para bytes aplicando heurísticas de MB."""
    default_bytes = 16 * 1024 * 1024

    if not raw_value:
        return default_bytes

    value = raw_value.strip().lower()
    multiplier = 1

    suffix_match = re.match(r"^(?P<number>[0-9]+(?:\.[0-9]+)?)(?P<unit>[a-z]*)$", value)
    if suffix_match:
        number = suffix_match.group('number')
        unit = suffix_match.group('unit')
    else:
        number = value
        unit = ''

    try:
        numeric_value = float(number)
    except ValueError:
        logging.warning(
            "Valor inválido para MAX_CONTENT_LENGTH='%s'. Aplicando padrão de 16MB.",
            raw_value,
        )
        return default_bytes

    if unit in ('mb', 'mib', 'm'):
        multiplier = 1024 * 1024
    elif unit in ('kb', 'kib', 'k'):
        multiplier = 1024
    elif unit in ('bytes', 'byte', 'b', ''):
        multiplier = 1
    else:
        logging.warning(
            "Unidade '%s' inválida para MAX_CONTENT_LENGTH. Interpretando como MB.",
            unit,
        )
        multiplier = 1024 * 1024

    bytes_value = int(numeric_value * multiplier)

    # Heurística: valores pequenos são MB
    if multiplier == 1 and bytes_value < 1024:
        bytes_value *= 1024 * 1024

    return bytes_value if bytes_value > 0 else default_bytes

def auto_load_knowledge_base():
    """
    Verifica se a base de conhecimento está vazia e executa a ingestão automaticamente se necessário.
    Esta função deve ser chamada após a inicialização do banco de dados.
    """
    try:
        if not os.path.exists("knowledge/etps/parsed"):
            logging.warning("📁 Diretório 'knowledge/etps/parsed' não encontrado — auto_load_knowledge_base ignorado.")
            return False

        # Verificar se existem documentos na base
        document_count = db.session.query(KbDocument).count()
        chunk_count = db.session.query(KbChunk).count()
        
        if document_count > 0:
            # Base já populada
            logging.info(
                "📚 Base de conhecimento já populada com %s documentos e %s chunks",
                document_count,
                chunk_count,
            )
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
            logging.info(
                "✅ Ingestão concluída: %s documentos / %s chunks",
                final_document_count,
                final_chunk_count,
            )
            return True
        else:
            logging.error("❌ Erro na ingestão automática")
            return False

    except Exception as e:
        logging.error("❌ Erro verificando/carregando base de conhecimento: %s", e)
        return False

def create_api():
    """Cria e configura a aplicação Flask"""
    
    # Configurar logging seguro (sem chaves de API)
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    root_logger = logging.getLogger()

    if not root_logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(LOG_FILE, mode='a')
        file_handler.setFormatter(formatter)

        root_logger.addHandler(stream_handler)
        root_logger.addHandler(file_handler)

    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Validar variáveis de ambiente obrigatórias
    validate_environment_variables()
    
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
    
    logging.debug("📁 Pasta static configurada: %s", static_path)
    logging.debug("📁 Pasta templates configurada: %s", template_path)
    logging.debug("📄 Verificando index.html: %s", os.path.exists(os.path.join(static_path, 'index.html')))
    
    # Inicialização do app Flask
    app = Flask(__name__, static_folder=static_path, template_folder=template_path)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')
    
    # Configurar CORS via variável de ambiente (só se CORS_ORIGINS estiver definido)
    cors_origins = os.getenv('CORS_ORIGINS')
    if cors_origins:
        if cors_origins == '*':
            # Modo permissivo (desenvolvimento)
            logging.warning("⚠️  CORS configurado para aceitar todas as origens (*) - NÃO recomendado para produção!")
            CORS(
                app,
                origins="*",
                supports_credentials=True,
                allow_headers=['Content-Type', 'Authorization'],
                methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            )
        else:
            # Modo restritivo (produção)
            # Formato: "https://app.example.com,https://admin.example.com"
            origins_list = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]
            logging.info("✅ CORS configurado para origens específicas: %s", origins_list)
            CORS(
                app,
                origins=origins_list,
                supports_credentials=True,
                allow_headers=['Content-Type', 'Authorization'],
                methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            )
    else:
        logging.info("ℹ️  CORS não configurado (CORS_ORIGINS não definido)")
    
    # Configurar limites de upload via variável de ambiente (MB -> bytes automaticamente)
    raw_max_content_length = os.getenv('MAX_CONTENT_LENGTH', '16')
    max_content_bytes = _parse_max_content_length(raw_max_content_length)
    max_content_mb = max_content_bytes / (1024 * 1024)
    logging.info(
        "✅ Limite de upload configurado: %s (%0.1f MB)",
        f"{max_content_bytes} bytes",
        max_content_mb,
    )
    app.config['MAX_CONTENT_LENGTH'] = max_content_bytes

    # SQLAlchemy configs
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    pool_size = _coerce_positive_int(os.getenv('DB_POOL_SIZE'), 5)
    max_overflow = _coerce_positive_int(os.getenv('DB_MAX_OVERFLOW'), 10)
    pool_recycle = _coerce_positive_int(os.getenv('DB_POOL_RECYCLE'), 3600)
    engine_options = {
        'pool_pre_ping': True,
        'future': True,
        'pool_size': pool_size,
        'max_overflow': max_overflow,
        'pool_recycle': pool_recycle,
    }
    # Merge com opções já existentes para evitar sobrescrever configurações definidas em init_database
    existing_engine_options = app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
    existing_engine_options.update(engine_options)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = existing_engine_options

    database_url = os.getenv('DATABASE_URL')
    if database_url:
        logging.info("✅ DATABASE_URL configurada: %s", mask_database_url(database_url))
    
    # Configurar banco de dados
    init_database(app, basedir)
    
    # Ingestão automática opcional
    if os.getenv('AUTO_INGEST_ON_BOOT', 'false').lower() == 'true':
        with app.app_context():
            auto_load_knowledge_base()
    else:
        logging.info("AUTO_INGEST_ON_BOOT desabilitado — pulando ingestão inicial.")
    
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
    
    # Endpoint /metrics para Prometheus (protegido por token) + hooks
    enable_metrics = os.getenv('ENABLE_METRICS', 'true').strip().lower() == 'true'
    if PROMETHEUS_AVAILABLE and enable_metrics:
        @app.route('/metrics')
        def metrics():
            metrics_token = os.getenv('METRICS_TOKEN')
            if not metrics_token:
                if os.getenv("FLASK_ENV", "").lower() == "development" or os.getenv("DEBUG", "0").lower() in {"1", "true", "yes"}:
                    metrics_token = "dev_default_token"
                    logging.warning("⚠️ METRICS_TOKEN não definido — usando token temporário 'dev_default_token' em ambiente de desenvolvimento.")
                else:
                    logging.error("METRICS_TOKEN não configurado - negando acesso ao /metrics (produção)")
                    return {"error": "METRICS token not configured"}, 503

            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return {"error": "Unauthorized"}, 401

            token = auth_header[7:]
            if token != metrics_token:
                return {"error": "Unauthorized"}, 401

            return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

        @app.before_request
        def _metrics_before_request():
            request._start_time = time.time()

        @app.after_request
        def _metrics_after_request(response):
            if hasattr(request, '_start_time'):
                duration = time.time() - request._start_time
                endpoint = request.endpoint or request.path or 'unknown'
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

        logging.info("✅ Métricas Prometheus habilitadas.")
    else:
        if not PROMETHEUS_AVAILABLE:
            logging.info("ℹ️ Métricas desabilitadas: pacote prometheus_client não instalado.")
        elif not enable_metrics:
            logging.info("ℹ️ Métricas desabilitadas por ENABLE_METRICS=false.")
    
    # Servir arquivos estáticos
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        static_folder_path = app.static_folder
        
        logging.debug("🔍 Tentando servir: %s", path)
        logging.debug("📁 Static folder: %s", static_folder_path)
        
        if static_folder_path is None:
            return "Static folder not configured", 404

        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            logging.debug("✅ Arquivo encontrado: %s", path)
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, 'index.html')
            logging.debug("🔍 Procurando index.html em: %s", index_path)
            logging.debug("📄 Index.html existe: %s", os.path.exists(index_path))

            if os.path.exists(index_path):
                logging.debug("✅ Servindo index.html")
                return send_from_directory(static_folder_path, 'index.html')
            else:
                # Listar arquivos na pasta static para debug
                if os.path.exists(static_folder_path):
                    files = os.listdir(static_folder_path)
                    logging.debug("📂 Arquivos na pasta static: %s", files)
                else:
                    logging.warning("❌ Pasta static não existe!")

                return f"index.html not found. Static folder: {static_folder_path}", 404

    return app
