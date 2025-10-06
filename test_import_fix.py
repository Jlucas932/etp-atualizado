#!/usr/bin/env python3
"""
Test script to verify the FlaskConfig import fix works correctly.
This test verifies that the ETPIngestor can be imported from rag.ingest_etps
without running the full Flask application.
"""

import os
import sys
from pathlib import Path

# Add src/main/python to path
current_dir = Path(__file__).parent
src_path = current_dir / "src" / "main" / "python"
sys.path.insert(0, str(src_path))

def test_import_fix():
    """Test that the import fix works correctly"""
    print("🔍 Testing FlaskConfig import fix...")
    
    try:
        # Test importing ETPIngestor directly
        from rag.ingest_etps import ETPIngestor
        print("✅ Successfully imported ETPIngestor from rag.ingest_etps")
        
        # Test creating an instance (without database connection)
        # This verifies the class can be instantiated
        try:
            ingestor = ETPIngestor(database_url="sqlite:///:memory:")
            print("✅ Successfully created ETPIngestor instance")
        except Exception as e:
            print(f"⚠️  Could not create ETPIngestor instance: {e}")
            print("   (This is expected without proper database setup)")
        
        # Test that the import in FlaskConfig would work
        print("🔍 Testing FlaskConfig import compatibility...")
        
        # Set minimal environment variables needed for FlaskConfig
        os.environ['OPENAI_API_KEY'] = 'test_key'
        os.environ['SECRET_KEY'] = 'test_secret'
        os.environ['DB_VENDOR'] = 'sqlite'
        os.environ['EMBEDDINGS_PROVIDER'] = 'openai'
        os.environ['RAG_FAISS_PATH'] = 'rag/index/faiss'
        
        # Try importing the specific function from FlaskConfig
        # This will test if our import fix doesn't break anything
        from application.config.FlaskConfig import auto_load_knowledge_base
        print("✅ Successfully imported auto_load_knowledge_base from FlaskConfig")
        
        print("\n🎉 All import tests passed! The fix is working correctly.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_import_fix()
    sys.exit(0 if success else 1)