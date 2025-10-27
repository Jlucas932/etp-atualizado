"""
Test strategy selection by keyword/title
Tests that user can select strategy by entering part of the title (e.g., "outsourcing")
"""
import unittest
import sys
import os
import json

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.config.FlaskConfig import create_api
from domain.interfaces.dataprovider.DatabaseConfig import db
from adapter.entrypoint.etp.EtpDynamicController import _parse_strategy_selection

class TestStrategyKeywordSelection(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret_key'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        self.app = create_api()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
        
        # Test strategies
        self.test_strategies = [
            {
                "titulo": "Compra Direta",
                "quando_indicado": "Propriedade permanente",
                "vantagens": ["Propriedade definitiva"],
                "riscos": ["Alto investimento"]
            },
            {
                "titulo": "Outsourcing Integral",
                "quando_indicado": "Gestão especializada",
                "vantagens": ["Foco no core business"],
                "riscos": ["Dependência"]
            },
            {
                "titulo": "Locação com Opção de Compra",
                "quando_indicado": "Necessidade temporária",
                "vantagens": ["Menor investimento inicial"],
                "riscos": ["Custo recorrente"]
            }
        ]
    
    def tearDown(self):
        """Clean up after tests"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        
        # Clean environment variables
        for key in ['OPENAI_API_KEY', 'SECRET_KEY', 'DATABASE_URL']:
            if key in os.environ:
                del os.environ[key]
    
    def test_parse_strategy_by_keyword_outsourcing(self):
        """Test parsing strategy selection by keyword 'outsourcing'"""
        print("[DEBUG_LOG] Testing _parse_strategy_selection with 'outsourcing'")
        
        result = _parse_strategy_selection("outsourcing", self.test_strategies)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['titulo'], "Outsourcing Integral")
        
        print(f"[DEBUG_LOG] Selected: {result[0]['titulo']}")
    
    def test_parse_strategy_by_keyword_locacao(self):
        """Test parsing strategy selection by keyword 'locação'"""
        print("[DEBUG_LOG] Testing _parse_strategy_selection with 'locação'")
        
        result = _parse_strategy_selection("locação", self.test_strategies)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['titulo'], "Locação com Opção de Compra")
        
        print(f"[DEBUG_LOG] Selected: {result[0]['titulo']}")
    
    def test_parse_strategy_by_partial_title(self):
        """Test parsing strategy selection by partial title"""
        print("[DEBUG_LOG] Testing _parse_strategy_selection with partial title")
        
        result = _parse_strategy_selection("compra", self.test_strategies)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['titulo'], "Compra Direta")
        
        print(f"[DEBUG_LOG] Selected: {result[0]['titulo']}")
    
    def test_parse_strategy_by_number(self):
        """Test parsing strategy selection by number"""
        print("[DEBUG_LOG] Testing _parse_strategy_selection with number")
        
        result = _parse_strategy_selection("3", self.test_strategies)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['titulo'], "Locação com Opção de Compra")
        
        print(f"[DEBUG_LOG] Selected by number 3: {result[0]['titulo']}")
    
    def test_parse_strategy_multiple_selection(self):
        """Test parsing multiple strategy selections"""
        print("[DEBUG_LOG] Testing _parse_strategy_selection with '1 e 3'")
        
        result = _parse_strategy_selection("1 e 3", self.test_strategies)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['titulo'], "Compra Direta")
        self.assertEqual(result[1]['titulo'], "Locação com Opção de Compra")
        
        print(f"[DEBUG_LOG] Selected multiple: {[s['titulo'] for s in result]}")
    
    def test_parse_strategy_invalid_input(self):
        """Test that invalid input returns None"""
        print("[DEBUG_LOG] Testing _parse_strategy_selection with invalid input")
        
        result = _parse_strategy_selection("xyz123", self.test_strategies)
        
        self.assertIsNone(result)
        print("[DEBUG_LOG] Invalid input correctly returned None")
    
    def test_parse_strategy_empty_strategies(self):
        """Test that empty strategies list returns None"""
        print("[DEBUG_LOG] Testing _parse_strategy_selection with empty strategies")
        
        result = _parse_strategy_selection("outsourcing", [])
        
        self.assertIsNone(result)
        print("[DEBUG_LOG] Empty strategies correctly returned None")
    
    def test_integration_keyword_selection(self):
        """Integration test: full flow with keyword selection"""
        print("[DEBUG_LOG] Testing full integration with keyword selection")
        
        with self.app.app_context():
            # Create a test conversation
            response = self.client.post('/api/etp-dynamic/new')
            self.assertEqual(response.status_code, 201)
            data = response.get_json()
            session_id = data['session_id']
            
            # Set up session with strategies
            from domain.dto.EtpOrm import EtpSession
            session = db.session.get(EtpSession, session_id)
            
            answers = session.get_answers() or {}
            answers['strategies'] = self.test_strategies
            session.set_answers(answers)
            session.conversation_stage = 'solution_strategies'
            session.necessity = 'Contratação de serviço'
            db.session.commit()
            
            print(f"[DEBUG_LOG] Session prepared with {len(self.test_strategies)} strategies")
            
            # Send keyword selection "outsourcing"
            response = self.client.post(
                '/api/etp-dynamic/conversation',
                json={
                    'session_id': session_id,
                    'message': 'outsourcing'
                },
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            
            print(f"[DEBUG_LOG] Response: {result.get('ai_response')}")
            
            # Refresh session
            db.session.refresh(session)
            updated_answers = session.get_answers()
            
            # Verify selection
            self.assertIn('selected_strategies', updated_answers)
            selected = updated_answers['selected_strategies']
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]['titulo'], 'Outsourcing Integral')
            
            # Verify stage advanced
            self.assertEqual(session.conversation_stage, 'pca')
            
            print(f"[DEBUG_LOG] Successfully selected '{selected[0]['titulo']}' and advanced to pca")

if __name__ == '__main__':
    unittest.main()
