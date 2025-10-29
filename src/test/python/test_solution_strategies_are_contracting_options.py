import unittest
import sys
import os
import re

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.ai.generator import generate_answer

class TestSolutionStrategiesAreContractingOptions(unittest.TestCase):
    """
    Testa que solution_strategies retorna opções de contratação (compra, locação, comodato, etc.)
    e NÃO "passos do ETP".
    """
    
    def setUp(self):
        """Set up test fixtures"""
        os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', 'test_api_key_for_testing')
        
        # Padrões proibidos (etapas de ETP, não estratégias de contratação)
        self.forbidden_etp_patterns = [
            r'elaborar.*(etp|termo de referência)',
            r'etapa.*etp',
            r'passo.*etp',
            r'definir escopo',
            r'planejar contratação',
            r'executar.*etp',
            r'validar.*etp',
            r'fazer.*etp',
            r'montar.*etp',
            r'preparar.*etp'
        ]
        
        # Padrões esperados (opções de contratação)
        self.expected_contracting_patterns = [
            r'compra|aquisição',
            r'locação|aluguel',
            r'comodato',
            r'outsourcing|terceirização',
            r'leasing',
            r'ata de registro de preços|arp',
            r'contrato.*desempenho',
            r'assinatura|subscription'
        ]
    
    def test_strategies_are_contracting_options(self):
        """Testa que strategies contém opções de contratação"""
        history = []
        user_input = "melhor caminho"
        rag_context = {
            'chunks': [],
            'necessity': 'notebooks para servidores',
            'requirements': [
                '1. Fornecimento de 50 notebooks',
                '2. Processador i7 ou superior',
                '3. Garantia de 36 meses'
            ]
        }
        
        result = generate_answer('solution_strategies', history, user_input, rag_context)
        
        # Verificar que tem strategies
        self.assertIn('strategies', result)
        strategies = result.get('strategies', [])
        self.assertGreater(len(strategies), 0, "No strategies returned")
        
        # Verificar que tem entre 2 e 5 estratégias
        self.assertGreaterEqual(len(strategies), 2, f"Expected at least 2 strategies, got {len(strategies)}")
        self.assertLessEqual(len(strategies), 5, f"Expected at most 5 strategies, got {len(strategies)}")
        
        print(f"[DEBUG_LOG] Strategies count: {len(strategies)}")
        
        # Verificar que cada estratégia tem os campos esperados
        for i, strat in enumerate(strategies):
            self.assertIn('titulo', strat, f"Strategy {i+1} missing 'titulo'")
            self.assertIn('quando_indicado', strat, f"Strategy {i+1} missing 'quando_indicado'")
            self.assertIn('vantagens', strat, f"Strategy {i+1} missing 'vantagens'")
            self.assertIn('riscos', strat, f"Strategy {i+1} missing 'riscos'")
            
            print(f"[DEBUG_LOG] Strategy {i+1}: {strat.get('titulo')}")
    
    def test_strategies_not_etp_steps(self):
        """Testa que strategies NÃO são passos de elaboração de ETP"""
        history = []
        user_input = "opções de contratação"
        rag_context = {
            'chunks': [],
            'necessity': 'veículos para transporte',
            'requirements': [
                '1. Fornecimento de 5 veículos SUV',
                '2. Ano de fabricação 2024'
            ]
        }
        
        result = generate_answer('solution_strategies', history, user_input, rag_context)
        strategies = result.get('strategies', [])
        
        # Verificar que títulos e descrições NÃO mencionam etapas de ETP
        for i, strat in enumerate(strategies):
            titulo = strat.get('titulo', '').lower()
            quando = strat.get('quando_indicado', '').lower()
            
            combined_text = f"{titulo} {quando}"
            
            for pattern in self.forbidden_etp_patterns:
                match = re.search(pattern, combined_text, re.IGNORECASE)
                self.assertIsNone(
                    match,
                    f"Strategy {i+1} contains forbidden ETP step pattern '{pattern}': {titulo}"
                )
        
        print(f"[DEBUG_LOG] All {len(strategies)} strategies are contracting options, not ETP steps")
    
    def test_strategies_have_contracting_keywords(self):
        """Testa que pelo menos algumas estratégias mencionam modalidades de contratação"""
        history = []
        user_input = "estratégias de contratação"
        rag_context = {
            'chunks': [],
            'necessity': 'impressoras multifuncionais',
            'requirements': [
                '1. Fornecimento de 20 impressoras',
                '2. Garantia de 24 meses'
            ]
        }
        
        result = generate_answer('solution_strategies', history, user_input, rag_context)
        strategies = result.get('strategies', [])
        
        # Verificar que pelo menos metade das estratégias menciona modalidades de contratação
        matches_count = 0
        
        for strat in strategies:
            titulo = strat.get('titulo', '').lower()
            quando = strat.get('quando_indicado', '').lower()
            combined_text = f"{titulo} {quando}"
            
            for pattern in self.expected_contracting_patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    matches_count += 1
                    break
        
        min_expected = len(strategies) // 2 if len(strategies) > 2 else 1
        self.assertGreaterEqual(
            matches_count,
            min_expected,
            f"Expected at least {min_expected} strategies with contracting keywords, got {matches_count}"
        )
        
        print(f"[DEBUG_LOG] {matches_count}/{len(strategies)} strategies contain contracting modality keywords")
    
    def test_strategies_have_vantagens_and_riscos(self):
        """Testa que cada estratégia tem vantagens e riscos listados"""
        history = []
        user_input = "opções disponíveis"
        rag_context = {
            'chunks': [],
            'necessity': 'sistema de backup em nuvem',
            'requirements': [
                '1. Backup automatizado diário',
                '2. Retenção de 90 dias'
            ]
        }
        
        result = generate_answer('solution_strategies', history, user_input, rag_context)
        strategies = result.get('strategies', [])
        
        for i, strat in enumerate(strategies):
            vantagens = strat.get('vantagens', [])
            riscos = strat.get('riscos', [])
            
            # Verificar que vantagens é uma lista não vazia
            self.assertIsInstance(vantagens, list, f"Strategy {i+1} vantagens is not a list")
            self.assertGreater(len(vantagens), 0, f"Strategy {i+1} has no vantagens")
            
            # Verificar que riscos é uma lista não vazia
            self.assertIsInstance(riscos, list, f"Strategy {i+1} riscos is not a list")
            self.assertGreater(len(riscos), 0, f"Strategy {i+1} has no riscos")
            
            print(f"[DEBUG_LOG] Strategy {i+1}: {len(vantagens)} vantagens, {len(riscos)} riscos")
    
    def test_strategies_title_not_generic(self):
        """Testa que títulos de estratégias não são genéricos demais"""
        history = []
        user_input = "estratégias"
        rag_context = {
            'chunks': [],
            'necessity': 'mobiliário para escritório',
            'requirements': [
                '1. Fornecimento de mesas e cadeiras',
                '2. Entrega em 60 dias'
            ]
        }
        
        result = generate_answer('solution_strategies', history, user_input, rag_context)
        strategies = result.get('strategies', [])
        
        # Títulos muito genéricos (não permitidos)
        generic_titles = [
            'estratégia 1', 'estratégia 2', 'estratégia 3',
            'opção 1', 'opção 2', 'opção 3',
            'caminho 1', 'caminho 2'
        ]
        
        for i, strat in enumerate(strategies):
            titulo = strat.get('titulo', '').lower().strip()
            
            self.assertNotIn(
                titulo,
                generic_titles,
                f"Strategy {i+1} has generic title: '{titulo}'"
            )
            
            # Título deve ter pelo menos 3 palavras significativas
            words = [w for w in titulo.split() if len(w) > 2]
            self.assertGreaterEqual(
                len(words),
                2,
                f"Strategy {i+1} title too short/generic: '{titulo}'"
            )
        
        print(f"[DEBUG_LOG] All {len(strategies)} strategies have specific titles")
    
    def tearDown(self):
        """Clean up after tests"""
        if os.environ.get('OPENAI_API_KEY') == 'test_api_key_for_testing':
            if 'OPENAI_API_KEY' in os.environ:
                del os.environ['OPENAI_API_KEY']

if __name__ == '__main__':
    unittest.main()
