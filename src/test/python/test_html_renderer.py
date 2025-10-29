import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.config.FlaskConfig import create_api
from domain.usecase.etp.html_renderer import render_etp_html

class TestHtmlRenderer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret_key'
        os.environ['DATABASE_URL'] = 'sqlite:///test.db'
        os.environ['EMBEDDINGS_PROVIDER'] = 'openai'
        os.environ['RAG_FAISS_PATH'] = 'rag/index/faiss'
        
        self.app = create_api()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
    def test_render_etp_html_basic(self):
        """Test that render_etp_html returns HTML string"""
        sample_doc = {
            'session_id': 'test-session-123',
            'title': 'Estudo Técnico Preliminar (ETP) - Teste',
            'sections': [
                {
                    'id': 'intro',
                    'title': 'Introdução',
                    'content': 'Este é um documento de teste.'
                },
                {
                    'id': 'necessity',
                    'title': 'Necessidade/Objeto',
                    'content': 'Aquisição de notebooks para o setor de TI.'
                },
                {
                    'id': 'requirements',
                    'title': 'Requisitos',
                    'content': 'Lista de requisitos confirmados.',
                    'items': ['Processador i7', 'RAM 16GB', 'SSD 512GB']
                },
                {
                    'id': 'pca',
                    'title': 'Plano de Contratações Anual (PCA)',
                    'content': 'Há previsão no PCA: Sim',
                    'details': 'Item X.Y do PCA 2025'
                },
                {
                    'id': 'price_research',
                    'title': 'Pesquisa de Preços',
                    'content': 'Registro de método, quantidade e evidências.',
                    'method': 'Cotação com fornecedores',
                    'supplier_count': 3,
                    'evidence_links': ['http://example.com/cotacao1', 'http://example.com/cotacao2']
                },
                {
                    'id': 'legal_basis',
                    'title': 'Base Legal',
                    'content': 'Lei 14.133/2021',
                    'notes': ['Art. 6º', 'Art. 12º']
                }
            ]
        }
        
        with self.app.app_context():
            html = render_etp_html(sample_doc)
            
            # Verify HTML is returned
            self.assertIsInstance(html, str)
            self.assertGreater(len(html), 0)
            
            # Verify essential HTML structure
            self.assertIn('<!doctype html>', html.lower())
            self.assertIn('<html', html.lower())
            self.assertIn('</html>', html.lower())
            
            # Verify document title
            self.assertIn('Estudo Técnico Preliminar (ETP) - Teste', html)
            
            # Verify session ID
            self.assertIn('test-session-123', html)
            
            # Verify all section titles
            self.assertIn('Introdução', html)
            self.assertIn('Necessidade/Objeto', html)
            self.assertIn('Requisitos', html)
            self.assertIn('Plano de Contratações Anual (PCA)', html)
            self.assertIn('Pesquisa de Preços', html)
            self.assertIn('Base Legal', html)
            
            # Verify section content
            self.assertIn('Aquisição de notebooks para o setor de TI', html)
            self.assertIn('Processador i7', html)
            self.assertIn('RAM 16GB', html)
            self.assertIn('Item X.Y do PCA 2025', html)
            self.assertIn('Cotação com fornecedores', html)
            self.assertIn('Lei 14.133/2021', html)
            
            print("[DEBUG_LOG] HTML rendering test passed successfully")
        
    def tearDown(self):
        """Clean up after tests"""
        # Clean environment variables
        for key in ['OPENAI_API_KEY', 'SECRET_KEY', 'DATABASE_URL', 'EMBEDDINGS_PROVIDER', 'RAG_FAISS_PATH']:
            if key in os.environ:
                del os.environ[key]

if __name__ == '__main__':
    unittest.main()
