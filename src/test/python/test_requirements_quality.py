"""
Test requirements quality validation - verify that requirements without metrics/SLA are rejected.
"""
import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.ai.generator import OpenAIGenerator

class TestRequirementsQuality(unittest.TestCase):
    """Test that requirements quality validation rejects incomplete requirements"""
    
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
    
    def test_validate_marks_requirements_without_metrics_or_sla(self):
        """Test that validation marks requirements missing both metrics and SLA"""
        print("\n[DEBUG_LOG] Testing validation marks requirements without metrics or SLA")
        
        requirements = [
            {
                'id': 1,
                'descricao': 'Sistema deve funcionar bem',
                'metrica': None,  # Missing
                'sla': None,      # Missing
                'aceite': 'Teste funcional',
                'grounding': []
            },
            {
                'id': 2,
                'descricao': 'Documentação completa',
                'metrica': None,  # Missing
                'sla': None,      # Missing
                'aceite': '',     # Also missing
                'grounding': []
            }
        ]
        
        validated = self.generator._validate_and_mark_requirements(requirements)
        
        print(f"[DEBUG_LOG] Validated requirements count: {len(validated)}")
        for req in validated:
            print(f"[DEBUG_LOG] Req {req['id']}: needs_input={req.get('needs_input')}, missing={req.get('missing')}")
        
        # All requirements should be marked as needing input
        self.assertEqual(len(validated), 2, "Should validate all requirements")
        self.assertTrue(validated[0]['needs_input'], "First requirement should need input")
        self.assertTrue(validated[1]['needs_input'], "Second requirement should need input")
        self.assertIn('métrica ou SLA', validated[0]['missing'], "Should indicate missing metric/SLA")
        self.assertIn('métrica ou SLA', validated[1]['missing'], "Should indicate missing metric/SLA")
    
    def test_validate_accepts_requirements_with_metrics(self):
        """Test that validation accepts requirements with proper metrics"""
        print("\n[DEBUG_LOG] Testing validation accepts requirements with metrics")
        
        requirements = [
            {
                'id': 1,
                'descricao': 'Disponibilidade do sistema',
                'metrica': {'tipo': 'disponibilidade', 'valor': 0.999, 'unidade': 'proporção'},
                'sla': None,
                'aceite': 'Medição mensal de uptime ≥ 99.9%',
                'grounding': []
            },
            {
                'id': 2,
                'descricao': 'Tempo de resposta',
                'metrica': None,
                'sla': {'tipo': 'resposta', 'valor': 2, 'unidade': 'segundos', 'janela': '95º percentil'},
                'aceite': 'Medição de latência em produção',
                'grounding': []
            }
        ]
        
        validated = self.generator._validate_and_mark_requirements(requirements)
        
        print(f"[DEBUG_LOG] Validated requirements count: {len(validated)}")
        for req in validated:
            print(f"[DEBUG_LOG] Req {req['id']}: needs_input={req.get('needs_input')}, missing={req.get('missing')}")
        
        # Requirements should NOT need input (they have metrics/SLA and aceite)
        self.assertFalse(validated[0]['needs_input'], "First requirement should not need input")
        self.assertFalse(validated[1]['needs_input'], "Second requirement should not need input")
        self.assertEqual(len(validated[0]['missing']), 0, "First requirement should have no missing items")
        self.assertEqual(len(validated[1]['missing']), 0, "Second requirement should have no missing items")
    
    def test_validate_rejects_vague_terms_without_metrics(self):
        """Test that validation marks vague terms without metrics as needing input"""
        print("\n[DEBUG_LOG] Testing validation rejects vague terms without metrics")
        
        requirements = [
            {
                'id': 1,
                'descricao': 'Sistema deve ser rápido e eficiente',
                'metrica': None,  # Vague terms without metric
                'sla': None,
                'aceite': 'Testes de desempenho',
                'grounding': []
            },
            {
                'id': 2,
                'descricao': 'Solução adequada e apropriada',
                'metrica': None,  # Vague terms without metric
                'sla': None,
                'aceite': '',
                'grounding': []
            },
            {
                'id': 3,
                'descricao': 'Performance qualificada',
                'metrica': None,  # Vague term without metric
                'sla': None,
                'aceite': 'Validação',
                'grounding': []
            }
        ]
        
        validated = self.generator._validate_and_mark_requirements(requirements)
        
        print(f"[DEBUG_LOG] Validated requirements with vague terms:")
        for req in validated:
            print(f"[DEBUG_LOG] Req {req['id']}: needs_input={req.get('needs_input')}, missing={req.get('missing')}")
        
        # All should be marked as needing input due to vague terms without metrics
        self.assertTrue(validated[0]['needs_input'], "Req with 'rápido' and 'eficiente' should need input")
        self.assertTrue(validated[1]['needs_input'], "Req with 'adequada' and 'apropriada' should need input")
        self.assertTrue(validated[2]['needs_input'], "Req with 'qualificada' should need input")
        
        # All should have 'métrica' in missing
        self.assertIn('métrica', validated[0]['missing'][0], "Should indicate missing metric for vague terms")
    
    def test_validate_requires_acceptance_criteria(self):
        """Test that validation marks requirements without acceptance criteria"""
        print("\n[DEBUG_LOG] Testing validation requires acceptance criteria")
        
        requirements = [
            {
                'id': 1,
                'descricao': 'Sistema com alta disponibilidade',
                'metrica': {'tipo': 'disponibilidade', 'valor': 0.99, 'unidade': 'proporção'},
                'sla': None,
                'aceite': '',  # Missing aceite
                'grounding': []
            },
            {
                'id': 2,
                'descricao': 'Capacidade de 100 usuários',
                'metrica': {'tipo': 'capacidade', 'valor': 100, 'unidade': 'usuários'},
                'sla': None,
                'aceite': 'curto',  # Too short (< 10 chars)
                'grounding': []
            }
        ]
        
        validated = self.generator._validate_and_mark_requirements(requirements)
        
        print(f"[DEBUG_LOG] Validated requirements without proper aceite:")
        for req in validated:
            print(f"[DEBUG_LOG] Req {req['id']}: needs_input={req.get('needs_input')}, missing={req.get('missing')}")
        
        # Both should be marked as needing input due to missing/insufficient aceite
        self.assertTrue(validated[0]['needs_input'], "Req without aceite should need input")
        self.assertTrue(validated[1]['needs_input'], "Req with short aceite should need input")
        self.assertIn('aceite', validated[0]['missing'][0], "Should indicate missing acceptance criteria")
        self.assertIn('aceite', validated[1]['missing'][0], "Should indicate missing acceptance criteria")
    
    def test_enhanced_defaults_have_complete_structure(self):
        """Test that enhanced default requirements have complete structure"""
        print("\n[DEBUG_LOG] Testing enhanced default requirements structure")
        
        defaults = self.generator._default_requirements_enhanced("Sistema de gestão de frotas")
        
        print(f"[DEBUG_LOG] Enhanced defaults count: {len(defaults)}")
        
        # All defaults should have complete structure
        for req in defaults:
            print(f"[DEBUG_LOG] Default req {req['id']}: has_metric={req.get('metrica') is not None}, "
                  f"has_aceite={len(req.get('aceite', '')) > 10}, needs_input={req.get('needs_input')}")
            
            self.assertIsNotNone(req.get('descricao'), f"Req {req['id']} should have descricao")
            self.assertIsNotNone(req.get('metrica'), f"Req {req['id']} should have metrica")
            self.assertIsNotNone(req.get('aceite'), f"Req {req['id']} should have aceite")
            self.assertFalse(req.get('needs_input', True), f"Req {req['id']} should not need input")
            self.assertEqual(len(req.get('missing', ['something'])), 0, f"Req {req['id']} should have no missing items")
            
            # Check metric structure
            if req['metrica']:
                self.assertIn('tipo', req['metrica'], f"Req {req['id']} metric should have tipo")
                self.assertIn('valor', req['metrica'], f"Req {req['id']} metric should have valor")
                self.assertIn('unidade', req['metrica'], f"Req {req['id']} metric should have unidade")
    
    def test_domain_detection_aviation(self):
        """Test that aviation domain is properly detected"""
        print("\n[DEBUG_LOG] Testing aviation domain detection")
        
        necessity = "Sistema de gestão de manutenção aeronáutica para frota de aeronaves"
        context = "Conformidade com RBAC 135 e requisitos ANAC para manutenção de aeronaves"
        
        domain_hint = self.generator._detect_domain(necessity, context)
        
        print(f"[DEBUG_LOG] Domain hint: {domain_hint[:100] if domain_hint else 'None'}")
        
        self.assertIsNotNone(domain_hint, "Should detect domain")
        self.assertIn('Aviação', domain_hint, "Should identify aviation domain")
        self.assertIn('AOG', domain_hint, "Should mention AOG for aviation")
        self.assertIn('RBAC', domain_hint, "Should mention RBAC for aviation")
        self.assertIn('MEL', domain_hint, "Should mention MEL for aviation")
    
    def test_domain_detection_it(self):
        """Test that IT domain is properly detected"""
        print("\n[DEBUG_LOG] Testing IT domain detection")
        
        necessity = "Sistema de software para gestão de banco de dados"
        context = "Aplicação web com servidores em nuvem"
        
        domain_hint = self.generator._detect_domain(necessity, context)
        
        print(f"[DEBUG_LOG] Domain hint: {domain_hint[:100] if domain_hint else 'None'}")
        
        self.assertIsNotNone(domain_hint, "Should detect domain")
        self.assertIn('Tecnologia da Informação', domain_hint, "Should identify IT domain")
        self.assertIn('Disponibilidade', domain_hint, "Should mention availability for IT")
        self.assertIn('SLA', domain_hint, "Should mention SLA for IT")

if __name__ == '__main__':
    unittest.main()
