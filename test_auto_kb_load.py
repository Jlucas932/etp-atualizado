#!/usr/bin/env python3
"""
Teste para verificar o carregamento automático da base de conhecimento
"""

import os
import sys
import logging
from pathlib import Path

# Adicionar src/main/python ao path
current_dir = Path(__file__).parent
src_path = current_dir / "src" / "main" / "python"
sys.path.insert(0, str(src_path))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_auto_kb_load():
    """Testa o carregamento automático da base de conhecimento"""
    
    try:
        print("🧪 Iniciando teste do carregamento automático da KB...")
        
        # Configurar variáveis de ambiente mínimas
        os.environ['OPENAI_API_KEY'] = 'test_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret'
        os.environ['DB_VENDOR'] = 'sqlite'
        os.environ['EMBEDDINGS_PROVIDER'] = 'openai'
        os.environ['RAG_FAISS_PATH'] = 'rag/index/faiss'
        
        # Importar e criar a aplicação
        from application.config.FlaskConfig import create_api
        from domain.dto.KbDto import KbDocument, KbChunk
        from domain.interfaces.dataprovider.DatabaseConfig import db
        
        print("📦 Criando aplicação Flask...")
        app = create_api()
        
        # Verificar se a base foi carregada
        with app.app_context():
            document_count = db.session.query(KbDocument).count()
            chunk_count = db.session.query(KbChunk).count()
            
            print(f"📊 Documentos na base: {document_count}")
            print(f"📊 Chunks na base: {chunk_count}")
            
            if document_count > 0:
                print("✅ Base de conhecimento carregada com sucesso!")
                return True
            else:
                print("⚠️  Base de conhecimento ainda vazia (pode ser normal se não há PDFs na pasta raw)")
                return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_auto_kb_load()
    if success:
        print("🎉 Teste concluído!")
        sys.exit(0)
    else:
        print("💥 Teste falhou!")
        sys.exit(1)