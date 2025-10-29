"""
Tests for preview_builder service
"""
import os
import sys
import unittest
import tempfile
import shutil

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from application.services.preview_builder import build_preview


class TestPreviewBuilder(unittest.TestCase):
    """Test preview builder service"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test previews
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        
        # Store original function to restore later
        from application.services import preview_builder
        self.original_generate_html = preview_builder._generate_html
        
    def tearDown(self):
        """Clean up after tests"""
        # Remove temporary directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_build_preview_creates_html_file(self):
        """Test that build_preview creates an HTML file"""
        conversation_id = "test-conv-123"
        summary = {
            'necessity': 'Aquisição de 5 veículos SUV',
            'requirements': [
                {'id': 'R1', 'text': 'Veículo tipo SUV'},
                {'id': 'R2', 'text': 'Zero quilômetro'}
            ],
            'answers': {
                'pca': 'Sim, previsto no PCA 2024',
                'legal_norms': 'Lei 14.133/2021',
                'qty_value': '5 unidades, R$ 250.000,00',
                'installment': 'Não haverá parcelamento',
                'solution_path': ['Definir escopo', 'Pesquisar mercado', 'Elaborar TR']
            }
        }
        
        try:
            result = build_preview(conversation_id, summary)
            
            # Check result structure
            self.assertIsInstance(result, dict)
            self.assertIn('html_path', result)
            self.assertIn('pdf_path', result)
            self.assertIn('filename', result)
            
            # Check paths
            self.assertIsNotNone(result['html_path'])
            self.assertTrue(result['html_path'].startswith('/static/previews/'))
            self.assertTrue(result['html_path'].endswith('.html'))
            
            # PDF should be None (not implemented)
            self.assertIsNone(result['pdf_path'])
            
            # Check filename
            self.assertIsNotNone(result['filename'])
            self.assertTrue(result['filename'].startswith('ETP_'))
            
            print(f"[TEST] Preview created successfully: {result}")
            
        except Exception as e:
            self.fail(f"build_preview raised exception: {e}")
    
    def test_build_preview_with_empty_requirements(self):
        """Test preview generation with no requirements"""
        conversation_id = "test-conv-empty"
        summary = {
            'necessity': 'Teste sem requisitos',
            'requirements': [],
            'answers': {}
        }
        
        try:
            result = build_preview(conversation_id, summary)
            
            # Should still create a file
            self.assertIsNotNone(result['html_path'])
            self.assertIn('html_path', result)
            
            print(f"[TEST] Preview with empty requirements created: {result}")
            
        except Exception as e:
            self.fail(f"build_preview raised exception with empty data: {e}")
    
    def test_build_preview_html_content(self):
        """Test that generated HTML contains expected content"""
        from application.services.preview_builder import _generate_html
        
        necessity = "Aquisição de equipamentos"
        requirements = [
            {'id': 'R1', 'text': 'Equipamento novo'},
            {'id': 'R2', 'text': 'Garantia mínima de 1 ano'}
        ]
        answers = {
            'pca': 'Sim',
            'legal_norms': 'Lei 14.133/2021',
            'qty_value': '10 unidades',
            'installment': 'Não',
            'solution_path': ['Passo 1', 'Passo 2']
        }
        
        html = _generate_html(necessity, requirements, answers)
        
        # Check HTML structure
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('<html', html)
        self.assertIn('</html>', html)
        
        # Check content
        self.assertIn('Estudo Técnico Preliminar', html)
        self.assertIn('Aquisição de equipamentos', html)
        self.assertIn('Equipamento novo', html)
        self.assertIn('Garantia mínima de 1 ano', html)
        self.assertIn('Lei 14.133/2021', html)
        
        # Should not have unescaped HTML
        self.assertNotIn('<script>', html.lower())
        
        print("[TEST] HTML content validation passed")
    
    def test_html_escape(self):
        """Test HTML escaping in generated content"""
        from application.services.preview_builder import _escape_html
        
        # Test basic escaping
        self.assertEqual(_escape_html('<script>alert("xss")</script>'), 
                        '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;')
        
        self.assertEqual(_escape_html('Test & Co.'), 'Test &amp; Co.')
        self.assertEqual(_escape_html("O'Brien"), "O&#x27;Brien")
        
        # Test non-string input
        self.assertEqual(_escape_html(123), '123')
        self.assertEqual(_escape_html(None), 'None')
        
        print("[TEST] HTML escaping validation passed")
    
    def test_build_preview_returns_correct_paths(self):
        """Test that paths are correctly formatted for frontend use"""
        conversation_id = "test-paths-456"
        summary = {
            'necessity': 'Test',
            'requirements': [],
            'answers': {}
        }
        
        try:
            result = build_preview(conversation_id, summary)
            
            # Check path format
            html_path = result['html_path']
            self.assertTrue(html_path.startswith('/'))
            self.assertIn('static/previews/', html_path)
            self.assertIn(conversation_id, html_path)
            
            # Check filename format
            filename = result['filename']
            self.assertTrue(filename.startswith('ETP_'))
            self.assertTrue(filename.endswith('.html'))
            
            print(f"[TEST] Path format validation passed: {html_path}")
            
        except Exception as e:
            self.fail(f"Path validation failed: {e}")


if __name__ == '__main__':
    unittest.main()
