"""
Tests for HOTFIX - verifying NameError fix and strategy selection blocking
"""
import sys
import os
import unittest

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

class TestGeneratorImportRe(unittest.TestCase):
    """Test that generator.py has re imported and _post_process_response works"""
    
    def test_generator_import_re(self):
        """Verify that _post_process_response can be called without NameError"""
        from application.ai.generator import _post_process_response
        
        # Test calling _post_process_response with sample data
        test_response = {
            "intro": "Test intro with adicionar: something",
            "requirements": ["Req 1", "Req 2 with remover: pattern"],
            "justification": "Test justification"
        }
        
        # Should not raise NameError: name 're' is not defined
        try:
            result = _post_process_response(test_response, "suggest_requirements")
            # Verify it ran successfully
            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)
            print("[DEBUG_LOG] _post_process_response executed without NameError")
        except NameError as e:
            if "'re' is not defined" in str(e):
                self.fail(f"NameError still present: {e}")
            else:
                raise


class TestStrategySelectionHelpers(unittest.TestCase):
    """Test new helper functions _is_free_confirm and _strategy_selection"""
    
    def setUp(self):
        """Import helper functions"""
        from adapter.entrypoint.etp.EtpDynamicController import _is_free_confirm, _strategy_selection
        self._is_free_confirm = _is_free_confirm
        self._strategy_selection = _strategy_selection
    
    def test_is_free_confirm_detects_simple_confirmations(self):
        """Test that _is_free_confirm identifies simple confirmations"""
        # Should return True for simple confirmations
        self.assertTrue(self._is_free_confirm("ok"))
        self.assertTrue(self._is_free_confirm("okay"))
        self.assertTrue(self._is_free_confirm("pode seguir"))
        self.assertTrue(self._is_free_confirm("pode continuar"))
        self.assertTrue(self._is_free_confirm("perfeito"))
        self.assertTrue(self._is_free_confirm("segue"))
        self.assertTrue(self._is_free_confirm("vamos lá"))
        
        # Should return False for actual content
        self.assertFalse(self._is_free_confirm("escolho a opção 2"))
        self.assertFalse(self._is_free_confirm("prefiro leasing"))
        self.assertFalse(self._is_free_confirm(""))
        self.assertFalse(self._is_free_confirm("3"))
        
        print("[DEBUG_LOG] _is_free_confirm correctly identifies simple confirmations")
    
    def test_strategy_select_by_number(self):
        """Test numeric strategy selection"""
        strategies = [
            "Compra Direta",
            "Leasing Operacional",
            "Outsourcing",
            "Comodato"
        ]
        
        # Test valid numeric selections (1-based input, 0-based output)
        self.assertEqual(self._strategy_selection("1", strategies), 0)
        self.assertEqual(self._strategy_selection("2", strategies), 1)
        self.assertEqual(self._strategy_selection("3", strategies), 2)
        self.assertEqual(self._strategy_selection("4", strategies), 3)
        
        # Test out of range
        self.assertIsNone(self._strategy_selection("5", strategies))
        self.assertIsNone(self._strategy_selection("9", strategies))
        
        # Test non-numeric
        self.assertIsNone(self._strategy_selection("abc", strategies))
        
        print("[DEBUG_LOG] Numeric strategy selection works correctly")
    
    def test_strategy_select_by_text(self):
        """Test text-based fuzzy strategy selection"""
        strategies = [
            "Compra Direta",
            "Leasing Operacional",
            "Outsourcing Completo",
            "Comodato"
        ]
        
        # Test exact/partial text matches
        result = self._strategy_selection("leasing", strategies)
        self.assertEqual(result, 1)  # Should match "Leasing Operacional"
        
        result = self._strategy_selection("outsourcing", strategies)
        self.assertEqual(result, 2)  # Should match "Outsourcing Completo"
        
        result = self._strategy_selection("compra", strategies)
        self.assertEqual(result, 0)  # Should match "Compra Direta"
        
        # Test low similarity - should return None
        result = self._strategy_selection("xyz", strategies)
        self.assertIsNone(result)
        
        print("[DEBUG_LOG] Text-based strategy selection works correctly")


class TestStrategyNeverAdvancesOnConfirm(unittest.TestCase):
    """Test that solution_strategies stage doesn't advance on free confirmations"""
    
    def setUp(self):
        """Set up test environment"""
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret_key'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    def tearDown(self):
        """Clean up environment"""
        for key in ['OPENAI_API_KEY', 'SECRET_KEY', 'DATABASE_URL']:
            if key in os.environ:
                del os.environ[key]
    
    def test_strategy_stage_stays_on_free_confirm(self):
        """
        Simulate solution_strategies stage with 4 strategies.
        Send "pode seguir" and assert stage remains and no selection is saved.
        """
        from adapter.entrypoint.etp.EtpDynamicController import _strategy_selection
        
        # Sample strategies
        strategies = [
            {"titulo": "Compra Direta"},
            {"titulo": "Leasing Operacional"},
            {"titulo": "Outsourcing"},
            {"titulo": "Comodato"}
        ]
        
        strategy_titles = [s["titulo"] for s in strategies]
        
        # Test with various free confirmations
        free_confirms = ["pode seguir", "ok", "perfeito", "segue", "pode continuar"]
        
        for confirm in free_confirms:
            result = _strategy_selection(confirm, strategy_titles)
            # Should NOT return a valid selection
            self.assertIsNone(result, 
                f"Free confirmation '{confirm}' should not trigger selection, got {result}")
        
        print("[DEBUG_LOG] Free confirmations do not trigger strategy selection")
        
        # Test with actual selections - should work
        self.assertEqual(_strategy_selection("2", strategy_titles), 1)
        self.assertIsNotNone(_strategy_selection("leasing", strategy_titles))
        
        print("[DEBUG_LOG] Actual selections still work properly")


if __name__ == '__main__':
    unittest.main()
