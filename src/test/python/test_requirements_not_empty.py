import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.ai.generator import generate_answer

class TestRequirementsNotEmpty(unittest.TestCase):
    """
    Testa que requisitos nunca são vazios.
    Dado collect_need com necessidade, o campo requirements retorna 8-15 itens numerados,
    sem "?" e sem vazio.
    """
    
    def setUp(self):
        """Set up test fixtures"""
        os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', 'test_api_key_for_testing')
    
    def test_collect_need_requirements_not_empty(self):
        """Testa que collect_need retorna requisitos não vazios"""
        history = []
        user_input = "gestão de frota de aeronaves"
        rag_context = {
            'chunks': [],
            'necessity': user_input
        }
        
        result = generate_answer('collect_need', history, user_input, rag_context)
        
        # Verificar que requirements existe e não é vazio
        self.assertIn('requirements', result)
        requirements = result.get('requirements', [])
        self.assertIsNotNone(requirements)
        self.assertIsInstance(requirements, list)
        self.assertGreater(len(requirements), 0, "Requirements list is empty")
        
        # Verificar que tem entre 8 e 15 requisitos
        self.assertGreaterEqual(
            len(requirements), 
            8, 
            f"Expected at least 8 requirements, got {len(requirements)}"
        )
        self.assertLessEqual(
            len(requirements), 
            15, 
            f"Expected at most 15 requirements, got {len(requirements)}"
        )
        
        print(f"[DEBUG_LOG] Requirements count: {len(requirements)}")
    
    def test_requirements_are_numbered(self):
        """Testa que todos os requisitos são numerados"""
        history = []
        user_input = "5 carros SUV"
        rag_context = {
            'chunks': [],
            'necessity': user_input
        }
        
        result = generate_answer('collect_need', history, user_input, rag_context)
        requirements = result.get('requirements', [])
        
        for i, req in enumerate(requirements):
            # Verificar que começa com número
            self.assertTrue(
                req.strip() and req.strip()[0].isdigit(),
                f"Requirement {i+1} is not numbered: '{req}'"
            )
            
            # Verificar que tem ponto após o número
            self.assertIn('.', req[:5], f"Requirement {i+1} doesn't have period after number: '{req}'")
        
        print(f"[DEBUG_LOG] All {len(requirements)} requirements are properly numbered")
    
    def test_requirements_no_questions(self):
        """Testa que requisitos não contêm perguntas"""
        history = []
        user_input = "notebooks para servidores"
        rag_context = {
            'chunks': [],
            'necessity': user_input
        }
        
        result = generate_answer('collect_need', history, user_input, rag_context)
        requirements = result.get('requirements', [])
        
        for i, req in enumerate(requirements):
            # Verificar que não termina com "?"
            self.assertFalse(
                req.strip().endswith('?'),
                f"Requirement {i+1} is a question: '{req}'"
            )
            
            # Verificar que não contém "?" no meio
            self.assertNotIn(
                '?',
                req,
                f"Requirement {i+1} contains question mark: '{req}'"
            )
        
        print(f"[DEBUG_LOG] All {len(requirements)} requirements are statements, not questions")
    
    def test_requirements_have_metrics(self):
        """Testa que requisitos têm métricas ou condições verificáveis"""
        history = []
        user_input = "sistema de gestão de documentos"
        rag_context = {
            'chunks': [],
            'necessity': user_input
        }
        
        result = generate_answer('collect_need', history, user_input, rag_context)
        requirements = result.get('requirements', [])
        
        # Pelo menos alguns requisitos devem ter números/métricas
        has_metrics_count = 0
        metric_patterns = [
            r'\d+\s*(meses|anos|dias|horas|minutos)',
            r'\d+\s*(GB|MB|TB|unidades|pessoas|usuários)',
            r'\d+\s*%',
            r'mínimo|máximo|pelo menos|até',
            r'SLA|garantia|prazo|disponibilidade'
        ]
        
        for req in requirements:
            req_lower = req.lower()
            for pattern in metric_patterns:
                import re
                if re.search(pattern, req_lower):
                    has_metrics_count += 1
                    break
        
        # Pelo menos 50% dos requisitos devem ter alguma métrica ou condição
        min_with_metrics = len(requirements) // 2
        self.assertGreaterEqual(
            has_metrics_count,
            min_with_metrics,
            f"Expected at least {min_with_metrics} requirements with metrics, got {has_metrics_count}"
        )
        
        print(f"[DEBUG_LOG] {has_metrics_count}/{len(requirements)} requirements have metrics or verifiable conditions")
    
    def test_different_needs_generate_different_requirements(self):
        """Testa que necessidades diferentes geram requisitos diferentes"""
        needs = [
            "notebooks para desenvolvimento",
            "veículos para transporte",
            "sistema de gestão hospitalar"
        ]
        
        all_requirements = []
        
        for need in needs:
            result = generate_answer('collect_need', [], need, {'chunks': [], 'necessity': need})
            requirements = result.get('requirements', [])
            
            # Cada necessidade deve gerar requisitos
            self.assertGreaterEqual(len(requirements), 8)
            
            all_requirements.append(set(req.lower()[:50] for req in requirements))
        
        # Verificar que os conjuntos são diferentes
        self.assertNotEqual(all_requirements[0], all_requirements[1])
        self.assertNotEqual(all_requirements[1], all_requirements[2])
        
        print(f"[DEBUG_LOG] Different needs generate different requirement sets")
    
    def tearDown(self):
        """Clean up after tests"""
        if os.environ.get('OPENAI_API_KEY') == 'test_api_key_for_testing':
            if 'OPENAI_API_KEY' in os.environ:
                del os.environ['OPENAI_API_KEY']

if __name__ == '__main__':
    unittest.main()
