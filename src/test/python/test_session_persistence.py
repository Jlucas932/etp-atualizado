"""Test session persistence for conversation_stage and requirements in answers."""
import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from datetime import datetime
from application.config.FlaskConfig import create_api
from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpOrm import EtpSession


class TestSessionPersistence(unittest.TestCase):
    """Test EtpSession model for proper persistence of conversation_stage and answers."""
    
    def setUp(self):
        """Set up test fixtures"""
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret_key'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        self.app = create_api()
        self.app.config['TESTING'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create all tables
        db.create_all()
        
    def test_conversation_stage_default(self):
        """Test that conversation_stage has default value 'collect_need'"""
        session = EtpSession(session_id='TST001')
        db.session.add(session)
        db.session.commit()
        
        # Retrieve from database
        retrieved = EtpSession.query.filter_by(session_id='TST001').first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.conversation_stage, 'collect_need')
        
    def test_session_stage_and_requirements_persist(self):
        """Test that conversation_stage and requirements persist correctly"""
        # Create session with initial stage
        session = EtpSession(session_id='TST123', conversation_stage='collect_need', answers={})
        db.session.add(session)
        db.session.commit()
        
        # Update requirements and stage
        session.set_requirements(['R1', 'R2'])
        session.conversation_stage = 'legal_norms'
        db.session.commit()
        
        # Retrieve from database
        session2 = EtpSession.query.filter_by(session_id='TST123').first()
        self.assertIsNotNone(session2)
        self.assertEqual(session2.conversation_stage, 'legal_norms')
        self.assertEqual(session2.get_requirements(), ['R1', 'R2'])
        
    def test_get_requirements_from_answers(self):
        """Test that get_requirements() reads from answers['requirements']"""
        session = EtpSession(session_id='TST200', answers={'requirements': ['Req1', 'Req2', 'Req3']})
        db.session.add(session)
        db.session.commit()
        
        retrieved = EtpSession.query.filter_by(session_id='TST200').first()
        reqs = retrieved.get_requirements()
        self.assertEqual(reqs, ['Req1', 'Req2', 'Req3'])
        
    def test_set_requirements_updates_answers(self):
        """Test that set_requirements() persists in answers['requirements']"""
        session = EtpSession(session_id='TST300', answers={'other_data': 'keep_me'})
        db.session.add(session)
        db.session.commit()
        
        # Update requirements
        session.set_requirements(['NewR1', 'NewR2'])
        db.session.commit()
        
        # Verify requirements are in answers
        retrieved = EtpSession.query.filter_by(session_id='TST300').first()
        self.assertEqual(retrieved.get_requirements(), ['NewR1', 'NewR2'])
        # Verify other data is preserved
        self.assertEqual(retrieved.answers.get('other_data'), 'keep_me')
        
    def test_updated_at_changes_on_set_requirements(self):
        """Test that updated_at changes when set_requirements() is called"""
        session = EtpSession(session_id='TST400')
        db.session.add(session)
        db.session.commit()
        
        original_updated_at = session.updated_at
        
        # Wait a moment and update requirements
        import time
        time.sleep(0.1)
        session.set_requirements(['R1'])
        db.session.commit()
        
        # Verify updated_at changed
        retrieved = EtpSession.query.filter_by(session_id='TST400').first()
        self.assertGreater(retrieved.updated_at, original_updated_at)
        
    def test_answers_confirmed_requirements_persist(self):
        """Test that answers.confirmed_requirements is saved when user confirms"""
        session = EtpSession(session_id='TST500')
        db.session.add(session)
        db.session.commit()
        
        # Simulate user confirmation
        session.answers = {'confirmed_requirements': True, 'requirements': ['R1', 'R2']}
        session.conversation_stage = 'legal_norms'
        db.session.commit()
        
        # Verify persistence
        retrieved = EtpSession.query.filter_by(session_id='TST500').first()
        self.assertTrue(retrieved.answers.get('confirmed_requirements'))
        self.assertEqual(retrieved.conversation_stage, 'legal_norms')
        
    def tearDown(self):
        """Clean up after tests"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        
        # Clean environment variables
        for key in ['OPENAI_API_KEY', 'SECRET_KEY', 'DATABASE_URL']:
            if key in os.environ:
                del os.environ[key]


if __name__ == '__main__':
    unittest.main()
