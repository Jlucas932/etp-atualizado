"""
Test answers coercion in EtpSession to prevent 'str' object does not support item assignment bug.
"""
import json
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpOrm import EtpSession
from application.config.FlaskConfig import create_api


def test_answers_string_is_coerced_to_dict():
    """Test that answers stored as string is coerced to dict by get_answers()"""
    # Use SQLite for testing
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_api()
    with app.app_context():
        # Create tables if needed
        db.create_all()
        
        # Create session with answers as string (simulating legacy data)
        session = EtpSession(
            session_id='TEST_COERCE_1',
            conversation_stage='collect_need',
            status='active'
        )
        # Manually set answers as string to simulate legacy data
        session.answers = json.dumps({"foo": "bar"})
        db.session.add(session)
        db.session.commit()
        
        # Retrieve and verify coercion
        session2 = EtpSession.query.filter_by(session_id='TEST_COERCE_1').first()
        assert session2 is not None, "Session not found"
        
        # get_answers should normalize string to dict
        answers = session2.get_answers()
        assert isinstance(answers, dict), f"Expected dict, got {type(answers)}"
        assert answers.get('foo') == 'bar', "Content should be preserved"
        
        # After normalization, answers should be dict
        assert isinstance(session2.answers, dict), "answers should be normalized to dict"
        
        # Clean up
        db.session.delete(session2)
        db.session.commit()
        print("✓ test_answers_string_is_coerced_to_dict passed")


def test_set_requirements_does_not_fail_on_string_answers():
    """Test that set_requirements works even if answers was a string"""
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_api()
    with app.app_context():
        db.create_all()
        
        # Create session with answers as string
        session = EtpSession(
            session_id='TEST_COERCE_2',
            conversation_stage='suggest_requirements',
            status='active'
        )
        # Simulate legacy string data
        session.answers = json.dumps({})
        db.session.add(session)
        db.session.commit()
        
        # Retrieve and use set_requirements
        session2 = EtpSession.query.filter_by(session_id='TEST_COERCE_2').first()
        
        # This should NOT raise "str object does not support item assignment"
        requirements = [
            {'id': 'R1', 'text': 'Requisito 1'},
            {'id': 'R2', 'text': 'Requisito 2'}
        ]
        session2.set_requirements(requirements)
        db.session.commit()
        
        # Verify requirements were stored
        session3 = EtpSession.query.filter_by(session_id='TEST_COERCE_2').first()
        stored_reqs = session3.get_requirements()
        assert isinstance(stored_reqs, list), "Requirements should be list"
        assert len(stored_reqs) == 2, "Should have 2 requirements"
        assert stored_reqs[0]['id'] == 'R1', "First requirement should be R1"
        
        # Clean up
        db.session.delete(session3)
        db.session.commit()
        print("✓ test_set_requirements_does_not_fail_on_string_answers passed")


def test_answers_none_is_coerced_to_dict():
    """Test that None answers is coerced to empty dict"""
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_api()
    with app.app_context():
        db.create_all()
        
        session = EtpSession(
            session_id='TEST_COERCE_3',
            conversation_stage='collect_need',
            status='active'
        )
        # Explicitly set to None
        session.answers = None
        db.session.add(session)
        db.session.commit()
        
        session2 = EtpSession.query.filter_by(session_id='TEST_COERCE_3').first()
        answers = session2.get_answers()
        assert isinstance(answers, dict), "None should be coerced to dict"
        assert len(answers) == 0, "Should be empty dict"
        
        # Clean up
        db.session.delete(session2)
        db.session.commit()
        print("✓ test_answers_none_is_coerced_to_dict passed")


if __name__ == '__main__':
    print("Running answers coercion tests...")
    try:
        test_answers_string_is_coerced_to_dict()
        test_set_requirements_does_not_fail_on_string_answers()
        test_answers_none_is_coerced_to_dict()
        print("\n✅ All answers coercion tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
