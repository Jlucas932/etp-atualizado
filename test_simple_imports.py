#!/usr/bin/env python3
"""
Simple test to verify imports work correctly after the blueprint fix
"""
import os
import sys

# Add the src path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_imports():
    """Test that imports work correctly without duplicate blueprint registration"""
    try:
        print("[DEBUG_LOG] Testing imports after blueprint registration fix...")
        
        # Set required environment variables
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        
        # Test 1: Import service module first
        print("[DEBUG_LOG] 1. Testing service module import...")
        from domain.services.etp_dynamic import etp_generator, prompt_generator, rag_system
        print(f"[DEBUG_LOG] ✓ Service module imported successfully!")
        print(f"[DEBUG_LOG]   - etp_generator: {type(etp_generator)}")
        print(f"[DEBUG_LOG]   - prompt_generator: {type(prompt_generator)}")
        print(f"[DEBUG_LOG]   - rag_system: {type(rag_system)}")
        
        # Test 2: Import EtpDynamicController (should not re-initialize)
        print("[DEBUG_LOG] 2. Testing EtpDynamicController import...")
        from adapter.entrypoint.etp.EtpDynamicController import etp_dynamic_bp
        print(f"[DEBUG_LOG] ✓ EtpDynamicController imported successfully!")
        print(f"[DEBUG_LOG]   - Blueprint name: {etp_dynamic_bp.name}")
        
        # Test 3: Import EtpController (should use service module)
        print("[DEBUG_LOG] 3. Testing EtpController import...")
        from adapter.entrypoint.etp.EtpController import etp_bp
        print(f"[DEBUG_LOG] ✓ EtpController imported successfully!")
        print(f"[DEBUG_LOG]   - Blueprint name: {etp_bp.name}")
        
        # Test 4: Verify the objects are the same instances
        print("[DEBUG_LOG] 4. Testing object identity...")
        from domain.services.etp_dynamic import etp_generator as service_generator
        from adapter.entrypoint.etp.EtpDynamicController import etp_generator as controller_generator
        
        print(f"[DEBUG_LOG] ✓ Service etp_generator: {id(service_generator)}")
        print(f"[DEBUG_LOG] ✓ Controller etp_generator: {id(controller_generator)}")
        print(f"[DEBUG_LOG] ✓ Same instance: {service_generator is controller_generator}")
        
        print("[DEBUG_LOG] ✓ All import tests passed! No blueprint registration errors.")
        return True
        
    except Exception as e:
        print(f"[DEBUG_LOG] ✗ Import test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up environment variables
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)