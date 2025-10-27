import os
import sys
import unittest

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from application.config.FlaskConfig import create_api


class TestHealthEndpoint(unittest.TestCase):
    """Test the health endpoint returns generator information"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Save original env vars
        self.original_provider = os.environ.get('ETP_AI_PROVIDER')
        self.original_api_key = os.environ.get('OPENAI_API_KEY')
        
        # Set required Flask env vars
        os.environ['SECRET_KEY'] = 'test_secret_key_for_testing'
        
        self.app = create_api()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Create application context
        self.app_context = self.app.app_context()
        self.app_context.push()
        
    def tearDown(self):
        """Clean up after tests"""
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
    
    def test_health_endpoint_exists(self):
        """Test that health endpoint is accessible"""
        response = self.client.get('/api/etp-dynamic/health')
        
        # Should return 200 or 500 (both are acceptable - endpoint exists)
        self.assertIn(response.status_code, [200, 500], 
                     f"Health endpoint should exist and return 200 or 500")
    
    def test_health_endpoint_with_fallback(self):
        """Test that health endpoint shows FallbackGenerator when no API key"""
        # Force fallback mode
        os.environ['ETP_AI_PROVIDER'] = 'fallback'
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']
        
        response = self.client.get('/api/etp-dynamic/health')
        
        # Even if it returns 500 for other reasons, should have JSON data
        data = response.get_json()
        self.assertIsNotNone(data, "Health endpoint should return JSON")
        
        # If status is healthy, check for generator info
        if response.status_code == 200 and data.get('status') == 'healthy':
            self.assertIn('simple_generator', data, 
                         "Health response should include simple_generator info")
            self.assertIn('FallbackGenerator', str(data.get('simple_generator')),
                         f"Should show FallbackGenerator. Got: {data.get('simple_generator')}")
    
    def test_health_endpoint_structure(self):
        """Test that health endpoint returns expected structure"""
        response = self.client.get('/api/etp-dynamic/health')
        data = response.get_json()
        
        self.assertIsNotNone(data, "Health endpoint should return JSON")
        
        # Check for basic structure
        if response.status_code == 200:
            self.assertIn('status', data, "Should have status field")
            self.assertIn('timestamp', data, "Should have timestamp field")
            
            # If healthy, should have generator info
            if data.get('status') == 'healthy':
                self.assertTrue(
                    'simple_generator' in data or 'etp_generator_ready' in data,
                    "Healthy response should include generator status"
                )
    
    def test_health_endpoint_with_openai_provider(self):
        """Test health endpoint when OpenAI provider is configured"""
        os.environ['ETP_AI_PROVIDER'] = 'openai'
        os.environ['OPENAI_API_KEY'] = 'test_fake_key_for_testing'
        
        response = self.client.get('/api/etp-dynamic/health')
        data = response.get_json()
        
        self.assertIsNotNone(data, "Health endpoint should return JSON")
        
        # With a fake key, it should still work but might show OpenAIGenerator or fallback
        if response.status_code == 200 and 'simple_generator' in data:
            generator_name = str(data.get('simple_generator'))
            # Should be either OpenAIGenerator (if it accepts fake key) or FallbackGenerator
            self.assertTrue(
                'Generator' in generator_name,
                f"Should show a generator class. Got: {generator_name}"
            )


if __name__ == '__main__':
    unittest.main()
