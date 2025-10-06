# ============================================================================
# DOCKERFILE MULTI-STAGE - AutoDocIA v2.0
# ============================================================================
# Stage 1: Builder - Compila dependências pesadas
# Stage 2: Runtime - Imagem final enxuta apenas com o necessário
# ============================================================================

# ----------------------------------------------------------------------------
# STAGE 1: BUILDER
# ----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Evita cache de bytecode
ENV PYTHONDONTWRITEBYTECODE=1

# Instala dependências de compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /build

# Copia requirements
COPY requirements.txt .

# Instala dependências em /build/venv
RUN python -m venv /build/venv \
 && /build/venv/bin/pip install --upgrade pip setuptools wheel \
 && /build/venv/bin/pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------------------------------
# STAGE 2: RUNTIME
# ----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Variáveis de ambiente para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Instala apenas dependências de runtime (não compiladores)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmariadb3 \
    unixodbc \
    curl \
    tini \
 && rm -rf /var/lib/apt/lists/*

# Cria usuário não-root para segurança
RUN useradd -m -u 1000 -s /bin/bash appuser \
 && mkdir -p /opt/az /opt/az/logs /opt/az/data /opt/az/rag/index \
 && chown -R appuser:appuser /opt/az

# Copia venv do builder
COPY --from=builder --chown=appuser:appuser /build/venv /opt/venv

# Define diretório de trabalho
WORKDIR /opt/az

# Copia código da aplicação
COPY --chown=appuser:appuser . .

# Muda para usuário não-root
USER appuser

# Porta exposta
EXPOSE 5002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5002/api/health || exit 1

# EntryPoint com tini (gerenciamento de processos)
ENTRYPOINT ["/usr/bin/tini", "--"]

# Comando padrão: gunicorn em produção
# Para desenvolvimento, sobrescreva com: docker run ... python src/main/python/applicationApi.py
CMD ["gunicorn", \
     "--config", "gunicorn.conf.py", \
     "--bind", "0.0.0.0:5002", \
     "src.main.python.applicationApi:app"]
