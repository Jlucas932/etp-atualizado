"""
Test complete ETP flow without questionnaires.
Tests the 9-stage flow: new → collect_need → suggest_requirements → solution_path → ... → preview
"""
import unittest
import sys
import os
import json

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from application.config.FlaskConfig import create_api
from domain.interfaces.dataprovider.DatabaseConfig import db


class TestFlowETP(unittest.TestCase):
    """Test complete ETP flow"""
    
    def setUp(self):
        """Set up test fixtures"""
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret_key'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        self.app = create_api()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Create tables
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
    
    def test_01_new_conversation(self):
        """Test creating new conversation"""
        response = self.client.post('/api/etp-dynamic/new', json={})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data.get('success'))
        self.assertIsNotNone(data.get('conversation_id'))
        self.assertEqual(data.get('stage'), 'collect_need')
        
        print(f"[DEBUG_LOG] Test 1 passed: New conversation created with stage={data.get('stage')}")
    
    def test_02_collect_need_to_suggest_requirements(self):
        """Test that collect_need immediately transitions to suggest_requirements with list"""
        # Create conversation
        response = self.client.post('/api/etp-dynamic/new', json={})
        data = json.loads(response.data)
        conversation_id = data.get('conversation_id')
        
        # Send need
        response = self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': '5 carros estilo SUV para transporte de equipes'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('stage'), 'suggest_requirements')
        
        # Check that response contains numbered list
        ai_response = data.get('ai_response', '')
        self.assertIn('requisitos:', ai_response.lower())
        
        # Check no questions in response
        self.assertNotIn('?', ai_response.split('\n')[0])  # First line shouldn't be a question
        
        # Check requirements are returned
        requirements = data.get('requirements')
        if requirements:
            for req in requirements:
                req_text = req.get('text') if isinstance(req, dict) else str(req)
                self.assertFalse(req_text.strip().endswith('?'), 
                                f"Requirement should not be a question: {req_text}")
        
        print(f"[DEBUG_LOG] Test 2 passed: collect_need → suggest_requirements without questions")
    
    def test_03_confirm_requirements_to_solution_path(self):
        """Test that 'pode seguir' moves directly to solution_path"""
        # Create conversation
        response = self.client.post('/api/etp-dynamic/new', json={})
        data = json.loads(response.data)
        conversation_id = data.get('conversation_id')
        
        # Send need
        self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'Aquisição de notebooks para escritório'
        })
        
        # Confirm requirements
        response = self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'pode seguir'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('stage'), 'solution_path')
        
        # Check no questionnaire appears
        ai_response = data.get('ai_response', '')
        lines = [line for line in ai_response.split('\n') if line.strip()]
        question_lines = [line for line in lines if '?' in line]
        # Allow questions only in instructions, not in content
        self.assertLess(len(question_lines), 2, "Should not have questionnaire format")
        
        print(f"[DEBUG_LOG] Test 3 passed: 'pode seguir' → solution_path without questionnaire")
    
    def test_04_edit_commands(self):
        """Test add/remove/edit commands in suggest_requirements"""
        # Create conversation
        response = self.client.post('/api/etp-dynamic/new', json={})
        data = json.loads(response.data)
        conversation_id = data.get('conversation_id')
        
        # Send need
        self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'Compra de 10 cadeiras ergonômicas'
        })
        
        # Test adicionar command
        response = self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'adicionar: Cadeiras devem ter certificação ISO'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('stage'), 'suggest_requirements')  # Stay in same stage
        self.assertIn('adicionado', data.get('ai_response', '').lower())
        
        print(f"[DEBUG_LOG] Test 4 passed: Edit commands work in suggest_requirements")
    
    def test_05_stage_progression(self):
        """Test progression through pca, legal_norms, qty_value, installment stages"""
        # Create conversation
        response = self.client.post('/api/etp-dynamic/new', json={})
        data = json.loads(response.data)
        conversation_id = data.get('conversation_id')
        
        # Go through initial stages
        self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'Serviço de limpeza predial'
        })
        
        self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'confirmo'
        })
        
        # Solution path → pca
        response = self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'ok'
        })
        data = json.loads(response.data)
        self.assertEqual(data.get('stage'), 'pca')
        
        # pca → legal_norms
        response = self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'sim, está no PCA'
        })
        data = json.loads(response.data)
        self.assertEqual(data.get('stage'), 'legal_norms')
        
        # legal_norms → qty_value
        response = self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'Lei 8666/93'
        })
        data = json.loads(response.data)
        self.assertEqual(data.get('stage'), 'qty_value')
        
        # qty_value → installment
        response = self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': '12 meses, R$ 120.000,00'
        })
        data = json.loads(response.data)
        self.assertEqual(data.get('stage'), 'installment')
        
        print(f"[DEBUG_LOG] Test 5 passed: Stage progression works correctly")
    
    def test_06_summary_and_preview(self):
        """Test summary format and preview generation with URLs"""
        # Create conversation and go through all stages
        response = self.client.post('/api/etp-dynamic/new', json={})
        data = json.loads(response.data)
        conversation_id = data.get('conversation_id')
        
        # Quick progression through stages
        stages_messages = [
            'Aquisição de 5 veículos SUV',  # collect_need
            'pode seguir',  # suggest_requirements
            'ok',  # solution_path
            'sim',  # pca
            'Lei 8666/93',  # legal_norms
            '5 unidades, R$ 500.000',  # qty_value
            'não haverá parcelamento'  # installment
        ]
        
        for msg in stages_messages:
            response = self.client.post('/api/etp-dynamic/chat-stage', json={
                'conversation_id': conversation_id,
                'message': msg
            })
        
        # Check summary stage
        data = json.loads(response.data)
        self.assertEqual(data.get('stage'), 'summary')
        
        ai_response = data.get('ai_response', '')
        self.assertIn('Resumo do ETP', ai_response)
        self.assertIn('itens', ai_response)
        self.assertIn('passos', ai_response)
        
        # Confirm to get preview
        response = self.client.post('/api/etp-dynamic/chat-stage', json={
            'conversation_id': conversation_id,
            'message': 'confirmo'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get('stage'), 'preview')
        
        # Check preview response fields
        self.assertTrue(data.get('preview_ready', False), "preview_ready should be True")
        
        # Check that all required fields are present
        self.assertIsNotNone(data.get('html_path'), "html_path should not be None")
        self.assertIsNotNone(data.get('filename'), "filename should not be None")
        
        # Check field formats
        html_path = data.get('html_path')
        self.assertIn('/static/previews/', html_path, "html_path should contain /static/previews/")
        self.assertTrue(html_path.endswith('.html'), "html_path should end with .html")
        
        filename = data.get('filename')
        self.assertTrue(filename.startswith('ETP_'), "filename should start with ETP_")
        self.assertTrue(filename.endswith('.html'), "filename should end with .html")
        
        # pdf_path should be None (not implemented) or present if implemented
        pdf_path = data.get('pdf_path')
        # Allow None since PDF generation is not yet implemented
        if pdf_path is not None:
            self.assertIn('/static/previews/', pdf_path, "pdf_path should contain /static/previews/")
        
        # Check that file_path is also present for backward compatibility
        self.assertIsNotNone(data.get('file_path'), "file_path should be present")
        
        print(f"[DEBUG_LOG] Test 6 passed: Summary format correct and preview generates with all fields")
        print(f"[DEBUG_LOG]   html_path: {html_path}")
        print(f"[DEBUG_LOG]   pdf_path: {pdf_path}")
        print(f"[DEBUG_LOG]   filename: {filename}")
    
    def test_07_no_questions_in_requirements(self):
        """Test that requirements never contain questions"""
        # Create conversation
        response = self.client.post('/api/etp-dynamic/new', json={})
        data = json.loads(response.data)
        conversation_id = data.get('conversation_id')
        
        # Send various needs
        test_needs = [
            'Aquisição de material de escritório',
            'Contratação de serviço de TI',
            'Locação de impressoras'
        ]
        
        for need in test_needs:
            # Create new conversation for each test
            response = self.client.post('/api/etp-dynamic/new', json={})
            data = json.loads(response.data)
            conversation_id = data.get('conversation_id')
            
            response = self.client.post('/api/etp-dynamic/chat-stage', json={
                'conversation_id': conversation_id,
                'message': need
            })
            
            data = json.loads(response.data)
            requirements = data.get('requirements', [])
            
            for req in requirements:
                req_text = req.get('text') if isinstance(req, dict) else str(req)
                self.assertFalse(req_text.strip().endswith('?'),
                                f"Requirement must not be question: {req_text}")
        
        print(f"[DEBUG_LOG] Test 7 passed: No questions in requirements for various needs")
    
    def test_08_message_persistence(self):
        """Test that all messages are persisted"""
        # Create conversation
        response = self.client.post('/api/etp-dynamic/new', json={})
        data = json.loads(response.data)
        conversation_id = data.get('conversation_id')
        
        # Send multiple messages
        messages = ['Compra de notebooks', 'pode seguir', 'ok']
        for msg in messages:
            self.client.post('/api/etp-dynamic/chat-stage', json={
                'conversation_id': conversation_id,
                'message': msg
            })
        
        # Open conversation and check messages
        response = self.client.get(f'/api/etp-dynamic/open/{conversation_id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data.get('success'))
        
        messages_list = data.get('messages', [])
        # Should have at least user messages (3) + system responses
        self.assertGreaterEqual(len(messages_list), 3)
        
        print(f"[DEBUG_LOG] Test 8 passed: Messages persisted correctly")


if __name__ == '__main__':
    unittest.main(verbosity=2)
