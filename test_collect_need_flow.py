#!/usr/bin/env python3
"""
Test script to validate the collect_need -> suggest_requirements flow fix
"""
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_conversational_state_machine_guard():
    """Test that intent guard in conversational_state_machine works"""
    print("[TEST 1] Testing conversational_state_machine intent guard...")
    
    from domain.usecase.etp import conversational_state_machine as csm
    
    # Test that confirmation at collect_need returns user_input intent
    result = csm.parse_user_intent("ok", "collect_need", {})
    
    if result['intent'] == 'user_input':
        print("✓ PASS: Intent guard correctly returns 'user_input' for confirmation at collect_need")
        return True
    else:
        print(f"✗ FAIL: Expected 'user_input' but got '{result['intent']}'")
        return False

def test_valid_transitions():
    """Test that state machine has correct transitions"""
    print("\n[TEST 2] Testing state machine transitions...")
    
    from domain.usecase.etp import conversational_state_machine as csm
    
    # Check that collect_need only transitions to suggest_requirements
    valid_transitions = csm.VALID_TRANSITIONS.get('collect_need', [])
    
    if valid_transitions == ['suggest_requirements']:
        print("✓ PASS: collect_need correctly transitions only to suggest_requirements")
        return True
    else:
        print(f"✗ FAIL: Expected ['suggest_requirements'] but got {valid_transitions}")
        return False

def test_generator_prompt():
    """Test that generator has correct prompt for collect_need"""
    print("\n[TEST 3] Testing generator prompt for collect_need...")
    
    from application.ai import generator
    
    # Get system prompt for collect_need
    prompt = generator.get_system_prompt('collect_need')
    
    # Check that prompt doesn't ask questions
    if 'requisitos' in prompt.lower() and 'tarefa' in prompt.lower():
        print("✓ PASS: collect_need prompt focuses on generating requirements")
        return True
    else:
        print("✗ FAIL: Prompt doesn't seem to focus on requirements generation")
        return False

def main():
    print("=" * 70)
    print("HOTFIX VALIDATION: collect_need -> suggest_requirements flow")
    print("=" * 70)
    
    results = []
    
    try:
        results.append(test_conversational_state_machine_guard())
    except Exception as e:
        print(f"✗ TEST 1 FAILED with exception: {e}")
        results.append(False)
    
    try:
        results.append(test_valid_transitions())
    except Exception as e:
        print(f"✗ TEST 2 FAILED with exception: {e}")
        results.append(False)
    
    try:
        results.append(test_generator_prompt())
    except Exception as e:
        print(f"✗ TEST 3 FAILED with exception: {e}")
        results.append(False)
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("\n✓ All validation tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
