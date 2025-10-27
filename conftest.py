#!/usr/bin/env python3
"""
Pytest configuration file for AutoDoc-IA tests
"""

import sys
import os
import pytest
import tempfile

# Add src path for imports so tests can find the application modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

@pytest.fixture
def app_ctx():
    """Fixture that provides Flask app context with test database"""
    # Set test environment variables
    os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
    os.environ['SECRET_KEY'] = 'test_secret_key'
    os.environ['EMBEDDINGS_PROVIDER'] = 'openai'
    os.environ['RAG_FAISS_PATH'] = '/tmp/test_faiss'
    
    # Create temporary database for testing
    db_fd, db_path = tempfile.mkstemp()
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
    
    from flask import Flask
    from domain.interfaces.dataprovider.DatabaseConfig import db
    from domain.dto.EtpOrm import EtpSession, EtpDocument
    from domain.dto.UserDto import User
    
    # Create a minimal Flask app for testing
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        # Create only the tables we need for this test
        EtpSession.__table__.create(db.engine, checkfirst=True)
        EtpDocument.__table__.create(db.engine, checkfirst=True)
        User.__table__.create(db.engine, checkfirst=True)
        yield app
        db.session.remove()
        db.drop_all()
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)
    
    # Clean environment variables
    for key in ['OPENAI_API_KEY', 'SECRET_KEY', 'DATABASE_URL', 'EMBEDDINGS_PROVIDER', 'RAG_FAISS_PATH']:
        if key in os.environ:
            del os.environ[key]

@pytest.fixture
def client(app_ctx):
    """Fixture that provides Flask test client with registered blueprints"""
    from domain.interfaces.dataprovider.DatabaseConfig import db
    from adapter.entrypoint.etp.EtpDynamicController import etp_dynamic_bp
    
    # Register the blueprint
    app_ctx.register_blueprint(etp_dynamic_bp, url_prefix='/api/etp-dynamic')
    
    with app_ctx.app_context():
        yield app_ctx.test_client()
