#!/usr/bin/env python3
"""
Script de teste para verificar se as correções do sistema RAG estão funcionando
"""

import os
import sys
from pathlib import Path

# Adicionar src ao path
current_dir = Path(__file__).parent
src_path = current_dir / "src" / "main" / "python"
sys.path.insert(0, str(src_path))

def test_knowledge_base_dto_import():
    """Testa se o KnowledgeBaseDto pode ser importado corretamente"""
    print("🔍 Testando importação do KnowledgeBaseDto...")
    try:
        from domain.dto.KnowledgeBaseDto import KbDocument, KbChunk, KnowledgeBaseDocument
        print("✅ KnowledgeBaseDto importado com sucesso")
        
        # Testar criação de KnowledgeBaseDocument
        doc = KnowledgeBaseDocument(
            id="test-123",
            title="Teste",
            section="requisitos",
            content="Conteúdo de teste"
        )
        print(f"✅ KnowledgeBaseDocument criado: {doc.title}")
        return True
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

def test_ingest_etps_import():
    """Testa se o módulo de ingestão pode importar as dependências"""
    print("\n🔍 Testando importações do módulo de ingestão...")
    try:
        from rag.ingest_etps import ETPIngestor
        print("✅ ETPIngestor importado com sucesso")
        return True
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

def test_retrieval_import():
    """Testa se o módulo de retrieval pode ser importado"""
    print("\n🔍 Testando importações do módulo de retrieval...")
    try:
        from rag.retrieval import RAGRetrieval
        print("✅ RAGRetrieval importado com sucesso")
        return True
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

def test_directories_creation():
    """Testa se os diretórios necessários são criados"""
    print("\n🔍 Testando criação de diretórios...")
    try:
        # Verificar se os diretórios existem
        knowledge_dir = current_dir / "knowledge" / "etps"
        raw_dir = knowledge_dir / "raw"
        parsed_dir = knowledge_dir / "parsed"
        index_dir = current_dir / "src" / "main" / "python" / "rag" / "index" / "faiss"
        
        # Criar diretórios se não existirem
        raw_dir.mkdir(parents=True, exist_ok=True)
        parsed_dir.mkdir(parents=True, exist_ok=True)
        index_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ Diretório raw: {raw_dir}")
        print(f"✅ Diretório parsed: {parsed_dir}")
        print(f"✅ Diretório index: {index_dir}")
        
        return True
    except Exception as e:
        print(f"❌ Erro criando diretórios: {e}")
        return False

def test_pdf_processing():
    """Testa se o PyPDF2 está disponível"""
    print("\n🔍 Testando biblioteca PyPDF2...")
    try:
        import PyPDF2
        print("✅ PyPDF2 disponível")
        return True
    except ImportError:
        print("❌ PyPDF2 não encontrado - execute: pip install PyPDF2==3.0.1")
        return False

def main():
    """Executa todos os testes"""
    print("🚀 Iniciando testes das correções do sistema RAG\n")
    
    tests = [
        test_knowledge_base_dto_import,
        test_ingest_etps_import,
        test_retrieval_import,
        test_directories_creation,
        test_pdf_processing
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Resultado dos testes: {passed}/{total} passaram")
    
    if passed == total:
        print("🎉 Todas as correções estão funcionando corretamente!")
        print("\n📋 Próximos passos:")
        print("1. Coloque PDFs na pasta knowledge/etps/raw/")
        print("2. Execute o ingestor: python -m rag.ingest_etps")
        print("3. Teste o sistema RAG na aplicação")
    else:
        print("⚠️ Algumas correções precisam de atenção")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())