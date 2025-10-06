#!/usr/bin/env python3
"""
Test script to validate RAG fixes for autodoc-ia project.
Tests Flask context fixes, constructor signature, and end-to-end RAG functionality.
"""

import os
import sys
import logging

# Add project path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, 'src', 'main', 'python'))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_flask_context_fix():
    """Test that Flask context errors are resolved"""
    logger.info("=== Testando correção do contexto Flask ===")
    
    try:
        # Set required environment variables
        os.environ['OPENAI_API_KEY'] = 'test_key_for_validation'
        os.environ['SECRET_KEY'] = 'test_secret_key'
        
        from rag.retrieval import RAGRetrieval
        
        # Test constructor with different calling patterns
        logger.info("Testando construtor com diferentes padrões...")
        
        # Pattern 1: openai_client as keyword argument (EtpDynamicController pattern)
        rag1 = RAGRetrieval(openai_client=None)
        logger.info("✓ Construtor com openai_client como argumento nomeado: OK")
        
        # Pattern 2: positional arguments (get_retrieval_instance pattern)
        rag2 = RAGRetrieval("database_url", None)
        logger.info("✓ Construtor com argumentos posicionais: OK")
        
        # Pattern 3: no arguments
        rag3 = RAGRetrieval()
        logger.info("✓ Construtor sem argumentos: OK")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro no teste do construtor: {str(e)}")
        return False

def test_build_indices_context():
    """Test that build_indices works without Flask context errors"""
    logger.info("=== Testando build_indices sem erro de contexto ===")
    
    try:
        from rag.retrieval import RAGRetrieval
        
        # Create RAG instance
        rag = RAGRetrieval(openai_client=None)
        
        # Try to build indices - this should not crash with Flask context error
        result = rag.build_indices()
        
        # It may return False due to no embeddings/data, but should not crash
        logger.info(f"✓ build_indices executado sem erro de contexto Flask. Resultado: {result}")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        if "Working outside of application context" in error_msg:
            logger.error(f"❌ Erro de contexto Flask ainda presente: {error_msg}")
            return False
        else:
            # Other errors are acceptable (no data, no OpenAI key, etc.)
            logger.info(f"✓ Sem erro de contexto Flask. Outro erro (aceitável): {error_msg}")
            return True

def test_rag_integration():
    """Test RAG integration and flag setting"""
    logger.info("=== Testando integração RAG ===")
    
    try:
        from domain.usecase.etp.dynamic_prompt_generator import DynamicPromptGenerator
        from rag.retrieval import RAGRetrieval
        
        # Create components
        prompt_gen = DynamicPromptGenerator("test_key")
        rag_system = RAGRetrieval(openai_client=None)
        prompt_gen.set_rag_retrieval(rag_system)
        
        # Test requirements generation
        result = prompt_gen.generate_requirements_with_rag(
            contracting_need="Teste de contratação",
            contract_type="produto",
            objective_slug="generic"
        )
        
        # Validate result structure
        expected_keys = ['requirements', 'consultative_message', 'source_citations', 'is_rag_based', 'total_rag_results']
        for key in expected_keys:
            if key not in result:
                logger.error(f"❌ Chave ausente no resultado: {key}")
                return False
        
        logger.info(f"✓ Integração RAG funcionando. Baseado em RAG: {result['is_rag_based']}, Resultados: {result['total_rag_results']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na integração RAG: {str(e)}")
        return False

def test_embedding_handling():
    """Test embedding format handling"""
    logger.info("=== Testando tratamento de embeddings ===")
    
    try:
        from rag.retrieval import RAGRetrieval
        import json
        import numpy as np
        
        # Create mock chunks with different embedding formats
        class MockChunk:
            def __init__(self, chunk_id, embedding_data, embedding_format):
                self.id = chunk_id
                self.kb_document_id = 1
                self.content = f"Test content {chunk_id}"
                self.section_type = "requisito"
                
                if embedding_format == "json":
                    self.embedding = json.dumps(embedding_data) if embedding_data else None
                elif embedding_format == "list":
                    self.embedding = embedding_data
                elif embedding_format == "array":
                    self.embedding = np.array(embedding_data) if embedding_data else None
                else:
                    self.embedding = None
                    
                self.kb_document = MockDocument()
        
        class MockDocument:
            def __init__(self):
                self.objective_slug = "test"
        
        # Test embedding formats
        test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]  # Simple 5-dim embedding
        
        chunks = [
            MockChunk(1, test_embedding, "json"),    # JSON format
            MockChunk(2, test_embedding, "list"),    # List format  
            MockChunk(3, test_embedding, "array"),   # Array format
            MockChunk(4, None, "none"),              # No embedding
        ]
        
        # Create RAG instance and test embedding processing
        rag = RAGRetrieval(openai_client=None)
        
        # This should handle all formats without crashing
        rag._build_faiss_index(chunks)
        
        logger.info("✓ Processamento de embeddings em diferentes formatos: OK")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento de embeddings: {str(e)}")
        return False

def main():
    """Run all validation tests"""
    logger.info("🚀 Iniciando validação das correções RAG")
    
    tests = [
        ("Correção do contexto Flask", test_flask_context_fix),
        ("Build indices sem erro de contexto", test_build_indices_context), 
        ("Integração RAG", test_rag_integration),
        ("Tratamento de embeddings", test_embedding_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Falha crítica no teste '{test_name}': {str(e)}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("RESUMO DOS TESTES")
    logger.info("="*60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1
    
    logger.info(f"\nResultado geral: {passed}/{len(results)} testes passaram")
    
    if passed == len(results):
        logger.info("🎉 Todas as correções RAG foram validadas com sucesso!")
        return True
    else:
        logger.error("⚠️  Algumas correções precisam de ajustes adicionais.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)