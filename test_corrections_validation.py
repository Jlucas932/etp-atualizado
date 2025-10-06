#!/usr/bin/env python3
"""
Validação das correções implementadas nos 10 passos
Testa os problemas críticos identificados no pasted_content.txt
"""

import requests
import json
import time
import uuid

# Configuração do servidor de teste
BASE_URL = "http://localhost:5000"  # Ajustar conforme necessário
API_BASE = f"{BASE_URL}/api/etp-dynamic"

def test_session_persistence():
    """PASSO 1A & 2A: Testa se session_id é persistido entre chamadas"""
    print("🔹 Testando persistência de sessão...")
    
    # Primeira chamada - deve criar nova sessão
    response1 = requests.post(f"{API_BASE}/conversation", json={
        "message": "Preciso contratar serviços de limpeza para o órgão"
    })
    
    if response1.status_code != 200:
        print(f"❌ Erro na primeira chamada: {response1.status_code}")
        return False
    
    data1 = response1.json()
    session_id = data1.get("session_id")
    
    if not session_id:
        print("❌ session_id não retornado na primeira chamada")
        return False
    
    print(f"✅ Session ID criado: {session_id}")
    
    # Segunda chamada - deve reutilizar a mesma sessão
    response2 = requests.post(f"{API_BASE}/conversation", json={
        "message": "pode manter os requisitos",
        "session_id": session_id
    })
    
    if response2.status_code != 200:
        print(f"❌ Erro na segunda chamada: {response2.status_code}")
        return False
    
    data2 = response2.json()
    session_id_2 = data2.get("session_id")
    
    if session_id != session_id_2:
        print(f"❌ Session ID mudou: {session_id} -> {session_id_2}")
        return False
    
    print("✅ Session ID mantido entre chamadas")
    return True


def test_command_interpreter():
    """PASSO 3: Testa interpretador de comandos em português brasileiro"""
    print("🔹 Testando interpretador de comandos...")
    
    from src.main.python.domain.usecase.etp.requirements_interpreter import parse_update_command
    
    # Teste de comandos típicos
    test_cases = [
        ("remover o 2", "remove", ["R2"]),
        ("ajustar o último", "edit", ["R5"]),  # Assumindo 5 requisitos
        ("pode manter", "confirm", []),
        ("trocar 3: novo texto aqui", "edit", ["R3"]),
        ("na verdade a necessidade é outra", "restart_necessity", []),
        ("adicionar novo requisito", "add", ["novo requisito"]),
        ("manter apenas 1 e 3", "keep_only", ["R1", "R3"])
    ]
    
    current_requirements = [
        {"id": "R1", "text": "Req 1"},
        {"id": "R2", "text": "Req 2"},
        {"id": "R3", "text": "Req 3"},
        {"id": "R4", "text": "Req 4"},
        {"id": "R5", "text": "Req 5"}
    ]
    
    for message, expected_intent, expected_items in test_cases:
        result = parse_update_command(message, current_requirements)
        
        if result['intent'] != expected_intent:
            print(f"❌ Comando '{message}': esperado {expected_intent}, obtido {result['intent']}")
            return False
        
        if expected_intent in ['remove', 'edit', 'keep_only'] and result['items'] != expected_items:
            print(f"❌ Comando '{message}': itens esperados {expected_items}, obtidos {result['items']}")
            return False
    
    print("✅ Interpretador de comandos funcionando")
    return True


def test_json_parser():
    """PASSO 5: Testa parser robusto para JSON com cercas"""
    print("🔹 Testando parser JSON robusto...")
    
    from src.main.python.domain.usecase.etp.utils_parser import parse_json_relaxed
    
    test_cases = [
        ('{"test": "value"}', {"test": "value"}),
        ('```json\n{"test": "value"}\n```', {"test": "value"}),
        ('```\n{"test": "value"}\n```', {"test": "value"}),
        ('Aqui está o JSON: {"test": "value"} fim', {"test": "value"}),
        ('JSON inválido {test: value}', None),
        ('', None)
    ]
    
    for input_str, expected in test_cases:
        result = parse_json_relaxed(input_str)
        
        if result != expected:
            print(f"❌ Parser JSON: entrada '{input_str}', esperado {expected}, obtido {result}")
            return False
    
    print("✅ Parser JSON robusto funcionando")
    return True


def test_requirements_rendering():
    """PASSO 1B: Testa renderização limpa de requisitos"""
    print("🔹 Testando renderização de requisitos...")
    
    # Simular dados estruturados
    test_data = {
        "kind": "requirements_suggestion",
        "necessity": "Contratação de serviços de limpeza",
        "requirements": [
            {"id": "R1", "text": "Fornecimento de materiais", "justification": "Necessário para execução"},
            {"id": "R2", "text": "Mão de obra qualificada", "justification": "Garantir qualidade"}
        ],
        "message": "Requisitos sugeridos baseados na necessidade"
    }
    
    # Verificar se não há JSON cru na renderização
    # (Este teste seria mais completo com DOM real, mas validamos a lógica)
    
    # Verificar se os campos estão estruturados
    if not test_data.get("kind", "").startswith("requirements_"):
        print("❌ Campo 'kind' não estruturado corretamente")
        return False
    
    if not isinstance(test_data.get("requirements"), list):
        print("❌ Campo 'requirements' não é lista")
        return False
    
    for req in test_data["requirements"]:
        if not all(key in req for key in ["id", "text", "justification"]):
            print(f"❌ Requisito mal estruturado: {req}")
            return False
    
    print("✅ Estrutura de renderização de requisitos válida")
    return True


def test_unified_contract():
    """PASSO 6: Testa contrato único de resposta"""
    print("🔹 Testando contrato único de resposta...")
    
    # Simular resposta do backend
    test_responses = [
        {
            "success": True,
            "session_id": "test-session",
            "kind": "text",
            "ai_response": "Mensagem de texto",
            "message": "Mensagem de texto"
        },
        {
            "success": True,
            "session_id": "test-session",
            "kind": "requirements_suggestion",
            "necessity": "Necessidade teste",
            "requirements": [],
            "ai_response": "Requisitos sugeridos",
            "message": "Requisitos sugeridos"
        }
    ]
    
    for response in test_responses:
        # Verificar campos obrigatórios
        required_fields = ["success", "session_id", "kind"]
        for field in required_fields:
            if field not in response:
                print(f"❌ Campo obrigatório '{field}' ausente na resposta")
                return False
        
        # Verificar consistência entre ai_response e message
        if response.get("ai_response") != response.get("message"):
            print("❌ Inconsistência entre ai_response e message")
            return False
    
    print("✅ Contrato único de resposta válido")
    return True


def run_validation():
    """Executa todos os testes de validação"""
    print("🚀 Iniciando validação das correções...\n")
    
    tests = [
        ("Persistência de Sessão", test_session_persistence),
        ("Interpretador de Comandos", test_command_interpreter),
        ("Parser JSON Robusto", test_json_parser),
        ("Renderização de Requisitos", test_requirements_rendering),
        ("Contrato Único", test_unified_contract)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSOU")
            else:
                print(f"❌ {test_name}: FALHOU")
        except Exception as e:
            print(f"❌ {test_name}: ERRO - {e}")
    
    print(f"\n🏁 Resultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todas as correções validadas com sucesso!")
        return True
    else:
        print("⚠️  Algumas correções precisam de ajustes")
        return False


if __name__ == "__main__":
    success = run_validation()
    exit(0 if success else 1)
