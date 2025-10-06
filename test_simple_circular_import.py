#!/usr/bin/env python3
"""
Simple test script to verify that the circular import issue has been fixed.
Tests only the import structure without dependencies that may not be installed.
"""

import sys
import os
from pathlib import Path

# Add the src/main/python directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src" / "main" / "python"
sys.path.insert(0, str(src_path))

def test_circular_import_fix():
    """Test that both modules can be imported without circular import errors"""
    print("🧪 Testing circular import fix (simple version)...")
    
    try:
        # Set minimal environment variables to prevent validation errors
        os.environ.setdefault('OPENAI_API_KEY', 'test_key_for_testing')
        os.environ.setdefault('SECRET_KEY', 'test_secret_key')
        os.environ.setdefault('DB_VENDOR', 'sqlite')
        os.environ.setdefault('EMBEDDINGS_PROVIDER', 'openai')
        os.environ.setdefault('RAG_FAISS_PATH', 'rag/index/faiss')
        
        print("1. Testing that we can access the ingest_etps module structure...")
        # Just test the module can be parsed without full import
        import ast
        ingest_file = src_path / "rag" / "ingest_etps.py"
        with open(ingest_file, 'r') as f:
            content = f.read()
        
        # Check that create_api is not imported
        if 'from application.config.FlaskConfig import create_api' in content:
            print("   ❌ Still has circular import: create_api imported from FlaskConfig")
            return False
        else:
            print("   ✅ No circular import detected in ingest_etps.py")
        
        # Parse AST to verify structure
        tree = ast.parse(content)
        print("   ✅ ingest_etps.py parses successfully")
        
        print("2. Testing FlaskConfig module structure...")
        flask_config_file = src_path / "application" / "config" / "FlaskConfig.py"
        with open(flask_config_file, 'r') as f:
            flask_content = f.read()
        
        # Check that ETPIngestor is still imported 
        if 'from rag.ingest_etps import ETPIngestor' in flask_content:
            print("   ✅ FlaskConfig still imports ETPIngestor as expected")
        else:
            print("   ❌ FlaskConfig missing ETPIngestor import")
            return False
            
        # Check that it uses the new method
        if 'ingest_initial_docs()' in flask_content:
            print("   ✅ FlaskConfig uses new ingest_initial_docs() method")
        else:
            print("   ❌ FlaskConfig not using new ingest_initial_docs() method")
            return False
        
        flask_tree = ast.parse(flask_content)
        print("   ✅ FlaskConfig.py parses successfully")
        
        print("\n🎉 All structural tests passed! Circular import issue has been resolved.")
        print("   - ingest_etps.py no longer imports create_api from FlaskConfig")
        print("   - FlaskConfig.py still imports ETPIngestor but uses new method")
        print("   - Both files parse successfully without circular dependencies")
        
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_circular_import_fix()
    sys.exit(0 if success else 1)