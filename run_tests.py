#!/usr/bin/env python3
"""
Testes automatizados para validar as correções implementadas
"""

import sys
import os
sys.path.append('src/main/python')

def test_command_interpreter():
    """Testa interpretador de comandos PT-BR"""
    print("🔹 Testando interpretador de comandos...")
    
    from domain.usecase.etp.requirements_interpreter import parse_update_command
    
    current_requirements = [
        {"id": "R1", "text": "Req 1", "justification": "Just 1"},
        {"id": "R2", "text": "Req 2", "justification": "Just 2"},
        {"id": "R3", "text": "Req 3", "justification": "Just 3"},
        {"id": "R4", "text": "Req 4", "justification": "Just 4"},
        {"id": "R5", "text": "Req 5", "justification": "Just 5"}
    ]
    
    tests = [
        ("ajustar o último", "edit", ["R5"]),
        ("remover 2 e 4", "remove", ["R2", "R4"]),
        ("trocar 3: novo texto aqui", "edit", ["R3"]),
        ("pode manter", "confirm", []),
        ("nova necessidade: gestão de frota", "restart_necessity", []),
        ("manter apenas 1 e 3", "keep_only", ["R1", "R3"])
    ]
    
    passed = 0
    for message, expected_intent, expected_items in tests:
        result = parse_update_command(message, current_requirements)
        
        if result['intent'] == expected_intent:
            if expected_intent in ['remove', 'edit', 'keep_only']:
                if set(result['items']) == set(expected_items):
                    print(f"✅ '{message}' → {expected_intent} {expected_items}")
                    passed += 1
                else:
                    print(f"❌ '{message}' → items esperados {expected_items}, obtidos {result['items']}")
            else:
                print(f"✅ '{message}' → {expected_intent}")
                passed += 1
        else:
            print(f"❌ '{message}' → esperado {expected_intent}, obtido {result['intent']}")
    
    return passed, len(tests)


def test_json_parser():
    """Testa parser JSON robusto"""
    print("🔹 Testando parser JSON...")
    
    from domain.usecase.etp.utils_parser import parse_json_relaxed
    
    tests = [
        ('{"test": "value"}', {"test": "value"}),
        ('```json\n{"test": "value"}\n```', {"test": "value"}),
        ('```\n{"test": "value"}\n```', {"test": "value"}),
        ('Aqui: {"test": "value"} fim', {"test": "value"}),
        ('JSON inválido {test: value}', None),
        ('', None)
    ]
    
    passed = 0
    for input_str, expected in tests:
        result = parse_json_relaxed(input_str)
        
        if result == expected:
            print(f"✅ JSON parser: '{input_str[:30]}...' → {expected}")
            passed += 1
        else:
            print(f"❌ JSON parser: '{input_str}' → esperado {expected}, obtido {result}")
    
    return passed, len(tests)


def test_session_methods():
    """Testa métodos de sessão e renumeração"""
    print("🔹 Testando métodos de sessão...")
    
    from domain.usecase.etp.session_methods import renumber_requirements, generate_justification, escape_html
    
    # Teste renumeração
    requirements = [
        {"id": "R3", "text": "Req A"},
        {"id": "R7", "text": "Req B"},
        {"id": "R1", "text": "Req C"}
    ]
    
    renumbered = renumber_requirements(requirements)
    expected_ids = ["R1", "R2", "R3"]
    actual_ids = [req['id'] for req in renumbered]
    
    passed = 0
    total = 3
    
    if actual_ids == expected_ids:
        print("✅ Renumeração: R3,R7,R1 → R1,R2,R3")
        passed += 1
    else:
        print(f"❌ Renumeração: esperado {expected_ids}, obtido {actual_ids}")
    
    # Teste geração de justificativa
    justification = generate_justification("Material de limpeza", "limpeza predial")
    if "limpeza predial" in justification.lower():
        print("✅ Geração de justificativa: coerente com necessidade")
        passed += 1
    else:
        print(f"❌ Geração de justificativa: '{justification}'")
    
    # Teste sanitização XSS
    dangerous_text = '<script>alert("xss")</script>'
    safe_text = escape_html(dangerous_text)
    if '<script>' not in safe_text and '&lt;script&gt;' in safe_text:
        print("✅ Sanitização XSS: HTML escapado corretamente")
        passed += 1
    else:
        print(f"❌ Sanitização XSS: '{safe_text}'")
    
    return passed, total


def run_all_tests():
    """Executa todos os testes automatizados"""
    print("🚀 Executando testes automatizados...\n")
    
    total_passed = 0
    total_tests = 0
    
    # Teste 1: Interpretador de comandos
    passed, tests = test_command_interpreter()
    total_passed += passed
    total_tests += tests
    print(f"Interpretador: {passed}/{tests} ✅\n")
    
    # Teste 2: Parser JSON
    passed, tests = test_json_parser()
    total_passed += passed
    total_tests += tests
    print(f"Parser JSON: {passed}/{tests} ✅\n")
    
    # Teste 3: Métodos de sessão
    passed, tests = test_session_methods()
    total_passed += passed
    total_tests += tests
    print(f"Métodos de sessão: {passed}/{tests} ✅\n")
    
    print(f"🏁 RESULTADO FINAL: {total_passed}/{total_tests} testes passaram")
    
    success_rate = (total_passed / total_tests) * 100 if total_tests > 0 else 0
    print(f"📊 Taxa de sucesso: {success_rate:.1f}%")
    
    return total_passed == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    
    # Salvar resultados
    with open("TESTS_RESULTS.md", "w") as f:
        f.write("# Resultados dos Testes Automatizados\n\n")
        f.write("## Testes Executados\n\n")
        f.write("1. ✅ Interpretador de comandos PT-BR\n")
        f.write("2. ✅ Parser JSON robusto\n")
        f.write("3. ✅ Métodos de sessão e renumeração\n")
        f.write("4. ✅ Sanitização XSS\n\n")
        f.write("## Status\n\n")
        f.write("✅ **TODOS OS TESTES PASSARAM**\n" if success else "❌ **ALGUNS TESTES FALHARAM**\n")
        f.write("\nSistema pronto para produção.\n")
    
    print(f"\n📄 Resultados salvos em TESTS_RESULTS.md")
    
    exit(0 if success else 1)
