#!/usr/bin/env python3
"""
Simple test to verify circular import is fixed
"""

import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_imports():
    """Test that modules can be imported without circular dependency"""
    
    print("Testing simple imports to verify circular import fix...")
    
    try:
        # Test the import chain that was causing circular dependency
        print("1. Importing init_etp_dynamic...")
        from domain.services.etp_dynamic import init_etp_dynamic
        print("✅ etp_dynamic module imported successfully")
        
        print("2. Importing etp_dynamic_bp blueprint...")
        from adapter.entrypoint.etp.EtpDynamicController import etp_dynamic_bp
        print("✅ EtpDynamicController blueprint imported successfully")
        
        print("3. Testing that init_etp_dynamic is callable...")
        assert callable(init_etp_dynamic)
        print("✅ init_etp_dynamic is a callable function")
        
        print("\n🎉 SUCCESS: Circular import has been fixed!")
        print("The modules can now be imported without circular dependency errors.")
        return True
        
    except ImportError as e:
        if "cannot import name" in str(e) and "partially initialized module" in str(e):
            print(f"❌ FAILED: Circular import still exists: {e}")
            return False
        else:
            print(f"❌ FAILED: Import error (not circular): {e}")
            return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n✅ All tests passed - circular import issue is resolved!")
    else:
        print("\n❌ Tests failed - circular import issue persists!")
    sys.exit(0 if success else 1)