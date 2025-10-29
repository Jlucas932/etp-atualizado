"""
Test that empty payloads are never returned
Tests that _ensure_min_payload fills intro, requirements (>=8), and justification
"""
import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.ai.generator import _ensure_min_payload, _fallback_response

class TestNoEmptyPayload(unittest.TestCase):
    
    def test_ensure_min_payload_collect_need(self):
        """Test that empty collect_need payload gets filled"""
        print("[DEBUG_LOG] Testing _ensure_min_payload for collect_need with empty data")
        
        # Empty response
        resp = {
            "intro": "",
            "requirements": [],
            "justification": ""
        }
        
        necessity = "Contratação de serviço de TI"
        result = _ensure_min_payload(resp, "collect_need", necessity)
        
        print(f"[DEBUG_LOG] Intro filled: {bool(result.get('intro'))}")
        print(f"[DEBUG_LOG] Requirements count: {len(result.get('requirements', []))}")
        print(f"[DEBUG_LOG] Justification filled: {bool(result.get('justification'))}")
        
        # Verify intro is filled
        self.assertTrue(result.get('intro'))
        self.assertIn('necessidade', result['intro'].lower())
        
        # Verify requirements has at least 8 items
        requirements = result.get('requirements', [])
        self.assertGreaterEqual(len(requirements), 8)
        
        # Verify all requirements are numbered
        for req in requirements:
            self.assertTrue(req.strip()[0].isdigit())
        
        # Verify justification is filled
        self.assertTrue(result.get('justification'))
        self.assertIn('conformidade', result['justification'].lower())
    
    def test_ensure_min_payload_solution_strategies(self):
        """Test that empty solution_strategies payload gets filled"""
        print("[DEBUG_LOG] Testing _ensure_min_payload for solution_strategies with empty data")
        
        # Empty strategies response
        resp = {
            "intro": "",
            "strategies": []
        }
        
        necessity = "Aquisição de equipamentos"
        result = _ensure_min_payload(resp, "solution_strategies", necessity)
        
        print(f"[DEBUG_LOG] Intro filled: {bool(result.get('intro'))}")
        print(f"[DEBUG_LOG] Strategies count: {len(result.get('strategies', []))}")
        
        # Verify intro is filled
        self.assertTrue(result.get('intro'))
        
        # Verify strategies has at least 2 items
        strategies = result.get('strategies', [])
        self.assertGreaterEqual(len(strategies), 2)
        
        # Verify each strategy has required fields
        for strat in strategies:
            self.assertIn('titulo', strat)
            self.assertIn('quando_indicado', strat)
            self.assertIn('vantagens', strat)
            self.assertIn('riscos', strat)
            self.assertTrue(isinstance(strat['vantagens'], list))
            self.assertTrue(isinstance(strat['riscos'], list))
        
        print(f"[DEBUG_LOG] Strategy titles: {[s['titulo'] for s in strategies]}")
    
    def test_ensure_min_payload_insufficient_requirements(self):
        """Test that insufficient requirements (less than 8) get filled"""
        print("[DEBUG_LOG] Testing _ensure_min_payload with insufficient requirements")
        
        # Only 3 requirements
        resp = {
            "intro": "Test intro",
            "requirements": [
                "1. Requisito um",
                "2. Requisito dois",
                "3. Requisito três"
            ],
            "justification": "Test justification"
        }
        
        necessity = "Serviços de manutenção"
        result = _ensure_min_payload(resp, "collect_need", necessity)
        
        requirements = result.get('requirements', [])
        print(f"[DEBUG_LOG] Requirements after ensure: {len(requirements)}")
        
        # Should have at least 8 requirements now
        self.assertGreaterEqual(len(requirements), 8)
        
        # Verify all are numbered
        for req in requirements:
            self.assertTrue(req.strip()[0].isdigit())
    
    def test_fallback_response_never_empty(self):
        """Test that _fallback_response always returns valid data"""
        print("[DEBUG_LOG] Testing _fallback_response for various stages")
        
        necessity = "Contratação de software"
        rag_context = {'necessity': necessity}
        
        # Test collect_need fallback
        result = _fallback_response('collect_need', necessity, rag_context)
        self.assertIn('requirements', result)
        self.assertGreaterEqual(len(result['requirements']), 8)
        self.assertTrue(result.get('intro'))
        self.assertTrue(result.get('justification'))
        print(f"[DEBUG_LOG] collect_need fallback: {len(result['requirements'])} requirements")
        
        # Test solution_strategies fallback
        result = _fallback_response('solution_strategies', necessity, rag_context)
        self.assertIn('strategies', result)
        self.assertGreaterEqual(len(result['strategies']), 2)
        self.assertTrue(result.get('intro'))
        print(f"[DEBUG_LOG] solution_strategies fallback: {len(result['strategies'])} strategies")
        
        # Test legal_refs fallback
        result = _fallback_response('legal_refs', necessity, rag_context)
        self.assertIn('legal', result)
        self.assertGreater(len(result['legal']), 0)
        print(f"[DEBUG_LOG] legal_refs fallback: {len(result['legal'])} legal items")
        
        # Test summary fallback
        result = _fallback_response('summary', necessity, rag_context)
        self.assertIn('summary', result)
        self.assertTrue(result['summary'])
        print(f"[DEBUG_LOG] summary fallback: {len(result['summary'])} chars")
    
    def test_ensure_min_payload_preserves_valid_data(self):
        """Test that _ensure_min_payload preserves valid data"""
        print("[DEBUG_LOG] Testing _ensure_min_payload preserves valid data")
        
        # Valid complete response
        resp = {
            "intro": "Minha introdução personalizada",
            "requirements": [f"{i}. Requisito número {i}" for i in range(1, 11)],
            "justification": "Minha justificativa personalizada"
        }
        
        necessity = "Test"
        result = _ensure_min_payload(resp, "collect_need", necessity)
        
        # Should preserve original intro and justification
        self.assertEqual(result['intro'], "Minha introdução personalizada")
        self.assertEqual(result['justification'], "Minha justificativa personalizada")
        
        # Should preserve original requirements
        self.assertEqual(len(result['requirements']), 10)
        self.assertEqual(result['requirements'][0], "1. Requisito número 1")
        
        print("[DEBUG_LOG] Valid data preserved successfully")

if __name__ == '__main__':
    unittest.main()
