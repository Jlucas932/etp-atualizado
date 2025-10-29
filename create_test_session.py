#!/usr/bin/env python3
"""Create a test ETP session for testing document generation endpoints"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

from datetime import datetime
from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpOrm import EtpSession
from application.config.FlaskConfig import create_api
import uuid

# Set minimal environment variables
os.environ.setdefault('OPENAI_API_KEY', 'test-key')
os.environ.setdefault('SECRET_KEY', 'test-secret')
os.environ.setdefault('DATABASE_URL', 'postgresql+psycopg2://az_etp_user:az_etp_password_2024@localhost:5432/az_etp_db')

# Create Flask app context
app = create_api()

with app.app_context():
    # Create test session
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    
    session = EtpSession(
        session_id=session_id,
        necessity="Contratação de serviços de manutenção predial para o edifício sede",
        conversation_stage='done',
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Set answers with structured data
    answers = {
        'requirements': [
            'R1 — Serviço de manutenção preventiva e corretiva',
            'R2 — Disponibilidade de equipe técnica especializada',
            'R3 — Fornecimento de materiais e ferramentas'
        ],
        'pca': {
            'present': 'Sim',
            'details': 'Item 15 do PCA 2025'
        },
        'price_research': {
            'method': 'Pesquisa de mercado',
            'supplier_count': 3,
            'evidence_links': ['http://example.com/cotacao1', 'http://example.com/cotacao2']
        },
        'legal_basis': {
            'text': 'Lei 14.133/2021',
            'notes': ['Art. 6º - Contratação direta', 'Fundamentação técnica adequada']
        }
    }
    
    session.set_answers(answers)
    
    db.session.add(session)
    db.session.commit()
    
    print(f"✅ Test session created: {session_id}")
    print(f"📋 Necessity: {session.necessity}")
    print(f"📝 Stage: {session.conversation_stage}")
    print(f"🔢 Requirements: {len(answers['requirements'])}")
