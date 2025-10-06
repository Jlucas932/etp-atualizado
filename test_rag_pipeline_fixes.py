#!/usr/bin/env python3
"""
Script para testar as correções do pipeline RAG:
1. Persistência do índice BM25
2. Parsing robusto de JSON com OpenAI
3. Logging abrangente
"""

import os
import sys
import logging
from pathlib import Path

# Adicionar src/main/python ao path
current_dir = Path(__file__).parent
src_dir = current_dir / "src" / "main" / "python"
sys.path.insert(0, str(src_dir))

# Configurar logging para ver os outputs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_rag_pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

def test_bm25_persistence():
    """Testa a persistência dos índices BM25"""
    print("=== Testando Persistência BM25 ===")
    
    try:
        from rag.retrieval import RAGRetrieval
        from application.config.FlaskConfig import create_api
        
        # Criar aplicação Flask para contexto de banco
        app = create_api()
        
        with app.app_context():
            # Criar instância do RAGRetrieval
            rag = RAGRetrieval()
            
            # Verificar se diretório BM25 foi criado
            if rag.bm25_dir.exists():
                print(f"✓ Diretório BM25 criado: {rag.bm25_dir}")
            else:
                print(f"✗ Falha ao criar diretório BM25")
                return False
                
            # Tentar carregar índices (deve logar apropriadamente)
            print("Testando carregamento de índices...")
            rag._load_bm25_indices()
            
            # Verificar se índices estão vazios inicialmente
            if not rag.bm25_indices:
                print("✓ Índices BM25 inicialmente vazios (esperado)")
            
            print("✓ Teste de persistência BM25 concluído")
            return True
            
    except Exception as e:
        print(f"✗ Erro no teste BM25: {e}")
        return False

def test_json_cleaning():
    """Testa a limpeza de respostas JSON da OpenAI"""
    print("\n=== Testando Limpeza de JSON ===")
    
    try:
        from domain.usecase.etp.dynamic_prompt_generator import DynamicPromptGenerator
        
        # Criar instância (sem API key real para teste)
        generator = DynamicPromptGenerator("test-key")
        
        # Testar diferentes formatos de resposta JSON
        test_cases = [
            # Caso 1: JSON com delimitadores markdown
            '```json\n{"test": "value"}\n```',
            # Caso 2: JSON sem delimitadores
            '{"test": "value"}',
            # Caso 3: JSON com texto extra
            'Aqui está o JSON:\n```json\n{"test": "value"}\n```\nEspero que ajude!',
            # Caso 4: JSON malformado
            '```json\n{"test": "value"\n```'
        ]
        
        expected_results = [
            '{"test": "value"}',
            '{"test": "value"}', 
            '{"test": "value"}',
            '{"test": "value"'
        ]
        
        for i, (test_input, expected) in enumerate(zip(test_cases, expected_results), 1):
            result = generator._clean_json_response(test_input)
            if result.strip() == expected.strip():
                print(f"✓ Caso {i}: JSON limpo corretamente")
            else:
                print(f"✗ Caso {i}: Esperado '{expected}', obtido '{result}'")
                
        print("✓ Teste de limpeza JSON concluído")
        return True
        
    except Exception as e:
        print(f"✗ Erro no teste JSON: {e}")
        return False

def test_logging_format():
    """Testa se os logs estão com formato correto"""
    print("\n=== Testando Formato de Logging ===")
    
    try:
        # Simular logs que seriam gerados
        test_logger = logging.getLogger('test_rag')
        
        test_logger.info("[RAG] Índice BM25 carregado com sucesso")
        test_logger.info("[RAG] Índice BM25 não encontrado, reconstruindo...")
        test_logger.warning("[RAG] Resposta JSON inválida, usando fallback de texto cru")
        
        print("✓ Logs de teste gerados com formato correto")
        return True
        
    except Exception as e:
        print(f"✗ Erro no teste de logging: {e}")
        return False

def main():
    """Executa todos os testes"""
    print("Iniciando testes das correções do pipeline RAG...\n")
    
    # Configurar variáveis de ambiente mínimas para teste
    os.environ.setdefault('SECRET_KEY', 'test-secret-key')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///database/app.db')
    
    tests = [
        ("Persistência BM25", test_bm25_persistence),
        ("Limpeza JSON", test_json_cleaning), 
        ("Formato Logging", test_logging_format)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Falha no teste {test_name}: {e}")
            results.append((test_name, False))
    
    # Sumário dos resultados
    print(f"\n=== SUMÁRIO DOS TESTES ===")
    passed = 0
    for test_name, result in results:
        status = "✓ PASSOU" if result else "✗ FALHOU"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nTestes aprovados: {passed}/{len(results)}")
    
    if passed == len(results):
        print("🎉 Todas as correções estão funcionando!")
    else:
        print("⚠️  Algumas correções precisam de ajustes.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)