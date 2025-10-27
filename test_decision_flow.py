#!/usr/bin/env python3
"""
Test script to validate the decision-awaiting flow implementation.
Tests the new helper functions and ensures they work as expected.
"""

import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_decision_helpers():
    """Test the decision-awaiting helper functions"""
    print("[TEST] Testing decision-awaiting helpers...")
    
    # Mock session object
    class MockSession:
        def __init__(self):
            self._answers = {}
        
        def get_answers(self):
            return self._answers
        
        def set_answers(self, answers):
            self._answers = answers
    
    # Import after path is set
    from adapter.entrypoint.etp.EtpDynamicController import ask_user_decision, try_consume_decision
    
    # Test 1: ask_user_decision sets state correctly
    print("\n[TEST 1] Testing ask_user_decision...")
    session = MockSession()
    proposal = "Test proposal with justification"
    prompt = "Test prompt"
    
    result = ask_user_decision(session, prompt, proposal, 'test_stage')
    
    answers = session.get_answers()
    assert 'state' in answers, "State should be in answers"
    assert answers['state']['awaiting_decision'] == True, "awaiting_decision should be True"
    assert answers['state']['pending_proposal'] == proposal, "proposal should be stored"
    assert "**Opções:**" in result, "Result should contain options"
    print("✓ ask_user_decision works correctly")
    
    # Test 2: try_consume_decision with no pending decision
    print("\n[TEST 2] Testing try_consume_decision with no pending decision...")
    session2 = MockSession()
    result = try_consume_decision(session2, "some text")
    assert result is None, "Should return None when no decision is pending"
    print("✓ Returns None when no decision pending")
    
    # Test 3: try_consume_decision with accept
    print("\n[TEST 3] Testing try_consume_decision with 'accept'...")
    session3 = MockSession()
    session3.set_answers({
        'state': {
            'awaiting_decision': True,
            'pending_proposal': 'Test proposal',
            'decision_stage': 'test_stage'
        }
    })
    result = try_consume_decision(session3, "1")
    assert isinstance(result, dict), "Should return dict for valid decision"
    assert result['action'] == 'accept', "Should detect accept action"
    assert result['text'] == 'Test proposal', "Should return proposal text"
    assert session3.get_answers()['state']['awaiting_decision'] == False, "Should clear awaiting state"
    print("✓ Correctly processes 'accept' decision")
    
    # Test 4: try_consume_decision with pendente
    print("\n[TEST 4] Testing try_consume_decision with 'pendente'...")
    session4 = MockSession()
    session4.set_answers({
        'state': {
            'awaiting_decision': True,
            'pending_proposal': 'Test proposal',
            'decision_stage': 'test_stage'
        }
    })
    result = try_consume_decision(session4, "2")
    assert isinstance(result, dict), "Should return dict for valid decision"
    assert result['action'] == 'pendente', "Should detect pendente action"
    print("✓ Correctly processes 'pendente' decision")
    
    # Test 5: try_consume_decision with debate
    print("\n[TEST 5] Testing try_consume_decision with 'debate'...")
    session5 = MockSession()
    session5.set_answers({
        'state': {
            'awaiting_decision': True,
            'pending_proposal': 'Test proposal',
            'decision_stage': 'test_stage'
        }
    })
    result = try_consume_decision(session5, "3")
    assert isinstance(result, dict), "Should return dict for valid decision"
    assert result['action'] == 'debate', "Should detect debate action"
    print("✓ Correctly processes 'debate' decision")
    
    # Test 6: try_consume_decision with unclear input
    print("\n[TEST 6] Testing try_consume_decision with unclear input...")
    session6 = MockSession()
    session6.set_answers({
        'state': {
            'awaiting_decision': True,
            'pending_proposal': 'Test proposal',
            'decision_stage': 'test_stage'
        }
    })
    result = try_consume_decision(session6, "não entendi")
    assert isinstance(result, str), "Should return string asking for clarification"
    assert "confirmar" in result.lower(), "Should ask for confirmation"
    print("✓ Asks for clarification on unclear input")
    
    print("\n[TEST] All decision helper tests passed! ✓")


def test_safe_nonempty():
    """Test the _safe_nonempty function"""
    print("\n[TEST] Testing _safe_nonempty function...")
    
    from application.ai.generator import _safe_nonempty
    
    # Test 1: Non-empty text returns as-is
    print("\n[TEST 1] Non-empty text...")
    result = _safe_nonempty("Valid text", "test_stage")
    assert result == "Valid text", "Should return original text"
    print("✓ Returns non-empty text unchanged")
    
    # Test 2: Empty text returns fallback
    print("\n[TEST 2] Empty text...")
    result = _safe_nonempty("", "test_stage")
    assert result != "", "Should not return empty string"
    assert "Para não te deixar sem base" in result, "Should return fallback message"
    print("✓ Returns fallback for empty text")
    
    # Test 3: Whitespace-only text returns fallback
    print("\n[TEST 3] Whitespace-only text...")
    result = _safe_nonempty("   ", "test_stage")
    assert result.strip() != "", "Should not return empty/whitespace string"
    print("✓ Returns fallback for whitespace-only text")
    
    print("\n[TEST] All _safe_nonempty tests passed! ✓")


if __name__ == '__main__':
    print("="*60)
    print("Decision Flow Implementation Tests")
    print("="*60)
    
    try:
        test_decision_helpers()
        test_safe_nonempty()
        
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED!")
        print("="*60)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
