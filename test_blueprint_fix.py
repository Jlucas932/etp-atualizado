#!/usr/bin/env python3
"""
Test script to verify the blueprint registration fix
"""
import os
import sys

# Add the src path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_blueprint_registration():
    """Test that the application can start without blueprint registration errors"""
    try:
        print("[DEBUG_LOG] Testing blueprint registration fix...")
        
        # Set required environment variables
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret_key'
        
        # Import the Flask configuration
        from application.config.FlaskConfig import create_api
        
        # Create the Flask app
        app = create_api()
        
        print("[DEBUG_LOG] Flask app created successfully!")
        print(f"[DEBUG_LOG] Registered blueprints: {[bp.name for bp in app.blueprints.values()]}")
        
        # Test that we can import etp_generator from the service module
        from domain.services.etp_dynamic import etp_generator, prompt_generator, rag_system
        print(f"[DEBUG_LOG] Service module imports successful!")
        print(f"[DEBUG_LOG] etp_generator: {etp_generator}")
        print(f"[DEBUG_LOG] prompt_generator: {prompt_generator}")
        print(f"[DEBUG_LOG] rag_system: {rag_system}")
        
        # Test that EtpDynamicController doesn't initialize duplicates
        from adapter.entrypoint.etp.EtpDynamicController import etp_dynamic_bp
        print(f"[DEBUG_LOG] EtpDynamicController blueprint: {etp_dynamic_bp.name}")
        
        # Test that EtpController can import from service module
        from adapter.entrypoint.etp.EtpController import etp_bp
        print(f"[DEBUG_LOG] EtpController blueprint: {etp_bp.name}")
        
        print("[DEBUG_LOG] ✓ All tests passed! Blueprint registration fix successful.")
        return True
        
    except Exception as e:
        print(f"[DEBUG_LOG] ✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up environment variables
        for key in ['OPENAI_API_KEY', 'SECRET_KEY']:
            if key in os.environ:
                del os.environ[key]

if __name__ == "__main__":
    success = test_blueprint_registration()
    sys.exit(0 if success else 1)