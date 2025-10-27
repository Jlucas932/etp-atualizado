#!/usr/bin/env python3
"""
Test script for the improvements implemented:
1. Natural language confirmation (positive/negative/uncertain)
2. DOCX export functionality
3. Streaming endpoint (SSE)
4. Intent classification
"""

import sys
import os
import unittest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from domain.usecase.etp import conversational_state_machine as csm


class TestIntentClassification(unittest.TestCase):
    """Test natural language confirmation intent classification"""
    
    def test_positive_intent_variations(self):
        """Test various positive confirmation phrases"""
        positive_phrases = [
            "sim",
            "ok",
            "pode seguir",
            "manda bala",
            "concordo",
            "está bom",
            "perfeito",
            "claro",
            "aprovado",
            "tá bom",
            "beleza",
            "vamos lá",
            "pode prosseguir"
        ]
        
        for phrase in positive_phrases:
            intent = csm.classify_confirmation_intent(phrase)
            self.assertEqual(intent, 'positive', 
                           f"Expected 'positive' for '{phrase}', got '{intent}'")
    
    def test_negative_intent_variations(self):
        """Test various negative/adjustment phrases"""
        negative_phrases = [
            "não",
            "não gostei",
            "ajustar",
            "corrigir",
            "mudar",
            "refazer",
            "discordo",
            "voltar",
            "modificar"
        ]
        
        for phrase in negative_phrases:
            intent = csm.classify_confirmation_intent(phrase)
            self.assertEqual(intent, 'negative', 
                           f"Expected 'negative' for '{phrase}', got '{intent}'")
    
    def test_uncertain_intent_variations(self):
        """Test various uncertain/doubt phrases"""
        uncertain_phrases = [
            "talvez",
            "não sei",
            "dúvida",
            "pode ser",
            "o que é isso?",
            "me explica",
            "não entendi",
            "como assim"
        ]
        
        for phrase in uncertain_phrases:
            intent = csm.classify_confirmation_intent(phrase)
            self.assertEqual(intent, 'uncertain', 
                           f"Expected 'uncertain' for '{phrase}', got '{intent}'")
    
    def test_accent_normalization(self):
        """Test that accents are normalized correctly"""
        pairs = [
            ("não", "nao"),
            ("está", "esta"),
            ("ótimo", "otimo"),
            ("dúvida", "duvida")
        ]
        
        for accented, normalized in pairs:
            intent_accented = csm.classify_confirmation_intent(accented)
            intent_normalized = csm.classify_confirmation_intent(normalized)
            self.assertEqual(intent_accented, intent_normalized,
                           f"Accent normalization failed for '{accented}' vs '{normalized}'")


class TestStateResponses(unittest.TestCase):
    """Test that state responses include friendly confirmation messages"""
    
    def test_suggest_requirements_friendly_message(self):
        """Test that suggest_requirements state has friendly confirmation"""
        session_data = {
            'requirements': [
                {'id': 'R1', 'text': 'Requisito 1'},
                {'id': 'R2', 'text': 'Requisito 2'}
            ]
        }
        
        response = csm.generate_state_response('suggest_requirements', session_data)
        
        # Should include friendly confirmation without exact word requirements
        self.assertIn('seguir', response.lower())
        self.assertNotIn('confirme', response.lower())  # Should not require exact word
    
    def test_summary_state_friendly_message(self):
        """Test that summary state has friendly confirmation"""
        session_data = {
            'necessity': 'Test necessity',
            'requirements': [{'id': 'R1', 'text': 'Test req'}],
            'answers': {
                'solution_strategy': 'Test strategy',
                'pca': 'Test PCA'
            }
        }
        
        response = csm.generate_state_response('summary', session_data)
        
        # Should ask friendly confirmation like "Tudo certo?"
        self.assertTrue(
            'tudo certo' in response.lower() or 'posso gerar' in response.lower(),
            "Summary should have friendly confirmation message"
        )


class TestDocxExporter(unittest.TestCase):
    """Test DOCX export functionality"""
    
    def test_docx_exporter_import(self):
        """Test that DocxExporter can be imported"""
        try:
            from domain.services.docx_exporter import DocxExporter
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import DocxExporter: {e}")
    
    def test_docx_exporter_initialization(self):
        """Test DocxExporter initialization"""
        from domain.services.docx_exporter import DocxExporter
        
        # Without template
        exporter = DocxExporter()
        self.assertFalse(exporter.use_template)
        
        # With non-existent template
        exporter = DocxExporter('/path/to/nonexistent/template.docx')
        self.assertFalse(exporter.use_template)
    
    def test_docx_export_basic(self):
        """Test basic DOCX export"""
        from domain.services.docx_exporter import DocxExporter
        
        exporter = DocxExporter()
        
        etp_data = {
            'title': 'Test ETP',
            'organ': 'Test Org',
            'object': 'Test Object',
            'necessity': 'Test necessity',
            'requirements': [
                {'text': 'Requisito 1'},
                {'text': 'Requisito 2'}
            ],
            'solution_strategy': 'Test strategy',
            'pca': 'Test PCA',
            'legal_norms': 'Lei 14.133/2021',
            'quant_value': 'R$ 100.000,00',
            'parcelamento': 'Não',
            'justifications': 'Test justification',
            'signatures': 'Test signature'
        }
        
        try:
            buffer = exporter.export_etp(etp_data)
            self.assertIsNotNone(buffer)
            self.assertGreater(buffer.getbuffer().nbytes, 0)
        except Exception as e:
            self.fail(f"Failed to export ETP to DOCX: {e}")


class TestTemplateGeneration(unittest.TestCase):
    """Test template generation"""
    
    def test_template_exists(self):
        """Test that template file was generated"""
        template_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'templates',
            'modelo-etp.docx'
        )
        
        self.assertTrue(
            os.path.exists(template_path),
            f"Template file not found at {template_path}"
        )


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestIntentClassification))
    suite.addTests(loader.loadTestsFromTestCase(TestStateResponses))
    suite.addTests(loader.loadTestsFromTestCase(TestDocxExporter))
    suite.addTests(loader.loadTestsFromTestCase(TestTemplateGeneration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 70)
    print("Testing Improvements Implementation")
    print("=" * 70)
    print("\n1. Testing natural language confirmation intent classification")
    print("2. Testing DOCX export functionality")
    print("3. Testing friendly confirmation messages")
    print("4. Testing template generation")
    print("\n" + "=" * 70 + "\n")
    
    success = run_tests()
    
    print("\n" + "=" * 70)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed. See details above.")
    print("=" * 70)
    
    sys.exit(0 if success else 1)
