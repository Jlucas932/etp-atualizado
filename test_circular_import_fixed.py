#!/usr/bin/env python3
"""
Test script to verify that the circular import issue has been fixed.
Tests importing both FlaskConfig and ingest_etps modules without ImportError.
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
    print("🧪 Testing circular import fix...")
    
    try:
        print("1. Testing import of rag.ingest_etps...")
        from rag.ingest_etps import ETPIngestor
        print("   ✅ Successfully imported ETPIngestor")
        
        print("2. Testing import of application.config.FlaskConfig...")
        from application.config.FlaskConfig import create_api, auto_load_knowledge_base
        print("   ✅ Successfully imported FlaskConfig functions")
        
        print("3. Testing ETPIngestor instantiation...")
        ingestor = ETPIngestor()
        print("   ✅ Successfully created ETPIngestor instance")
        
        print("4. Testing ingest_initial_docs method exists...")
        if hasattr(ingestor, 'ingest_initial_docs'):
            print("   ✅ ingest_initial_docs method found")
        else:
            print("   ❌ ingest_initial_docs method not found")
            return False
        
        print("\n🎉 All tests passed! Circular import issue has been resolved.")
        return True
        
    except ImportError as e:
        print(f"❌ ImportError detected: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    # Set minimal environment variables to prevent validation errors
    os.environ.setdefault('OPENAI_API_KEY', 'test_key_for_testing')
    os.environ.setdefault('SECRET_KEY', 'test_secret_key')
    os.environ.setdefault('DB_VENDOR', 'sqlite')
    os.environ.setdefault('EMBEDDINGS_PROVIDER', 'openai')
    os.environ.setdefault('RAG_FAISS_PATH', 'rag/index/faiss')
    
    success = test_circular_import_fix()
    sys.exit(0 if success else 1)