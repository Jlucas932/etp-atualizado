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


class TestAnalyzeResponseRobust(unittest.TestCase):
    """Test that /analyze-response endpoint is resilient and never returns 404"""
    
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
    
    def test_analyze_creates_when_missing(self):
        """Test that /analyze-response creates session when it doesn't exist"""
        sid = 'sid-analyze-new-1'
        
        # Don't create session beforehand - let endpoint handle it
        response = self.client.post(
            '/api/etp-dynamic/analyze-response',
            json={'session_id': sid},
            content_type='application/json'
        )
        
        # Should return 200, not 404
        self.assertEqual(response.status_code, 200, 
                        f"Should return 200, not 404. Got: {response.status_code}")
        
        data = response.get_json()
        self.assertIsNotNone(data)
        self.assertTrue(data.get('success'), f"Should return success=True: {data}")
        self.assertEqual(data.get('session_id'), sid, 
                        f"Should return the provided session_id: {data.get('session_id')}")
        
        # Verify session was created in database
        s = EtpSession.query.filter_by(session_id=sid).first()
        self.assertIsNotNone(s, "Session should have been created")
        self.assertEqual(s.conversation_stage, data.get('conversation_stage'),
                        "Conversation stage should match")
    
    def test_analyze_with_existing_session(self):
        """Test that /analyze-response works correctly with existing session"""
        sid = 'sid-analyze-existing-1'
        
        # Create session beforehand
        session = EtpSession(
            user_id=1,
            session_id=sid,
            status='active',
            conversation_stage='collect_need',
            necessity='Test necessity',
            answers=json.dumps({'requirements': [{'id': 'R1', 'text': 'Test requirement'}]}),
            created_at=datetime.utcnow()
        )
        db.session.add(session)
        db.session.commit()
        
        response = self.client.post(
            '/api/etp-dynamic/analyze-response',
            json={'session_id': sid},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('session_id'), sid)
        self.assertIsNotNone(data.get('analysis'), "Should return analysis object")
        
        # Verify analysis contains expected fields
        analysis = data.get('analysis')
        self.assertIn('has_necessity', analysis)
        self.assertTrue(analysis.get('has_necessity'), "Should detect necessity")
        self.assertIn('requirements_count', analysis)
        self.assertEqual(analysis.get('requirements_count'), 1, "Should count requirements")
    
    def test_analyze_without_session_id(self):
        """Test that /analyze-response handles missing session_id gracefully"""
        # No session_id provided - endpoint should create one
        response = self.client.post(
            '/api/etp-dynamic/analyze-response',
            json={},
            content_type='application/json'
        )
        
        # Should still return 200 with success=True
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        self.assertTrue(data.get('success'), "Should return success=True even without session_id")
        self.assertIsNotNone(data.get('session_id'), "Should generate and return session_id")
        
        # Verify session was created
        generated_sid = data.get('session_id')
        s = EtpSession.query.filter_by(session_id=generated_sid).first()
        self.assertIsNotNone(s, "Should create session in database")
    
    def test_analyze_returns_empty_analysis_for_new_session(self):
        """Test that /analyze-response returns valid empty analysis for new session"""
        sid = 'sid-analyze-empty-1'
        
        response = self.client.post(
            '/api/etp-dynamic/analyze-response',
            json={'session_id': sid},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        self.assertTrue(data.get('success'))
        self.assertIsNotNone(data.get('analysis'))
        
        analysis = data.get('analysis')
        # Should have valid structure even for empty session
        self.assertFalse(analysis.get('has_necessity', True), 
                        "New session should not have necessity")
        self.assertEqual(analysis.get('requirements_count', -1), 0, 
                        "New session should have 0 requirements")
        self.assertEqual(data.get('conversation_stage'), 'collect_need',
                        "New session should start at collect_need stage")
    
    def test_analyze_never_404(self):
        """Test that /analyze-response never returns 404 for any session_id"""
        test_sids = [
            'nonexistent-1',
            'nonexistent-2',
            'random-uuid-xyz-123',
            'test-session-that-does-not-exist'
        ]
        
        for sid in test_sids:
            response = self.client.post(
                '/api/etp-dynamic/analyze-response',
                json={'session_id': sid},
                content_type='application/json'
            )
            
            # Should NEVER return 404
            self.assertNotEqual(response.status_code, 404,
                              f"Should not return 404 for session_id: {sid}")
            self.assertEqual(response.status_code, 200,
                           f"Should return 200 for session_id: {sid}")
            
            data = response.get_json()
            self.assertTrue(data.get('success'),
                          f"Should return success=True for session_id: {sid}")


if __name__ == '__main__':
    unittest.main()
