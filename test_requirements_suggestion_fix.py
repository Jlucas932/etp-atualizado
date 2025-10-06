#!/usr/bin/env python3
"""
Test script to validate the fix for requirements suggestion error
Tests the parse_requirements_response_safely function with different input formats
"""

import sys
import os
import json

# Add the src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_parse_requirements_function():
    """Test the parse_requirements_response_safely function directly"""
    
    try:
        from domain.usecase.etp.utils_parser import parse_requirements_response_safely
        print("[DEBUG_LOG] Successfully imported parse_requirements_response_safely")
        
        # Test Case 1: Legacy format with list of strings
        print("\n=== Test Case 1: Legacy format with strings ===")
        legacy_string_response = json.dumps({
            "requirements": [
                "Sistema deve ter interface web responsiva",
                "Deve suportar até 1000 usuários simultâneos",
                "Backup automático diário"
            ]
        })
        
        result1 = parse_requirements_response_safely(legacy_string_response)
        print(f"[DEBUG_LOG] Result 1: {json.dumps(result1, indent=2)}")
        
        # Verify the strings were converted to dicts
        requirements1 = result1.get('suggested_requirements', [])
        if requirements1 and all(isinstance(req, dict) and 'description' in req for req in requirements1):
            print("[DEBUG_LOG] ✓ Test 1 PASSED: Strings converted to dicts with 'description' key")
        else:
            print("[DEBUG_LOG] ✗ Test 1 FAILED: String conversion failed")
            
        # Test Case 2: Legacy format with list of dictionaries
        print("\n=== Test Case 2: Legacy format with dictionaries ===")
        legacy_dict_response = json.dumps({
            "requirements": [
                {"id": "R1", "text": "Sistema web responsivo", "justification": "Usabilidade"},
                {"id": "R2", "text": "Suporte a 1000 usuários", "justification": "Escalabilidade"}
            ]
        })
        
        result2 = parse_requirements_response_safely(legacy_dict_response)
        print(f"[DEBUG_LOG] Result 2: {json.dumps(result2, indent=2)}")
        
        # Verify the dicts were preserved
        requirements2 = result2.get('suggested_requirements', [])
        if requirements2 and all(isinstance(req, dict) for req in requirements2):
            print("[DEBUG_LOG] ✓ Test 2 PASSED: Dictionaries preserved")
        else:
            print("[DEBUG_LOG] ✗ Test 2 FAILED: Dictionary preservation failed")
            
        # Test Case 3: Mixed format (strings and dicts)
        print("\n=== Test Case 3: Mixed format ===")
        mixed_response = json.dumps({
            "requirements": [
                "Sistema deve ter backup automático",
                {"id": "R2", "text": "Interface responsiva", "justification": "UX"},
                "Suporte a múltiplos idiomas"
            ]
        })
        
        result3 = parse_requirements_response_safely(mixed_response)
        print(f"[DEBUG_LOG] Result 3: {json.dumps(result3, indent=2)}")
        
        # Verify mixed format was handled
        requirements3 = result3.get('suggested_requirements', [])
        if requirements3 and all(isinstance(req, dict) for req in requirements3):
            print("[DEBUG_LOG] ✓ Test 3 PASSED: Mixed format handled correctly")
        else:
            print("[DEBUG_LOG] ✗ Test 3 FAILED: Mixed format handling failed")
            
        # Test Case 4: New expected format (should work as before)
        print("\n=== Test Case 4: New expected format ===")
        new_format_response = json.dumps({
            "suggested_requirements": [
                {"id": "R1", "text": "Sistema web", "justification": "Necessário"},
                {"id": "R2", "text": "Backup diário", "justification": "Segurança"}
            ],
            "consultative_message": "Requisitos sugeridos baseados na análise"
        })
        
        result4 = parse_requirements_response_safely(new_format_response)
        print(f"[DEBUG_LOG] Result 4: {json.dumps(result4, indent=2)}")
        
        if 'suggested_requirements' in result4 and 'consultative_message' in result4:
            print("[DEBUG_LOG] ✓ Test 4 PASSED: New format works correctly")
        else:
            print("[DEBUG_LOG] ✗ Test 4 FAILED: New format handling broken")
            
        print("\n=== Summary ===")
        print("[DEBUG_LOG] All tests completed. The fix should handle both string and dict legacy formats correctly.")
        return True
        
    except Exception as e:
        print(f"[DEBUG_LOG] Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("[DEBUG_LOG] Starting requirements suggestion fix validation...")
    success = test_parse_requirements_function()
    if success:
        print("[DEBUG_LOG] Test completed successfully")
        exit(0)
    else:
        print("[DEBUG_LOG] Test failed")
        exit(1)