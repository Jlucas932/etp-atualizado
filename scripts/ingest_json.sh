#!/bin/bash

# Script para ingestão de arquivos JSON

INPUT_DIR="./data/json"

if [ ! -d "$INPUT_DIR" ]; then
  echo "Diretório de entrada $INPUT_DIR não encontrado."
  exit 1
fi

for json_file in "$INPUT_DIR"/*.json; do
  echo "Processando $json_file..."
  # Adicione aqui a lógica para processar cada arquivo JSON.
  # Exemplo: python3 scripts/process_json.py "$json_file"
done

echo "Ingestão de JSON concluída."

