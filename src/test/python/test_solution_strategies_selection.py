"""
Test strategy selection functionality
Tests that user can select strategies by number or title and advance to next stage
"""
import unittest
import sys
import os
import json

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.config.FlaskConfig import create_api
from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.ConversationModels import Conversation, Message
from domain.repositories.ConversationRepository import ConversationRepo, MessageRepo

class TestSolutionStrategiesSelection(unittest.TestCase):
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
    
    def tearDown(self):
        """Clean up after tests"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        
        # Clean environment variables
        for key in ['OPENAI_API_KEY', 'SECRET_KEY', 'DATABASE_URL']:
            if key in os.environ:
                del os.environ[key]
    
    def test_strategy_selection_by_number(self):
        """Test that user can select strategy by number and advance to pca stage"""
        print("[DEBUG_LOG] Testing strategy selection by number")
        
        with self.app.app_context():
            # Create a test conversation
            response = self.client.post('/api/etp-dynamic/new')
            self.assertEqual(response.status_code, 201)
            data = response.get_json()
            session_id = data['session_id']
            
            print(f"[DEBUG_LOG] Created session: {session_id}")
            
            # Simulate having strategies stored (mock the stage)
            from domain.dto.EtpOrm import EtpSession
            session = db.session.get(EtpSession, session_id)
            
            # Set up session state with strategies
            test_strategies = [
                {
                    "titulo": "Compra Direta",
                    "quando_indicado": "Propriedade permanente",
                    "vantagens": ["Propriedade definitiva"],
                    "riscos": ["Alto investimento"],
                    "pontos_de_requisito_afetados": [1, 2]
                },
                {
                    "titulo": "Outsourcing Integral",
                    "quando_indicado": "Gestão especializada",
                    "vantagens": ["Foco no core business"],
                    "riscos": ["Dependência"],
                    "pontos_de_requisito_afetados": [3, 4]
                }
            ]
            
            answers = session.get_answers() or {}
            answers['strategies'] = test_strategies
            session.set_answers(answers)
            session.conversation_stage = 'solution_strategies'
            session.necessity = 'Contratação de serviço de TI'
            db.session.commit()
            
            print(f"[DEBUG_LOG] Session state: stage={session.conversation_stage}, strategies={len(test_strategies)}")
            
            # Send selection by number "2"
            response = self.client.post(
                '/api/etp-dynamic/conversation',
                json={
                    'session_id': session_id,
                    'message': '2'
                },
                content_type='application/json'
            )
            
            print(f"[DEBUG_LOG] Response status: {response.status_code}")
            self.assertEqual(response.status_code, 200)
            
            result = response.get_json()
            print(f"[DEBUG_LOG] Response: {json.dumps(result, indent=2)}")
            
            self.assertTrue(result.get('success'))
            
            # Refresh session to check updated state
            db.session.refresh(session)
            updated_answers = session.get_answers()
            
            print(f"[DEBUG_LOG] Updated stage: {session.conversation_stage}")
            print(f"[DEBUG_LOG] Selected strategies: {updated_answers.get('selected_strategies')}")
            
            # Verify that strategy was selected
            self.assertIn('selected_strategies', updated_answers)
            selected = updated_answers['selected_strategies']
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]['titulo'], 'Outsourcing Integral')
            
            # Verify stage advanced to 'pca'
            self.assertEqual(session.conversation_stage, 'pca')
    
    def test_strategy_no_loop_on_invalid_input(self):
        """Test that invalid input doesn't repeat full strategy list"""
        print("[DEBUG_LOG] Testing no loop on invalid input")
        
        with self.app.app_context():
            # Create a test conversation
            response = self.client.post('/api/etp-dynamic/new')
            data = response.get_json()
            session_id = data['session_id']
            
            # Set up session with strategies
            from domain.dto.EtpOrm import EtpSession
            session = db.session.get(EtpSession, session_id)
            
            test_strategies = [
                {"titulo": "Compra Direta", "quando_indicado": "Test", "vantagens": [], "riscos": []},
                {"titulo": "Locação", "quando_indicado": "Test", "vantagens": [], "riscos": []}
            ]
            
            answers = {'strategies': test_strategies}
            session.set_answers(answers)
            session.conversation_stage = 'solution_strategies'
            session.necessity = 'Test'
            db.session.commit()
            
            # Send neutral message
            response = self.client.post(
                '/api/etp-dynamic/conversation',
                json={
                    'session_id': session_id,
                    'message': 'ola'
                },
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            
            print(f"[DEBUG_LOG] Response message: {result.get('ai_response')}")
            
            # Verify brief guidance message (not full list)
            ai_response = result.get('ai_response', '')
            self.assertIn('estratégia', ai_response.lower())
            # Should be brief (less than 200 chars)
            self.assertLess(len(ai_response), 200)
            
            # Should stay in same stage
            db.session.refresh(session)
            self.assertEqual(session.conversation_stage, 'solution_strategies')

if __name__ == '__main__':
    unittest.main()
