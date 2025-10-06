#!/bin/bash

# Script de inicialização do AZ ETP Fácil - Versão Completa
echo "🚀 Iniciando AZ ETP Fácil..."
echo ""

# Verificar se arquivo .env existe
if [ ! -f .env ]; then
    echo "⚠️  Arquivo .env não encontrado. Copiando de .env.example..."
    cp .env.example .env
    echo "✅ Arquivo .env criado. Configure sua OPENAI_API_KEY no arquivo .env"
    echo ""
fi

# Verificar se Docker está disponível
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "🐘 Docker encontrado. Tentando iniciar PostgreSQL..."
    
    # Tentar iniciar PostgreSQL
    if docker-compose up -d postgres 2>/dev/null; then
        echo "✅ PostgreSQL iniciado com sucesso!"
        echo "⏳ Aguardando PostgreSQL ficar pronto..."
        sleep 5
    else
        echo "❌ ERRO: Não foi possível iniciar PostgreSQL. PostgreSQL é obrigatório."
        echo "   Configure o Docker e PostgreSQL antes de continuar."
        exit 1
    fi
else
    echo "❌ ERRO: Docker não encontrado. PostgreSQL é obrigatório."
    echo "   Instale Docker e Docker Compose antes de continuar."
    exit 1
fi

# Instalar dependências se necessário
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
fi

echo "🔧 Instalando dependências..."
source venv/bin/activate 2>/dev/null || echo "Usando Python global"
pip install -r requirements.txt

# Verificar configuração da API
if grep -q "sua_api_key_aqui" .env 2>/dev/null; then
    echo ""
    echo "⚠️  ATENÇÃO: Configure sua OPENAI_API_KEY no arquivo .env!"
    echo ""
fi

# Iniciar aplicação
echo "🎯 Iniciando aplicação..."
echo "📍 Acesse: http://localhost:5002"
echo "🔄 Para parar: Ctrl+C"
echo ""

python src/main/python/applicationApi.py

