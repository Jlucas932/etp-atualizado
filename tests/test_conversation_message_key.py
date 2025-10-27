"""
Test that conversation endpoint accepts both 'message' and 'user_message' fields.
"""
import sys
import os
import json

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpOrm import EtpSession
from application.config.FlaskConfig import create_api


def test_conversation_accepts_message_key():
    """Test that /conversation endpoint accepts 'message' field"""
    # Set environment variables
    os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
    os.environ['SECRET_KEY'] = 'test_secret_key'
    
    app = create_api()
    app.config['TESTING'] = True
    client = app.test_client()
    
    with app.app_context():
        db.create_all()
        
        # Create a session
        session = EtpSession(
            session_id='TEST_MSG_1',
            conversation_stage='collect_need',
            status='active',
            answers={}
        )
        db.session.add(session)
        db.session.commit()
        
        # Send message using 'message' key
        response = client.post('/api/etp-dynamic/conversation',
                              json={
                                  'session_id': 'TEST_MSG_1',
                                  'message': 'Aquisição de material de limpeza'
                              },
                              content_type='application/json')
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.get_json()
        assert data is not None, "Response should have JSON data"
        assert data.get('success') is not False, f"Request should not fail: {data.get('error')}"
        
        # Clean up
        session = EtpSession.query.filter_by(session_id='TEST_MSG_1').first()
        if session:
            db.session.delete(session)
            db.session.commit()
    
    # Clean environment
    if 'OPENAI_API_KEY' in os.environ:
        del os.environ['OPENAI_API_KEY']
    if 'SECRET_KEY' in os.environ:
        del os.environ['SECRET_KEY']
    
    print("✓ test_conversation_accepts_message_key passed")


def test_conversation_accepts_user_message_key():
    """Test that /conversation endpoint accepts 'user_message' field"""
    os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
    os.environ['SECRET_KEY'] = 'test_secret_key'
    
    app = create_api()
    app.config['TESTING'] = True
    client = app.test_client()
    
    with app.app_context():
        db.create_all()
        
        # Create a session
        session = EtpSession(
            session_id='TEST_MSG_2',
            conversation_stage='collect_need',
            status='active',
            answers={}
        )
        db.session.add(session)
        db.session.commit()
        
        # Send message using 'user_message' key
        response = client.post('/api/etp-dynamic/conversation',
                              json={
                                  'session_id': 'TEST_MSG_2',
                                  'user_message': 'Contratação de serviços de TI'
                              },
                              content_type='application/json')
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.get_json()
        assert data is not None, "Response should have JSON data"
        assert data.get('success') is not False, f"Request should not fail: {data.get('error')}"
        
        # Clean up
        session = EtpSession.query.filter_by(session_id='TEST_MSG_2').first()
        if session:
            db.session.delete(session)
            db.session.commit()
    
    # Clean environment
    if 'OPENAI_API_KEY' in os.environ:
        del os.environ['OPENAI_API_KEY']
    if 'SECRET_KEY' in os.environ:
        del os.environ['SECRET_KEY']
    
    print("✓ test_conversation_accepts_user_message_key passed")


def test_conversation_rejects_empty_message():
    """Test that /conversation endpoint rejects empty message"""
    os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
    os.environ['SECRET_KEY'] = 'test_secret_key'
    
    app = create_api()
    app.config['TESTING'] = True
    client = app.test_client()
    
    with app.app_context():
        db.create_all()
        
        # Create a session
        session = EtpSession(
            session_id='TEST_MSG_3',
            conversation_stage='collect_need',
            status='active',
            answers={}
        )
        db.session.add(session)
        db.session.commit()
        
        # Send empty message
        response = client.post('/api/etp-dynamic/conversation',
                              json={
                                  'session_id': 'TEST_MSG_3',
                                  'message': ''
                              },
                              content_type='application/json')
        
        assert response.status_code == 400, f"Expected 400 for empty message, got {response.status_code}"
        data = response.get_json()
        assert data.get('success') is False, "Empty message should fail"
        assert 'obrigatória' in data.get('error', '').lower(), "Error should mention required message"
        
        # Clean up
        session = EtpSession.query.filter_by(session_id='TEST_MSG_3').first()
        if session:
            db.session.delete(session)
            db.session.commit()
    
    # Clean environment
    if 'OPENAI_API_KEY' in os.environ:
        del os.environ['OPENAI_API_KEY']
    if 'SECRET_KEY' in os.environ:
        del os.environ['SECRET_KEY']
    
    print("✓ test_conversation_rejects_empty_message passed")


if __name__ == '__main__':
    print("Running conversation message key tests...")
    try:
        test_conversation_accepts_message_key()
        test_conversation_accepts_user_message_key()
        test_conversation_rejects_empty_message()
        print("\n✅ All conversation message key tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
