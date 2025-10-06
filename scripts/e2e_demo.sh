#!/bin/bash

# Script para demonstração de ponta a ponta

echo "Iniciando demonstração de ponta a ponta..."

# 1. Iniciar os serviços (simulado)
echo "(Simulado) Subindo contêineres com docker-compose up..."

# 2. Ingestão de dados
make ingest_pdf

# 3. Construção dos índices
make build_indexes

# 4. Execução dos testes
make test

# 5. Simulação de uma conversa
echo "\n--- Iniciando simulação de conversa ---"

# Simulação de uma necessidade
NECESSITY="uma empresa especializada em gestão de frota de aeronaves"
echo "Usuário: $NECESSITY"

# A API seria chamada aqui. Como não temos um servidor rodando, vamos simular a saída.
echo "Sistema: Perfeito! Identifiquei sua necessidade: **$NECESSITY**..."

echo "\nDemonstração de ponta a ponta concluída."

