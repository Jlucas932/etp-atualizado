import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from domain.usecase.etp.legal_norms_interpreter import parse_legal_norms

class TestLegalNormsParser(unittest.TestCase):
    def test_pca_yes_no_unknown_and_details(self):
        """Test that parser correctly identifies PCA intents"""
        # Test pca_yes intent
        result = parse_legal_norms("Sim, está no PCA", {})
        self.assertEqual(result['intent'], 'pca_yes')
        
        # Test pca_no intent
        result = parse_legal_norms("Não está no PCA", {})
        self.assertEqual(result['intent'], 'pca_no')
        
        # Test pca_unknown intent
        result = parse_legal_norms("Não sei te dizer", {})
        self.assertEqual(result['intent'], 'pca_unknown')
        
        # Test pca_details intent
        result = parse_legal_norms("PCA nº 123/2025, item 7", {})
        self.assertEqual(result['intent'], 'pca_details')
        self.assertIn('raw', result['payload'])
        self.assertIn('123/2025', result['payload']['raw'])

if __name__ == '__main__':
    unittest.main()
