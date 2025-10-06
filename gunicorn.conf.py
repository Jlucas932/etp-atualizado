"""
Configuração do Gunicorn para AutoDocIA v2.0

Referências:
- https://docs.gunicorn.org/en/stable/settings.html
- https://docs.gunicorn.org/en/stable/design.html
"""

import os
import multiprocessing

# ----------------------------------------------------------------------------
# BIND
# ----------------------------------------------------------------------------
# Host e porta (lê de ENV ou usa padrão)
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '5002')}"

# ----------------------------------------------------------------------------
# WORKERS
# ----------------------------------------------------------------------------
# Número de workers (processos)
# Fórmula recomendada: (2 x CPU cores) + 1
# Pode ser sobrescrito por GUNICORN_WORKERS
workers = int(os.getenv('GUNICORN_WORKERS', (multiprocessing.cpu_count() * 2) + 1))

# Tipo de worker
# - sync: Padrão, bloqueante (bom para CPU-bound)
# - gevent/eventlet: Assíncrono (bom para I/O-bound, requer instalação)
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'sync')

# Threads por worker (apenas para worker_class=gthread)
threads = int(os.getenv('GUNICORN_THREADS', '1'))

# ----------------------------------------------------------------------------
# TIMEOUTS
# ----------------------------------------------------------------------------
# Timeout de requisição (segundos)
# Requisições que demoram mais que isso são abortadas
# Aumentar para operações pesadas (geração de ETP, RAG)
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))

# Graceful timeout (tempo para worker terminar após SIGTERM)
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', '30'))

# Keep-alive (segundos)
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '5'))

# ----------------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------------
# Nível de log
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')

# Arquivo de log de acesso (None = stdout)
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '-')  # '-' = stdout

# Arquivo de log de erros (None = stderr)
errorlog = os.getenv('GUNICORN_ERROR_LOG', '-')  # '-' = stderr

# Formato de log de acesso
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# ----------------------------------------------------------------------------
# SEGURANÇA
# ----------------------------------------------------------------------------
# Limitar tamanho de header (evita ataques)
limit_request_line = int(os.getenv('GUNICORN_LIMIT_REQUEST_LINE', '4096'))
limit_request_fields = int(os.getenv('GUNICORN_LIMIT_REQUEST_FIELDS', '100'))
limit_request_field_size = int(os.getenv('GUNICORN_LIMIT_REQUEST_FIELD_SIZE', '8190'))

# ----------------------------------------------------------------------------
# PERFORMANCE
# ----------------------------------------------------------------------------
# Número máximo de requisições por worker antes de reiniciar
# Previne memory leaks
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', '50'))

# Preload app (carrega app antes de fork workers)
# Economiza memória mas dificulta reload
preload_app = os.getenv('GUNICORN_PRELOAD_APP', 'false').lower() in ('true', '1', 'yes')

# ----------------------------------------------------------------------------
# PROCESS NAMING
# ----------------------------------------------------------------------------
proc_name = 'autodoc-ia'

# ----------------------------------------------------------------------------
# HOOKS
# ----------------------------------------------------------------------------
def on_starting(server):
    """Chamado quando Gunicorn inicia"""
    server.log.info("=" * 60)
    server.log.info("AutoDocIA v2.0 - Gunicorn iniciando")
    server.log.info(f"Workers: {workers} | Timeout: {timeout}s | Bind: {bind}")
    server.log.info("=" * 60)

def on_reload(server):
    """Chamado quando Gunicorn recarrega"""
    server.log.info("Gunicorn recarregado")

def worker_int(worker):
    """Chamado quando worker recebe SIGINT"""
    worker.log.info(f"Worker {worker.pid} interrompido por usuário")

def worker_abort(worker):
    """Chamado quando worker aborta (timeout)"""
    worker.log.warning(f"Worker {worker.pid} abortado (timeout de {timeout}s excedido)")

def post_fork(server, worker):
    """Chamado após fork de worker"""
    server.log.info(f"Worker {worker.pid} spawned")

def pre_exec(server):
    """Chamado antes de exec (reload)"""
    server.log.info("Gunicorn preparando para reload")

def when_ready(server):
    """Chamado quando servidor está pronto para aceitar conexões"""
    server.log.info("✅ Gunicorn pronto para aceitar conexões")
