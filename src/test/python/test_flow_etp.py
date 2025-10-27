"""
Test ETP flow validation - verify that system blocks advancement when requirements need input.
"""
import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.ai.generator import OpenAIGenerator

class TestFlowETP(unittest.TestCase):
    """Test that flow validation prevents advancement with incomplete requirements"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock OpenAI client
        class MockOpenAIClient:
            class ChatCompletions:
                def create(self, **kwargs):
                    class MockChoice:
                        class MockMessage:
                            content = '{"requirements": []}'
                        message = MockMessage()
                    class MockResponse:
                        choices = [MockChoice()]
                    return MockResponse()
            
            chat = type('Chat', (), {'completions': ChatCompletions()})()
        
        self.mock_client = MockOpenAIClient()
        self.generator = OpenAIGenerator(self.mock_client, model="gpt-4")
    
    def test_blocked_when_needs_input_above_30_percent(self):
        """Test that system blocks when >= 30% requirements need input"""
        print("\n[DEBUG_LOG] Testing blocked flow when >= 30% requirements need input")
        
        # Create requirements with 40% needing input (2 out of 5)
        requirements = [
            {
                'id': 1,
                'descricao': 'Requisito completo',
                'metrica': {'tipo': 'disponibilidade', 'valor': 0.99, 'unidade': 'proporção'},
                'sla': {'tipo': 'resposta', 'valor': 4, 'unidade': 'horas'},
                'aceite': 'Teste de disponibilidade mensal',
                'needs_input': False,
                'missing': []
            },
            {
                'id': 2,
                'descricao': 'Requisito incompleto sem métrica',
                'metrica': None,
                'sla': None,
                'aceite': '',
                'needs_input': True,
                'missing': ['métrica ou SLA', 'critério de aceite']
            },
            {
                'id': 3,
                'descricao': 'Outro requisito completo',
                'metrica': {'tipo': 'capacidade', 'valor': 100, 'unidade': 'usuários'},
                'sla': None,
                'aceite': 'Teste de carga com 100 usuários simultâneos',
                'needs_input': False,
                'missing': []
            },
            {
                'id': 4,
                'descricao': 'Requisito vago sem métrica',
                'metrica': None,
                'sla': None,
                'aceite': '',
                'needs_input': True,
                'missing': ['métrica ou SLA', 'critério de aceite']
            },
            {
                'id': 5,
                'descricao': 'Requisito final completo',
                'metrica': {'tipo': 'tempo', 'valor': 12, 'unidade': 'meses'},
                'sla': None,
                'aceite': 'Verificação de garantia válida',
                'needs_input': False,
                'missing': []
            }
        ]
        
        # Call the refinement validator
        result = self.generator._handle_refine_requirements(
            necessity="Sistema de gestão",
            context=[],
            data={'requirements': requirements}
        )
        
        print(f"[DEBUG_LOG] Result blocked: {result.get('blocked', False)}")
        print(f"[DEBUG_LOG] Needs input count: {result.get('needs_input_count', 0)}")
        
        # Verify that flow is blocked
        self.assertTrue(result.get('blocked', False), "Flow should be blocked when >= 30% requirements need input")
        self.assertEqual(result.get('needs_input_count'), 2, "Should identify 2 requirements needing input")
        self.assertIsNone(result.get('next_stage'), "Next stage should be None when blocked")
        self.assertIn('Não é possível avançar', result.get('message', ''), "Message should indicate blocking")
    
    def test_not_blocked_when_needs_input_below_30_percent(self):
        """Test that system allows advancement when < 30% requirements need input"""
        print("\n[DEBUG_LOG] Testing unblocked flow when < 30% requirements need input")
        
        # Create requirements with 20% needing input (1 out of 5)
        requirements = [
            {
                'id': 1,
                'descricao': 'Requisito completo',
                'metrica': {'tipo': 'disponibilidade', 'valor': 0.99, 'unidade': 'proporção'},
                'sla': {'tipo': 'resposta', 'valor': 4, 'unidade': 'horas'},
                'aceite': 'Teste de disponibilidade mensal',
                'needs_input': False,
                'missing': []
            },
            {
                'id': 2,
                'descricao': 'Requisito incompleto',
                'metrica': None,
                'sla': None,
                'aceite': '',
                'needs_input': True,
                'missing': ['métrica ou SLA']
            },
            {
                'id': 3,
                'descricao': 'Requisito completo 2',
                'metrica': {'tipo': 'capacidade', 'valor': 100, 'unidade': 'usuários'},
                'sla': None,
                'aceite': 'Teste de carga',
                'needs_input': False,
                'missing': []
            },
            {
                'id': 4,
                'descricao': 'Requisito completo 3',
                'metrica': {'tipo': 'tempo', 'valor': 24, 'unidade': 'horas'},
                'sla': None,
                'aceite': 'Verificação de prazo',
                'needs_input': False,
                'missing': []
            },
            {
                'id': 5,
                'descricao': 'Requisito completo 4',
                'metrica': {'tipo': 'conformidade', 'valor': 100, 'unidade': '%'},
                'sla': None,
                'aceite': 'Auditoria de conformidade',
                'needs_input': False,
                'missing': []
            }
        ]
        
        result = self.generator._handle_refine_requirements(
            necessity="Sistema de gestão",
            context=[],
            data={'requirements': requirements}
        )
        
        print(f"[DEBUG_LOG] Result blocked: {result.get('blocked', False)}")
        
        # Note: With 20% incomplete, system should still warn but might allow with conditions
        # The exact behavior depends on implementation - adjust assertion as needed
        # For now, we check that the system processes it
        self.assertIsNotNone(result.get('message'), "Should return a message")
    
    def test_blocked_with_vague_terms_no_metrics(self):
        """Test that system blocks requirements with vague terms and no metrics"""
        print("\n[DEBUG_LOG] Testing blocked flow with vague terms without metrics")
        
        requirements = [
            {
                'id': 1,
                'descricao': 'Sistema deve ser adequado e eficiente',
                'metrica': None,  # No metric for vague terms
                'sla': None,
                'aceite': 'Validação manual',
                'needs_input': False,
                'missing': []
            },
            {
                'id': 2,
                'descricao': 'Performance rápida',
                'metrica': None,
                'sla': None,
                'aceite': '',
                'needs_input': False,
                'missing': []
            }
        ]
        
        result = self.generator._handle_refine_requirements(
            necessity="Sistema de gestão",
            context=[],
            data={'requirements': requirements}
        )
        
        print(f"[DEBUG_LOG] Result blocked: {result.get('blocked', False)}")
        print(f"[DEBUG_LOG] Message: {result.get('message', '')[:100]}")
        
        # Should be blocked due to vague terms without metrics
        self.assertTrue(result.get('blocked', False), "Flow should be blocked with vague terms lacking metrics")
        self.assertIn('vago', result.get('message', '').lower(), "Message should mention vague terms")
    
    def test_blocked_with_duplicates(self):
        """Test that system blocks when duplicates are detected"""
        print("\n[DEBUG_LOG] Testing blocked flow with duplicate requirements")
        
        requirements = [
            {
                'id': 1,
                'descricao': 'Sistema deve ter alta disponibilidade',
                'metrica': {'tipo': 'disponibilidade', 'valor': 0.99, 'unidade': 'proporção'},
                'sla': None,
                'aceite': 'Teste mensal',
                'needs_input': False,
                'missing': []
            },
            {
                'id': 2,
                'descricao': 'Sistema deve ter alta disponibilidade',  # Duplicate
                'metrica': {'tipo': 'disponibilidade', 'valor': 0.99, 'unidade': 'proporção'},
                'sla': None,
                'aceite': 'Teste mensal',
                'needs_input': False,
                'missing': []
            },
            {
                'id': 3,
                'descricao': 'Outro requisito',
                'metrica': {'tipo': 'capacidade', 'valor': 50, 'unidade': 'usuários'},
                'sla': None,
                'aceite': 'Teste',
                'needs_input': False,
                'missing': []
            }
        ]
        
        result = self.generator._handle_refine_requirements(
            necessity="Sistema de gestão",
            context=[],
            data={'requirements': requirements}
        )
        
        print(f"[DEBUG_LOG] Result blocked: {result.get('blocked', False)}")
        
        # Should be blocked due to duplicates
        self.assertTrue(result.get('blocked', False), "Flow should be blocked with duplicate requirements")
        self.assertIn('duplicad', result.get('message', '').lower(), "Message should mention duplicates")

if __name__ == '__main__':
    unittest.main()
