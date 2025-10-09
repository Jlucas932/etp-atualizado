# Imagem base estável (mais suporte a libs científicas do que Alpine)
FROM python:3.12-slim

# Evita cache de bytecode e garante logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instala dependências do sistema necessárias para psycopg2, numpy, faiss, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    python3-dev \
    curl \
    tini \
 && rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /opt/az

# Copia requirements primeiro para aproveitar cache de build
COPY requirements.txt .

# Atualiza pip e instala dependências do Python
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copia o restante do projeto
COPY . .

# Porta exposta pelo app
EXPOSE 5002

# EntryPoint seguro com tini (mata processos zumbis)
ENTRYPOINT ["/usr/bin/tini", "--"]

# Comando padrão para rodar a aplicação
CMD ["python", "src/main/python/applicationApi.py"]
