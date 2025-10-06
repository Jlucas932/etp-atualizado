#!/usr/bin/env python3
"""
Test script to reproduce and validate the requirements suggestion fix
Tests the parse_requirements_response_safely function with various inputs
"""

import sys
import os
import json

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_parser_with_old_format():
    """Test parser with the old format that was causing the error"""
    from domain.usecase.etp.utils_parser import parse_requirements_response_safely
    
    # Simulate the old JSON format that was causing issues
    old_format_json = '''
    {
        "requirements": [
            {"id": "R1", "text": "Requisito 1", "justification": "Justificativa 1"},
            {"id": "R2", "text": "Requisito 2", "justification": "Justificativa 2"}
        ]
    }
    '''
    
    print("[DEBUG_LOG] Testing parser with old format...")
    result = parse_requirements_response_safely(old_format_json)
    print(f"[DEBUG_LOG] Old format result: {result}")
    
    # This should convert the old format to the new format
    if (isinstance(result, dict) and 
        'suggested_requirements' in result and 
        'consultative_message' in result and
        len(result['suggested_requirements']) == 2 and
        result['consultative_message'] == 'Requisitos convertidos do formato legado'):
        print("[DEBUG_LOG] ✓ Old format correctly converted to new format")
    else:
        print("[DEBUG_LOG] ✗ Old format handling failed")
        return False
    
    return True

def test_parser_with_new_format():
    """Test parser with the new correct format"""
    from domain.usecase.etp.utils_parser import parse_requirements_response_safely
    
    # Simulate the new JSON format that should work
    new_format_json = '''
    {
        "suggested_requirements": [
            {"id": "R1", "text": "Requisito 1", "justification": "Justificativa 1"},
            {"id": "R2", "text": "Requisito 2", "justification": "Justificativa 2"}
        ],
        "consultative_message": "Requisitos sugeridos baseados na necessidade identificada"
    }
    '''
    
    print("[DEBUG_LOG] Testing parser with new format...")
    result = parse_requirements_response_safely(new_format_json)
    print(f"[DEBUG_LOG] New format result: {result}")
    
    # This should parse successfully
    if (isinstance(result, dict) and 
        'suggested_requirements' in result and 
        'consultative_message' in result and
        len(result['suggested_requirements']) == 2):
        print("[DEBUG_LOG] ✓ New format correctly parsed")
        return True
    else:
        print("[DEBUG_LOG] ✗ New format parsing failed")
        return False

def test_parser_with_code_fences():
    """Test parser with JSON wrapped in code fences (common LLM response format)"""
    from domain.usecase.etp.utils_parser import parse_requirements_response_safely
    
    # Simulate JSON wrapped in code fences
    fenced_json = '''```json
    {
        "suggested_requirements": [
            {"id": "R1", "text": "Requisito 1", "justification": "Justificativa 1"}
        ],
        "consultative_message": "Requisitos com code fence"
    }
    ```'''
    
    print("[DEBUG_LOG] Testing parser with code fences...")
    result = parse_requirements_response_safely(fenced_json)
    print(f"[DEBUG_LOG] Fenced format result: {result}")
    
    if (isinstance(result, dict) and 
        'suggested_requirements' in result and 
        'consultative_message' in result):
        print("[DEBUG_LOG] ✓ Code fences correctly handled")
        return True
    else:
        print("[DEBUG_LOG] ✗ Code fences handling failed")
        return False

def test_parser_with_invalid_input():
    """Test parser with invalid inputs"""
    from domain.usecase.etp.utils_parser import parse_requirements_response_safely
    
    print("[DEBUG_LOG] Testing parser with invalid inputs...")
    
    # Test with empty string
    result1 = parse_requirements_response_safely("")
    print(f"[DEBUG_LOG] Empty string result: {result1}")
    
    # Test with None
    result2 = parse_requirements_response_safely(None)
    print(f"[DEBUG_LOG] None result: {result2}")
    
    # Test with invalid JSON
    result3 = parse_requirements_response_safely("invalid json {")
    print(f"[DEBUG_LOG] Invalid JSON result: {result3}")
    
    # All should return safe fallback
    expected_fallback = {
        'suggested_requirements': [],
        'consultative_message': 'Resposta inválida do sistema'
    }
    
    if (result1.get('suggested_requirements') == [] and 
        result2.get('suggested_requirements') == [] and
        result3.get('suggested_requirements') == []):
        print("[DEBUG_LOG] ✓ Invalid inputs correctly handled with fallbacks")
        return True
    else:
        print("[DEBUG_LOG] ✗ Invalid inputs handling failed")
        return False

def main():
    """Run all tests"""
    print("[DEBUG_LOG] Starting requirements parser fix validation tests...")
    
    tests = [
        ("Old format handling", test_parser_with_old_format),
        ("New format parsing", test_parser_with_new_format),
        ("Code fences handling", test_parser_with_code_fences),
        ("Invalid inputs handling", test_parser_with_invalid_input)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n[DEBUG_LOG] Running test: {test_name}")
        try:
            if test_func():
                print(f"[DEBUG_LOG] ✓ {test_name} PASSED")
                passed += 1
            else:
                print(f"[DEBUG_LOG] ✗ {test_name} FAILED")
        except Exception as e:
            print(f"[DEBUG_LOG] ✗ {test_name} ERROR: {e}")
    
    print(f"\n[DEBUG_LOG] Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("[DEBUG_LOG] 🎉 All tests passed! The requirements suggestion fix should work correctly.")
        return True
    else:
        print("[DEBUG_LOG] ❌ Some tests failed. The fix may need additional work.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)