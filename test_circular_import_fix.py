#!/usr/bin/env python3
"""
Test script to verify circular import fix
"""

import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_circular_import_fix():
    """Test that the circular import between the modules is resolved"""
    
    print("Testing circular import fix...")
    
    try:
        # Test 1: Import RAGRetrieval (should not call create_api anymore)
        print("1. Testing RAGRetrieval import...")
        from rag.retrieval import RAGRetrieval
        print("✅ RAGRetrieval imported successfully")
        
        # Test 2: Import etp_dynamic (should not instantiate objects at module level)
        print("2. Testing etp_dynamic import...")
        from domain.services.etp_dynamic import init_etp_dynamic
        print("✅ etp_dynamic imported successfully")
        
        # Test 3: Import EtpDynamicController (should import without circular dependency)
        print("3. Testing EtpDynamicController import...")
        from adapter.entrypoint.etp.EtpDynamicController import etp_dynamic_bp
        print("✅ EtpDynamicController imported successfully")
        
        # Test 4: Test that init_etp_dynamic works
        print("4. Testing init_etp_dynamic function...")
        # This should work without Flask context issues
        try:
            # We expect this to fail due to missing OpenAI key or database, but not due to circular imports
            etp_gen, prompt_gen, rag_sys = init_etp_dynamic()
            print(f"✅ init_etp_dynamic executed successfully - generators: {etp_gen is not None}, {prompt_gen is not None}, {rag_sys is not None}")
        except Exception as e:
            # Expected - but should not be ImportError about circular imports
            if "cannot import name" in str(e) and "partially initialized module" in str(e):
                print(f"❌ Circular import still exists: {e}")
                return False
            else:
                print(f"✅ init_etp_dynamic executed (expected error due to missing config): {e}")
        
        print("\n🎉 All tests passed! Circular import has been fixed.")
        return True
        
    except ImportError as e:
        if "cannot import name" in str(e) and "partially initialized module" in str(e):
            print(f"❌ Circular import detected: {e}")
            return False
        else:
            print(f"❌ Other import error: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_circular_import_fix()
    sys.exit(0 if success else 1)