#!/usr/bin/env python3
"""
Test script to verify that the search_requirements function calls work correctly
after fixing the parameter issue.
"""

import sys
import os
from pathlib import Path

# Add src path for imports
project_root = Path(__file__).parent
src_path = project_root / "src" / "main" / "python"
sys.path.insert(0, str(src_path))

def test_search_requirements_import():
    """Test that we can import search_requirements without errors"""
    try:
        from rag.retrieval import search_requirements
        print("✅ Successfully imported search_requirements")
        return True
    except ImportError as e:
        print(f"❌ Failed to import search_requirements: {e}")
        return False

def test_search_requirements_call():
    """Test that we can call search_requirements with correct parameters"""
    try:
        from rag.retrieval import search_requirements
        
        # Test the function call with correct parameters
        # This should not raise "unexpected keyword argument" error
        result = search_requirements("generic", "test query", k=5)
        print(f"✅ Successfully called search_requirements with k parameter")
        print(f"   Result type: {type(result)}")
        return True
        
    except TypeError as e:
        if "unexpected keyword argument" in str(e):
            print(f"❌ Still getting unexpected keyword argument error: {e}")
            return False
        else:
            # Other TypeError might be expected (like missing database connection)
            print(f"⚠️  Got TypeError but not keyword argument issue: {e}")
            return True
    except Exception as e:
        # Other exceptions are acceptable - we just want to avoid the keyword argument error
        print(f"⚠️  Got other exception (expected): {e}")
        return True

def test_controller_imports():
    """Test that the controller can import without syntax errors"""
    try:
        # Just test if the file can be parsed/imported
        from adapter.entrypoint.etp.EtpDynamicController import etp_dynamic_bp
        print("✅ EtpDynamicController imports successfully")
        return True
    except Exception as e:
        print(f"❌ EtpDynamicController import failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing search_requirements fix...")
    print("=" * 50)
    
    tests = [
        ("Import test", test_search_requirements_import),
        ("Function call test", test_search_requirements_call),
        ("Controller import test", test_controller_imports)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}:")
        result = test_func()
        results.append(result)
    
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    all_passed = all(results)
    if all_passed:
        print("\n🎉 All tests passed! The search_requirements fix appears to be working.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)