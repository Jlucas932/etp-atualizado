#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Adicionar src/main/python ao path para imports
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.main.python.rag.ingest_etps import ETPIngestor

def main():
    """Função principal para construir os índices."""
    print("Iniciando a construção dos índices...")
    
    # A construção dos índices já é feita no final da ingestão.
    # Apenas para garantir, vamos instanciar o ingestor e chamar um método que 
    # possa no futuro conter a lógica de reconstrução de índice separadamente.
    ingestor = ETPIngestor()
    ingestor.ingest_pdfs_and_jsonl(rebuild=False) # Não reconstruir, apenas garantir que os índices existam.

    print("Construção dos índices concluída.")

if __name__ == "__main__":
    main()

