import unittest
import sys
import os
import re

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.ai.generator import generate_answer

class TestNoCannedMessages(unittest.TestCase):
    """
    Valida que nenhuma resposta contém textos fixos conhecidos.
    Testa contra: "Você pode dizer", "pode seguir", "adicionar:", "editar:", "remover:"
    """
    
    def setUp(self):
        """Set up test fixtures"""
        os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', 'test_api_key_for_testing')
        
        # Lista de padrões proibidos (canned messages)
        self.forbidden_patterns = [
            r'você pode dizer',
            r'pode seguir',
            r'adicionar:',
            r'editar:',
            r'remover:',
            r'com base na sua necessidade, sugiro',
            r'faz sentido o que você descreveu',
            r'escolhi esses pontos porque',
            r'se quiser ajustar algo, diga no seu jeito'
        ]
    
    def test_collect_need_no_canned_messages(self):
        """Testa que collect_need não retorna mensagens prontas"""
        history = []
        user_input = "5 carros SUV para secretaria de administração"
        rag_context = {
            'chunks': [],
            'necessity': user_input
        }
        
        result = generate_answer('collect_need', history, user_input, rag_context)
        
        # Verificar que tem intro e requirements
        self.assertIn('intro', result)
        self.assertIn('requirements', result)
        
        # Verificar que intro não contém padrões proibidos
        intro = result.get('intro', '').lower()
        for pattern in self.forbidden_patterns:
            self.assertIsNone(
                re.search(pattern, intro, re.IGNORECASE),
                f"Canned message found in intro: '{pattern}'"
            )
        
        # Verificar requirements
        requirements = result.get('requirements', [])
        for req in requirements:
            req_lower = req.lower()
            for pattern in self.forbidden_patterns:
                self.assertIsNone(
                    re.search(pattern, req_lower, re.IGNORECASE),
                    f"Canned message found in requirement: '{pattern}'"
                )
    
    def test_refine_no_canned_messages(self):
        """Testa que refine não retorna mensagens prontas"""
        history = [
            {'role': 'user', 'content': '5 carros SUV'},
            {'role': 'assistant', 'content': 'Requisitos gerados'}
        ]
        user_input = "incluir garantia de 36 meses e rastreador GPS"
        rag_context = {
            'chunks': [],
            'necessity': '5 carros SUV',
            'requirements': [
                '1. Fornecimento de 5 veículos SUV',
                '2. Ano de fabricação 2024 ou superior'
            ]
        }
        
        result = generate_answer('refine', history, user_input, rag_context)
        
        # Verificar que tem intro e requirements
        self.assertIn('intro', result)
        self.assertIn('requirements', result)
        
        # Verificar que intro não contém padrões proibidos
        intro = result.get('intro', '').lower()
        for pattern in self.forbidden_patterns:
            self.assertIsNone(
                re.search(pattern, intro, re.IGNORECASE),
                f"Canned message found in refine intro: '{pattern}'"
            )
    
    def test_solution_strategies_no_canned_messages(self):
        """Testa que solution_strategies não retorna mensagens prontas"""
        history = []
        user_input = "melhor caminho"
        rag_context = {
            'chunks': [],
            'necessity': 'notebooks para servidores',
            'requirements': [
                '1. Fornecimento de notebooks',
                '2. Garantia de 12 meses'
            ]
        }
        
        result = generate_answer('solution_strategies', history, user_input, rag_context)
        
        # Verificar que tem intro e strategies
        self.assertIn('intro', result)
        self.assertIn('strategies', result)
        
        # Verificar que intro não contém padrões proibidos
        intro = result.get('intro', '').lower()
        for pattern in self.forbidden_patterns:
            self.assertIsNone(
                re.search(pattern, intro, re.IGNORECASE),
                f"Canned message found in strategies intro: '{pattern}'"
            )
        
        # Verificar strategies
        strategies = result.get('strategies', [])
        for strat in strategies:
            titulo = strat.get('titulo', '').lower()
            quando = strat.get('quando_indicado', '').lower()
            
            for pattern in self.forbidden_patterns:
                self.assertIsNone(
                    re.search(pattern, titulo, re.IGNORECASE),
                    f"Canned message found in strategy title: '{pattern}'"
                )
                self.assertIsNone(
                    re.search(pattern, quando, re.IGNORECASE),
                    f"Canned message found in strategy description: '{pattern}'"
                )
    
    def tearDown(self):
        """Clean up after tests"""
        # Clean environment variables if they were test values
        if os.environ.get('OPENAI_API_KEY') == 'test_api_key_for_testing':
            if 'OPENAI_API_KEY' in os.environ:
                del os.environ['OPENAI_API_KEY']

if __name__ == '__main__':
    unittest.main()
