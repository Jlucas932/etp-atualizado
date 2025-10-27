import os
import sys
import unittest

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from application.ai.generator import get_etp_generator, FallbackGenerator, OpenAIGenerator


class TestGeneratorFallback(unittest.TestCase):
    """Test the generator factory and fallback behavior"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Save original env vars
        self.original_provider = os.environ.get('ETP_AI_PROVIDER')
        self.original_api_key = os.environ.get('OPENAI_API_KEY')
        self.original_model = os.environ.get('OPENAI_MODEL')
    
    def tearDown(self):
        """Clean up after tests"""
        # Restore original env vars
        if self.original_provider:
            os.environ['ETP_AI_PROVIDER'] = self.original_provider
        elif 'ETP_AI_PROVIDER' in os.environ:
            del os.environ['ETP_AI_PROVIDER']
            
        if self.original_api_key:
            os.environ['OPENAI_API_KEY'] = self.original_api_key
        elif 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']
            
        if self.original_model:
            os.environ['OPENAI_MODEL'] = self.original_model
        elif 'OPENAI_MODEL' in os.environ:
            del os.environ['OPENAI_MODEL']
    
    def test_generator_factory_defaults_to_fallback(self):
        """Test that factory defaults to FallbackGenerator when no provider is set"""
        if 'ETP_AI_PROVIDER' in os.environ:
            del os.environ['ETP_AI_PROVIDER']
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']
            
        gen = get_etp_generator()
        self.assertIsInstance(gen, FallbackGenerator)
    
    def test_generator_factory_fallback_explicit(self):
        """Test that factory returns FallbackGenerator when explicitly set"""
        os.environ['ETP_AI_PROVIDER'] = 'fallback'
        gen = get_etp_generator()
        self.assertIsInstance(gen, FallbackGenerator)
    
    def test_generator_factory_openai_without_key_falls_back(self):
        """Test that factory falls back when OpenAI is requested but no API key is set"""
        os.environ['ETP_AI_PROVIDER'] = 'openai'
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']
            
        gen = get_etp_generator()
        self.assertIsInstance(gen, FallbackGenerator)
    
    def test_fallback_generator_produces_requirements(self):
        """Test that FallbackGenerator produces valid requirements"""
        gen = FallbackGenerator()
        reqs = gen.suggest_requirements("Aquisição de notebooks para laboratório")
        
        self.assertIsInstance(reqs, list)
        self.assertGreaterEqual(len(reqs), 3)
        for req in reqs:
            self.assertIsInstance(req, str)
            self.assertGreater(len(req), 0)
    
    def test_fallback_generator_handles_empty_necessity(self):
        """Test that FallbackGenerator handles empty or None necessity"""
        gen = FallbackGenerator()
        
        reqs1 = gen.suggest_requirements("")
        self.assertIsInstance(reqs1, list)
        self.assertGreater(len(reqs1), 0)
        
        reqs2 = gen.suggest_requirements(None)
        self.assertIsInstance(reqs2, list)
        self.assertGreater(len(reqs2), 0)
    
    def test_openai_generator_requires_api_key(self):
        """Test that OpenAIGenerator raises error without API key"""
        with self.assertRaises(RuntimeError):
            OpenAIGenerator(None, None)
        
        with self.assertRaises(RuntimeError):
            OpenAIGenerator("", None)


if __name__ == '__main__':
    unittest.main()
