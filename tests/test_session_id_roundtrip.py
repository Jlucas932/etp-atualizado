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


class TestSessionIdRoundtrip(unittest.TestCase):
    """Test that session_id is properly synchronized between client and server"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Save original env vars
        self.original_provider = os.environ.get('ETP_AI_PROVIDER')
        self.original_api_key = os.environ.get('OPENAI_API_KEY')
        
        # Set required env vars BEFORE creating app
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret_key_for_testing'
        os.environ['ETP_AI_PROVIDER'] = 'fallback'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
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
    
    def test_session_roundtrip_conversation(self):
        """Test that /conversation endpoint respects client's session_id"""
        # Cliente cria um ID e espera que o servidor o respeite
        sid = 'sid-roundtrip-123'
        
        response = self.client.post(
            '/api/etp-dynamic/conversation',
            json={
                'session_id': sid,
                'message': 'Contratação de suporte de TI'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Verify response structure
        self.assertIsNotNone(data)
        self.assertTrue(data.get('success'), f"Expected success=True, got: {data}")
        
        # Server must respect the client's session_id
        self.assertEqual(data.get('session_id'), sid, 
                        f"Server should return the same session_id. Expected: {sid}, Got: {data.get('session_id')}")
        
        # Verify session was created in database with exact ID
        s = EtpSession.query.filter_by(session_id=sid).first()
        self.assertIsNotNone(s, "Session should exist in database")
        self.assertIn(s.conversation_stage, ['collect_need', 'review_requirements', 'suggest_requirements', 'legal_norms'],
                     f"Session should have valid stage: {s.conversation_stage}")
    
    def test_session_created_when_not_provided(self):
        """Test that server creates new session_id when client doesn't provide one"""
        response = self.client.post(
            '/api/etp-dynamic/conversation',
            json={
                'message': 'Aquisição de notebooks'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        self.assertTrue(data.get('success'))
        self.assertIsNotNone(data.get('session_id'), "Server should generate session_id")
        
        # Verify session exists in database
        generated_sid = data.get('session_id')
        s = EtpSession.query.filter_by(session_id=generated_sid).first()
        self.assertIsNotNone(s, "Generated session should exist in database")
    
    def test_session_id_stable_across_requests(self):
        """Test that session_id remains stable across multiple requests"""
        sid = 'sid-stable-456'
        
        # First request
        response1 = self.client.post(
            '/api/etp-dynamic/conversation',
            json={
                'session_id': sid,
                'message': 'Primeira mensagem'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response1.status_code, 200)
        data1 = response1.get_json()
        self.assertEqual(data1.get('session_id'), sid)
        
        # Second request with same session_id
        response2 = self.client.post(
            '/api/etp-dynamic/conversation',
            json={
                'session_id': sid,
                'message': 'Segunda mensagem'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response2.status_code, 200)
        data2 = response2.get_json()
        self.assertEqual(data2.get('session_id'), sid, 
                        "Session ID should remain stable across requests")
        
        # Verify only one session exists
        sessions = EtpSession.query.filter_by(session_id=sid).all()
        self.assertEqual(len(sessions), 1, "Should have exactly one session")


if __name__ == '__main__':
    unittest.main()
