"""
Testes para o interpretador de intenções via OpenAI
Verifica conversão de linguagem natural para comandos estruturados
"""

import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from domain.usecase.etp.requirements_interpreter import (
    parse_intent_with_openai,
    convert_openai_intent_to_controller_format,
    parse_update_command
)


class TestIntentParser(unittest.TestCase):
    """Testes para o parser de intenções"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock requirements for testing
        self.mock_requirements = [
            {'id': 'R1', 'text': 'Requisito de segurança', 'justification': 'Justificativa 1'},
            {'id': 'R2', 'text': 'Requisito de manutenção', 'justification': 'Justificativa 2'},
            {'id': 'R3', 'text': 'Requisito de treinamento', 'justification': 'Justificativa 3'},
            {'id': 'R4', 'text': 'Requisito de qualidade', 'justification': 'Justificativa 4'},
            {'id': 'R5', 'text': 'Requisito de prazo', 'justification': 'Justificativa 5'}
        ]
    
    def test_convert_accept_all(self):
        """Testa conversão de accept_all para confirm"""
        openai_intent = {"intent": "accept_all"}
        result = convert_openai_intent_to_controller_format(openai_intent, self.mock_requirements)
        
        self.assertEqual(result['intent'], 'confirm')
        self.assertEqual(result['items'], [])
        self.assertIn('confirmad', result['message'].lower())
    
    def test_convert_replace_item(self):
        """Testa conversão de replace_item para edit"""
        openai_intent = {
            "intent": "replace_item",
            "index": 3,
            "new_text": "Compatível com ANAC RBAC 145"
        }
        result = convert_openai_intent_to_controller_format(openai_intent, self.mock_requirements)
        
        self.assertEqual(result['intent'], 'edit')
        self.assertIn('R3', result['items'])
        self.assertEqual(result['new_text'], "Compatível com ANAC RBAC 145")
    
    def test_convert_remove_items(self):
        """Testa conversão de remove_items para remove"""
        openai_intent = {
            "intent": "remove_items",
            "indexes": [2, 4]
        }
        result = convert_openai_intent_to_controller_format(openai_intent, self.mock_requirements)
        
        self.assertEqual(result['intent'], 'remove')
        self.assertIn('R2', result['items'])
        self.assertIn('R4', result['items'])
    
    def test_convert_remove_items_with_add(self):
        """Testa comando combinado: remove + add"""
        openai_intent = {
            "intent": "remove_items",
            "indexes": [2, 4],
            "extra_add": [{"text": "treinamento dos operadores"}]
        }
        result = convert_openai_intent_to_controller_format(openai_intent, self.mock_requirements)
        
        self.assertEqual(result['intent'], 'remove')
        self.assertIn('R2', result['items'])
        self.assertIn('R4', result['items'])
        self.assertIn('extra_add', result)
        self.assertEqual(len(result['extra_add']), 1)
        self.assertEqual(result['extra_add'][0]['text'], 'treinamento dos operadores')
    
    def test_convert_add_item(self):
        """Testa conversão de add_item para add"""
        openai_intent = {
            "intent": "add_item",
            "new_text": "treinamento de 4h"
        }
        result = convert_openai_intent_to_controller_format(openai_intent, self.mock_requirements)
        
        self.assertEqual(result['intent'], 'add')
        self.assertIn('treinamento de 4h', result['items'])
    
    def test_convert_reorder(self):
        """Testa conversão de reorder"""
        openai_intent = {
            "intent": "reorder",
            "new_order": [3, 1, 2, 5, 4]
        }
        result = convert_openai_intent_to_controller_format(openai_intent, self.mock_requirements)
        
        self.assertEqual(result['intent'], 'reorder')
        self.assertEqual(result['items'], [3, 1, 2, 5, 4])
    
    def test_convert_ask_clarification(self):
        """Testa conversão de ask_clarification para ask"""
        openai_intent = {
            "intent": "ask_clarification",
            "question": "Explicar requisito 5"
        }
        result = convert_openai_intent_to_controller_format(openai_intent, self.mock_requirements)
        
        self.assertEqual(result['intent'], 'ask')
        self.assertEqual(result['items'], [])
        self.assertIn('Explicar requisito 5', result['message'])
    
    def test_convert_reject_and_restart(self):
        """Testa conversão de reject_and_restart para restart_necessity"""
        openai_intent = {
            "intent": "reject_and_restart",
            "reason": "nova necessidade: manutenção predial"
        }
        result = convert_openai_intent_to_controller_format(openai_intent, self.mock_requirements)
        
        self.assertEqual(result['intent'], 'restart_necessity')
        self.assertEqual(result['items'], [])
        self.assertIn('manutenção predial', result['message'])
    
    def test_parse_update_command_fallback(self):
        """Testa fallback para parser regex quando OpenAI não está disponível"""
        # Sem cliente OpenAI, deve usar regex fallback
        result = parse_update_command("ok pode seguir", self.mock_requirements, openai_client=None)
        
        # Deve retornar confirm intent
        self.assertIn(result['intent'], ['confirm', 'accept'])
    
    def test_parse_update_command_with_question(self):
        """Testa detecção de pergunta no parser"""
        result = parse_update_command("não entendi o requisito 2", self.mock_requirements, openai_client=None)
        
        # Deve retornar ask intent
        self.assertEqual(result['intent'], 'ask')
    
    def test_parse_update_command_remove(self):
        """Testa comando de remoção"""
        result = parse_update_command("remover o 2 e o 4", self.mock_requirements, openai_client=None)
        
        # Deve retornar remove intent
        self.assertEqual(result['intent'], 'remove')
        self.assertTrue(len(result['items']) >= 1)
    
    def test_parse_update_command_add(self):
        """Testa comando de adição"""
        result = parse_update_command("adicionar requisito de auditoria", self.mock_requirements, openai_client=None)
        
        # Deve retornar add intent
        self.assertEqual(result['intent'], 'add')
        self.assertTrue(len(result['items']) >= 1)


class TestOpenAIIntentParser(unittest.TestCase):
    """Testes que requerem OpenAI configurado (podem ser skipped)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_requirements = [
            {'id': 'R1', 'text': 'Requisito de segurança', 'justification': 'Justificativa 1'},
            {'id': 'R2', 'text': 'Requisito de manutenção', 'justification': 'Justificativa 2'},
            {'id': 'R3', 'text': 'Requisito de treinamento', 'justification': 'Justificativa 3'},
            {'id': 'R4', 'text': 'Requisito de qualidade', 'justification': 'Justificativa 4'},
            {'id': 'R5', 'text': 'Requisito de prazo', 'justification': 'Justificativa 5'}
        ]
        
        # Check if OpenAI is available
        self.openai_available = False
        try:
            import openai
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key and api_key != 'test_api_key_for_testing':
                self.client = openai.OpenAI(api_key=api_key)
                self.openai_available = True
        except:
            pass
    
    def test_openai_accept_all(self):
        """Testa: 'Mantém como está, pode seguir.' → accept_all"""
        if not self.openai_available:
            self.skipTest("OpenAI não disponível")
        
        result = parse_intent_with_openai(
            "Mantém como está, pode seguir.",
            self.mock_requirements,
            self.client
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.get('intent'), 'accept_all')
    
    def test_openai_replace_item(self):
        """Testa: 'Troca o 3 por ...' → replace_item"""
        if not self.openai_available:
            self.skipTest("OpenAI não disponível")
        
        result = parse_intent_with_openai(
            "Troca o 3 por 'Compatível com ANAC RBAC 145'.",
            self.mock_requirements,
            self.client
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.get('intent'), 'replace_item')
        self.assertEqual(result.get('index'), 3)
        self.assertIn('ANAC', result.get('new_text', ''))
    
    def test_openai_remove_and_add(self):
        """Testa: 'Remove 2 e 4 e adiciona ...' → remove_items + add"""
        if not self.openai_available:
            self.skipTest("OpenAI não disponível")
        
        result = parse_intent_with_openai(
            "Remove 2 e 4 e adiciona 'treinamento dos operadores'.",
            self.mock_requirements,
            self.client
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.get('intent'), 'remove_items')
        self.assertIn(2, result.get('indexes', []))
        self.assertIn(4, result.get('indexes', []))
    
    def test_openai_ask_clarification(self):
        """Testa: 'Não entendi esse requisito 5, explica.' → ask_clarification"""
        if not self.openai_available:
            self.skipTest("OpenAI não disponível")
        
        result = parse_intent_with_openai(
            "Não entendi esse requisito 5, explica.",
            self.mock_requirements,
            self.client
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.get('intent'), 'ask_clarification')
    
    def test_openai_reject_and_restart(self):
        """Testa: 'Volta pro começo, necessidade mudou...' → reject_and_restart"""
        if not self.openai_available:
            self.skipTest("OpenAI não disponível")
        
        result = parse_intent_with_openai(
            "Volta pro começo, necessidade mudou para manutenção predial.",
            self.mock_requirements,
            self.client
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.get('intent'), 'reject_and_restart')
    
    def test_openai_natural_language_variations(self):
        """Testa variações naturais: 'tira manutenção', 'inclui treinamento'"""
        if not self.openai_available:
            self.skipTest("OpenAI não disponível")
        
        # Test "tira manutenção"
        result1 = parse_intent_with_openai(
            "Tira manutenção",
            self.mock_requirements,
            self.client
        )
        self.assertIsNotNone(result1)
        self.assertEqual(result1.get('intent'), 'remove_items')
        
        # Test "inclui treinamento de 4h"
        result2 = parse_intent_with_openai(
            "Inclui treinamento de 4h",
            self.mock_requirements,
            self.client
        )
        self.assertIsNotNone(result2)
        self.assertEqual(result2.get('intent'), 'add_item')


if __name__ == '__main__':
    print("=" * 70)
    print("TESTES DO INTERPRETADOR DE INTENÇÕES VIA OPENAI")
    print("=" * 70)
    print()
    
    # Run tests
    unittest.main(verbosity=2)
