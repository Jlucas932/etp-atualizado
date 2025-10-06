#!/usr/bin/env python3
"""
Test script para verificar a integração RAG no ETP dinâmico
"""

import os
import sys
import json
import requests
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações
API_BASE_URL = "http://localhost:5002"
TEST_CASES = [
    {
        "name": "Contratação de notebooks",
        "message": "Preciso contratar notebooks para os servidores da empresa",
        "expected_section": "DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO"
    },
    {
        "name": "Contratação de serviços de limpeza",
        "message": "Necessidade de contratação de serviços de limpeza para o prédio administrativo",
        "expected_section": "DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO"
    },
    {
        "name": "Contratação de sistema de software",
        "message": "Precisamos contratar um sistema de gestão documental para o órgão",
        "expected_section": "DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO"
    }
]

def test_health_check():
    """Testa se a API está funcionando"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/etp-dynamic/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Health check OK - Status: {data.get('status')}")
            logger.info(f"   OpenAI configurado: {data.get('openai_configured')}")
            logger.info(f"   ETP Generator pronto: {data.get('etp_generator_ready')}")
            return True
        else:
            logger.error(f"❌ Health check falhou - Status: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Erro ao conectar com a API: {e}")
        return False

def test_conversation(test_case):
    """Testa uma conversa específica"""
    logger.info(f"\n🧪 Testando: {test_case['name']}")
    
    try:
        # Preparar dados da requisição
        payload = {
            "message": test_case["message"],
            "conversation_history": [],
            "answered_questions": [],
            "extracted_answers": {},
            "objective_slug": "test"
        }
        
        # Fazer requisição
        response = requests.post(
            f"{API_BASE_URL}/api/etp-dynamic/conversation",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            ai_response = data.get('ai_response', '')
            
            logger.info(f"✅ Resposta recebida (primeiros 200 chars):")
            logger.info(f"   {ai_response[:200]}...")
            
            # Verificar se contém requisitos
            if "requisitos" in ai_response.lower() or "requisito" in ai_response.lower():
                logger.info("✅ Resposta contém requisitos")
            else:
                logger.warning("⚠️  Resposta não parece conter requisitos")
            
            # Verificar se há indicação de fonte (não deveria ter)
            if "base de conhecimento" in ai_response.lower() or "rag" in ai_response.lower():
                logger.warning("⚠️  Resposta menciona fonte (deveria ser transparente)")
            else:
                logger.info("✅ Resposta transparente (não menciona fonte)")
                
            return True
            
        else:
            logger.error(f"❌ Erro na requisição - Status: {response.status_code}")
            logger.error(f"   Resposta: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro ao testar conversa: {e}")
        return False

def test_rag_function_directly():
    """Testa a função search_requirements diretamente"""
    logger.info("\n🧪 Testando função search_requirements diretamente")
    
    try:
        # Adicionar caminho do projeto
        sys.path.insert(0, 'src/main/python')
        
        from rag.retrieval import search_requirements
        
        # Testar com diferentes queries
        test_queries = [
            "notebooks",
            "serviços de limpeza", 
            "sistema de software"
        ]
        
        for query in test_queries:
            logger.info(f"   Testando query: '{query}'")
            results = search_requirements("test", query, k=3)
            
            if results:
                logger.info(f"   ✅ {len(results)} resultados encontrados")
                for i, result in enumerate(results[:2]):
                    content = result.get('content', '')[:100]
                    logger.info(f"      {i+1}: {content}...")
            else:
                logger.info(f"   ⚠️  Nenhum resultado encontrado")
                
        return True
        
    except ImportError as e:
        logger.warning(f"⚠️  Não foi possível importar search_requirements: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao testar função RAG: {e}")
        return False

def main():
    """Função principal do teste"""
    logger.info("🚀 Iniciando testes de integração RAG")
    
    # Teste 1: Health check
    if not test_health_check():
        logger.error("❌ Health check falhou. Verifique se a aplicação está rodando.")
        return False
    
    # Teste 2: Função RAG direta
    test_rag_function_directly()
    
    # Teste 3: Conversas com diferentes tipos de contratação
    success_count = 0
    for test_case in TEST_CASES:
        if test_conversation(test_case):
            success_count += 1
    
    # Resultado final
    logger.info(f"\n📊 Resultado dos testes:")
    logger.info(f"   ✅ Sucessos: {success_count}/{len(TEST_CASES)}")
    logger.info(f"   ❌ Falhas: {len(TEST_CASES) - success_count}/{len(TEST_CASES)}")
    
    if success_count == len(TEST_CASES):
        logger.info("🎉 Todos os testes passaram!")
        return True
    else:
        logger.warning("⚠️  Alguns testes falharam.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)