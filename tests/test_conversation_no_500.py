import os
import sys
import unittest
import json
from datetime import datetime

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from application.config.FlaskConfig import create_api
from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpOrm import EtpSession


class TestConversationNo500(unittest.TestCase):
    """Test that conversation endpoint never returns 500 errors"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Save original env vars
        self.original_provider = os.environ.get('ETP_AI_PROVIDER')
        self.original_api_key = os.environ.get('OPENAI_API_KEY')
        
        # Force fallback mode (no API key)
        os.environ['ETP_AI_PROVIDER'] = 'fallback'
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']
        
        # Set required Flask env vars
        os.environ['SECRET_KEY'] = 'test_secret_key_for_testing'
        
        self.app = create_api()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Create application context
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create tables
        db.create_all()
        
    def tearDown(self):
        """Clean up after tests"""
        # Clean up database
        db.session.remove()
        db.drop_all()
        
        # Pop application context
        self.app_context.pop()
        
        # Restore env vars
        if self.original_provider:
            os.environ['ETP_AI_PROVIDER'] = self.original_provider
        elif 'ETP_AI_PROVIDER' in os.environ:
            del os.environ['ETP_AI_PROVIDER']
            
        if self.original_api_key:
            os.environ['OPENAI_API_KEY'] = self.original_api_key
        
        # Clean up test env vars
        for key in ['SECRET_KEY']:
            if key in os.environ:
                del os.environ[key]
    
    def test_first_message_no_500_with_fallback(self):
        """Test that first message doesn't return 500 even without OpenAI API key"""
        # Create a session
        session = EtpSession(
            user_id=1,
            session_id='TEST_SESSION_NO500',
            status='active',
            conversation_stage='collect_need',
            answers=json.dumps({}),
            created_at=datetime.utcnow()
        )
        db.session.add(session)
        db.session.commit()
        
        # Send first message
        response = self.client.post(
            '/api/etp-dynamic/conversation',
            json={
                'session_id': 'TEST_SESSION_NO500',
                'message': 'Aquisição de notebooks para laboratório de informática'
            },
            content_type='application/json'
        )
        
        # Should return 200, not 500
        self.assertEqual(response.status_code, 200, 
                        f"Expected 200, got {response.status_code}. Response: {response.get_json()}")
        
        data = response.get_json()
        self.assertIsNotNone(data)
        self.assertTrue(data.get('success'), f"Response should have success=True: {data}")
        self.assertIn('ai_response', data, "Response should contain ai_response")
        self.assertIsNotNone(data.get('ai_response'), "ai_response should not be None")
    
    def test_conversation_stage_advances_on_necessity(self):
        """Test that conversation stage advances after necessity is provided"""
        # Create a session
        session = EtpSession(
            user_id=1,
            session_id='TEST_SESSION_STAGE',
            status='active',
            conversation_stage='collect_need',
            answers=json.dumps({}),
            created_at=datetime.utcnow()
        )
        db.session.add(session)
        db.session.commit()
        
        # Send necessity message
        response = self.client.post(
            '/api/etp-dynamic/conversation',
            json={
                'session_id': 'TEST_SESSION_STAGE',
                'message': 'Contratação de serviços de limpeza para o prédio administrativo'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Should advance to suggest_requirements or review_requirements
        self.assertIn(data.get('conversation_stage'), 
                     ['suggest_requirements', 'review_requirements', 'legal_norms'],
                     f"Stage should advance from collect_need. Got: {data.get('conversation_stage')}")
    
    def test_multiple_messages_no_500(self):
        """Test that multiple messages never return 500 with fallback"""
        # Create a session
        session = EtpSession(
            user_id=1,
            session_id='TEST_SESSION_MULTI',
            status='active',
            conversation_stage='collect_need',
            answers=json.dumps({}),
            created_at=datetime.utcnow()
        )
        db.session.add(session)
        db.session.commit()
        
        messages = [
            'Aquisição de equipamentos de TI',
            'Pode adicionar mais requisitos',
            'Remover o último requisito'
        ]
        
        for i, msg in enumerate(messages):
            response = self.client.post(
                '/api/etp-dynamic/conversation',
                json={
                    'session_id': 'TEST_SESSION_MULTI',
                    'message': msg
                },
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200, 
                           f"Message {i+1} returned {response.status_code}: {response.get_json()}")
            data = response.get_json()
            self.assertTrue(data.get('success'), 
                          f"Message {i+1} should have success=True: {data}")


if __name__ == '__main__':
    unittest.main()
