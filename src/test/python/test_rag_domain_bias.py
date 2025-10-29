"""
Test RAG domain bias - verify that domain-specific terms appear in generated requirements.
"""
import unittest
import sys
import os
import json

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.ai.generator import OpenAIGenerator

class TestRAGDomainBias(unittest.TestCase):
    """Test that domain-specific terms are properly injected into requirements"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock OpenAI client that returns aviation-themed requirements
        class MockOpenAIClient:
            def __init__(self, response_content):
                self.response_content = response_content
            
            class ChatCompletions:
                def __init__(self, parent):
                    self.parent = parent
                
                def create(self, **kwargs):
                    class MockChoice:
                        def __init__(self, content):
                            self.content = content
                        class MockMessage:
                            def __init__(self, content):
                                self.content = content
                        @property
                        def message(self):
                            return self.MockMessage(self.content)
                    
                    class MockResponse:
                        def __init__(self, content):
                            self.choices = [MockChoice(content)]
                    
                    return MockResponse(self.parent.response_content)
            
            @property
            def chat(self):
                parent = self
                class Chat:
                    completions = MockOpenAIClient.ChatCompletions(parent)
                return Chat()
        
        # Aviation domain mock response
        self.aviation_response = json.dumps({
            "requirements": [
                {
                    "id": 1,
                    "descricao": "Tempo de resposta a ocorrências AOG (Aircraft On Ground)",
                    "metrica": {"tipo": "tempo_resposta_aog", "valor": 4, "unidade": "horas"},
                    "sla": {"tipo": "resposta_aog", "valor": 4, "unidade": "horas", "janela": "24x7"},
                    "aceite": "Relatórios mensais demonstrando 95% dos AOGs atendidos em ≤4h",
                    "opcoes": [
                        {"valor": 2, "unidade": "horas"},
                        {"valor": 4, "unidade": "horas"},
                        {"valor": 8, "unidade": "horas"}
                    ],
                    "grounding": ["chunk_1"]
                },
                {
                    "id": 2,
                    "descricao": "Gestão de MEL (Minimum Equipment List) conforme RBAC 91",
                    "metrica": {"tipo": "conformidade_mel", "valor": 100, "unidade": "%"},
                    "sla": None,
                    "aceite": "Auditoria trimestral de conformidade MEL com 100% de aderência",
                    "opcoes": [],
                    "grounding": ["chunk_2"]
                },
                {
                    "id": 3,
                    "descricao": "Rastreabilidade de componentes críticos com part-number e serial",
                    "metrica": {"tipo": "rastreabilidade", "valor": 100, "unidade": "%"},
                    "sla": None,
                    "aceite": "Amostragem trimestral (n≥30) com 0 inconformidades documentais",
                    "opcoes": [],
                    "grounding": ["chunk_3"]
                },
                {
                    "id": 4,
                    "descricao": "Implementação de SMS (Safety Management System)",
                    "metrica": {"tipo": "implementacao_sms", "valor": 100, "unidade": "%"},
                    "sla": {"tipo": "prazo_implementacao", "valor": 180, "unidade": "dias"},
                    "aceite": "Certificação SMS conforme RBAC 135 e auditoria ANAC aprovada",
                    "opcoes": [],
                    "grounding": ["chunk_4"]
                },
                {
                    "id": 5,
                    "descricao": "Relatórios FDM/FOQA (Flight Data Monitoring)",
                    "metrica": {"tipo": "cobertura_voos", "valor": 100, "unidade": "%"},
                    "sla": None,
                    "aceite": "Relatórios mensais de FDM para 100% dos voos com análise de tendências",
                    "opcoes": [],
                    "grounding": ["chunk_5"]
                }
            ],
            "observacoes": ["Normas aplicadas: RBAC 91, 135, 145", "Domínio: Aviação Civil"]
        })
        
        self.mock_client_aviation = MockOpenAIClient(self.aviation_response)
        self.generator_aviation = OpenAIGenerator(self.mock_client_aviation, model="gpt-4")
    
    def test_aviation_domain_terms_presence(self):
        """Test that aviation-specific terms appear in ≥60% of applicable requirements"""
        print("\n[DEBUG_LOG] Testing aviation domain terms presence in requirements")
        
        # Aviation-specific terms to check
        aviation_terms = [
            'aog', 'aircraft on ground',
            'mel', 'minimum equipment list',
            'rbac', 'anac',
            'aeronave', 'aeronavegabilidade',
            'sms', 'safety management',
            'fdm', 'foqa', 'flight data',
            'part-number', 'serial',
            'camo', 'parte 145',
            'manutenção aeronáutica'
        ]
        
        necessity = "Sistema de gestão de manutenção aeronáutica para frota de aeronaves"
        context = [
            {'id': 'chunk_1', 'text': 'Conformidade RBAC 135 para operações de táxi aéreo'},
            {'id': 'chunk_2', 'text': 'MEL deve ser gerido conforme RBAC 91'},
            {'id': 'chunk_3', 'text': 'Rastreabilidade de componentes críticos'},
            {'id': 'chunk_4', 'text': 'SMS conforme ANAC'},
            {'id': 'chunk_5', 'text': 'FDM para monitoramento de dados de voo'}
        ]
        
        # Generate requirements
        result = self.generator_aviation.generate('suggest_requirements', necessity, context, {})
        requirements = result.get('requirements', [])
        
        print(f"[DEBUG_LOG] Generated {len(requirements)} requirements")
        
        # Count requirements with domain-specific terms
        requirements_with_terms = 0
        for req in requirements:
            descricao = req.get('descricao', '').lower()
            aceite = req.get('aceite', '').lower()
            metrica_tipo = req.get('metrica', {}).get('tipo', '').lower() if req.get('metrica') else ''
            sla_tipo = req.get('sla', {}).get('tipo', '').lower() if req.get('sla') else ''
            
            full_text = f"{descricao} {aceite} {metrica_tipo} {sla_tipo}"
            
            has_term = any(term in full_text for term in aviation_terms)
            
            if has_term:
                requirements_with_terms += 1
                matched_terms = [term for term in aviation_terms if term in full_text]
                print(f"[DEBUG_LOG] Req {req.get('id')}: Has aviation terms: {matched_terms[:3]}")
            else:
                print(f"[DEBUG_LOG] Req {req.get('id')}: NO aviation terms found")
        
        # Calculate percentage
        if len(requirements) > 0:
            percentage = (requirements_with_terms / len(requirements)) * 100
            print(f"[DEBUG_LOG] Domain term coverage: {requirements_with_terms}/{len(requirements)} = {percentage:.1f}%")
            
            # Assert ≥60% have domain-specific terms
            self.assertGreaterEqual(percentage, 60.0, 
                f"At least 60% of requirements should contain domain-specific aviation terms. Got {percentage:.1f}%")
        else:
            self.fail("No requirements generated")
    
    def test_aviation_domain_hint_injection(self):
        """Test that domain hint is properly generated for aviation necessity"""
        print("\n[DEBUG_LOG] Testing aviation domain hint injection")
        
        necessity = "Sistema de manutenção de aeronaves e gestão de aeronavegabilidade"
        context = "Conformidade com RBAC 135 e requisitos ANAC"
        
        domain_hint = self.generator_aviation._detect_domain(necessity, context)
        
        print(f"[DEBUG_LOG] Domain hint length: {len(domain_hint)}")
        print(f"[DEBUG_LOG] Domain hint preview: {domain_hint[:200]}")
        
        # Check that hint contains aviation-specific guidance
        self.assertIn('AOG', domain_hint, "Hint should mention AOG")
        self.assertIn('aeronavegabilidade', domain_hint, "Hint should mention aeronavegabilidade")
        self.assertIn('MEL', domain_hint, "Hint should mention MEL")
        self.assertIn('RBAC', domain_hint, "Hint should mention RBAC")
        self.assertIn('SMS', domain_hint, "Hint should mention SMS")
        self.assertIn('rastreabilidade', domain_hint, "Hint should mention rastreabilidade")
    
    def test_non_aviation_domain_no_aviation_terms(self):
        """Test that non-aviation domains don't get aviation-specific terms"""
        print("\n[DEBUG_LOG] Testing that non-aviation domains don't get aviation terms")
        
        # IT domain mock response
        it_response = json.dumps({
            "requirements": [
                {
                    "id": 1,
                    "descricao": "Disponibilidade do sistema",
                    "metrica": {"tipo": "uptime", "valor": 0.999, "unidade": "proporção"},
                    "sla": {"tipo": "disponibilidade", "valor": 99.9, "unidade": "%", "janela": "24x7"},
                    "aceite": "Monitoramento contínuo com 99.9% uptime",
                    "opcoes": [],
                    "grounding": []
                }
            ],
            "observacoes": ["Domínio: TI"]
        })
        
        class MockITClient:
            class ChatCompletions:
                def create(self, **kwargs):
                    class MockChoice:
                        class MockMessage:
                            content = it_response
                        message = MockMessage()
                    class MockResponse:
                        choices = [MockChoice()]
                    return MockResponse()
            
            chat = type('Chat', (), {'completions': ChatCompletions()})()
        
        generator_it = OpenAIGenerator(MockITClient(), model="gpt-4")
        
        necessity = "Sistema de gestão de banco de dados"
        context = [{'id': 'c1', 'text': 'Sistema web com alta disponibilidade'}]
        
        result = generator_it.generate('suggest_requirements', necessity, context, {})
        requirements = result.get('requirements', [])
        
        aviation_terms = ['aog', 'mel', 'rbac', 'aeronave', 'anac']
        
        # None of the requirements should have aviation terms
        for req in requirements:
            descricao = req.get('descricao', '').lower()
            has_aviation = any(term in descricao for term in aviation_terms)
            
            print(f"[DEBUG_LOG] IT Req {req.get('id')}: descricao='{descricao[:50]}', has_aviation={has_aviation}")
            
            self.assertFalse(has_aviation, 
                f"IT requirements should not contain aviation terms. Found in: {descricao}")
    
    def test_domain_hint_for_it(self):
        """Test that IT domain gets appropriate hints"""
        print("\n[DEBUG_LOG] Testing IT domain hint")
        
        necessity = "Sistema de software para aplicação web"
        context = "Servidor em nuvem com banco de dados PostgreSQL"
        
        domain_hint = self.generator_aviation._detect_domain(necessity, context)
        
        print(f"[DEBUG_LOG] IT Domain hint preview: {domain_hint[:200]}")
        
        # Should detect IT domain
        if domain_hint:  # IT domain detected
            self.assertIn('Tecnologia', domain_hint, "Should mention Tecnologia")
            self.assertIn('Disponibilidade', domain_hint, "Should mention Disponibilidade")
            self.assertIn('SLA', domain_hint, "Should mention SLA")
            # Should NOT have aviation terms
            self.assertNotIn('AOG', domain_hint, "IT domain should not mention AOG")
            self.assertNotIn('aeronave', domain_hint, "IT domain should not mention aeronave")
    
    def test_requirements_have_specific_metrics_not_vague(self):
        """Test that generated requirements have specific metrics, not vague terms"""
        print("\n[DEBUG_LOG] Testing that requirements avoid vague terms")
        
        necessity = "Sistema de gestão aeronáutica"
        context = [{'id': 'c1', 'text': 'RBAC 135'}]
        
        result = self.generator_aviation.generate('suggest_requirements', necessity, context, {})
        requirements = result.get('requirements', [])
        
        vague_terms = ['adequado', 'apropriado', 'qualificado', 'suficiente', 'rápido', 'eficiente']
        
        for req in requirements:
            descricao = req.get('descricao', '').lower()
            metrica = req.get('metrica')
            
            # Check for vague terms
            has_vague = any(term in descricao for term in vague_terms)
            has_metric = metrica is not None and metrica.get('valor') is not None
            
            print(f"[DEBUG_LOG] Req {req.get('id')}: has_vague={has_vague}, has_metric={has_metric}")
            
            if has_vague:
                # If vague term present, MUST have a metric to compensate
                self.assertTrue(has_metric, 
                    f"Requirement with vague term '{descricao}' must have a metric")

if __name__ == '__main__':
    unittest.main()
