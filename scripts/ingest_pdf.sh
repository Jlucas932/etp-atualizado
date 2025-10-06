#!/bin/bash

# Script para ingestão de arquivos PDF

INPUT_DIR="./knowledge/etps/raw"

if [ ! -d "$INPUT_DIR" ]; then
  echo "Diretório de entrada $INPUT_DIR não encontrado."
  exit 1
fi

# A lógica de ingestão de PDF já está no ingest_etps.py, 
# então este script pode simplesmente chamar o processo principal de ingestão.

echo "Iniciando ingestão de PDFs..."
python3 -m src.main.python.rag.ingest_etps --rebuild

echo "Ingestão de PDF concluída."

