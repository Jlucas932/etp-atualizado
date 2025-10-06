#!/usr/bin/env python3
"""
Test script to verify the RAG fixes for embedding column and PostgreSQL connection.
"""

import os
import sys
import traceback

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_kbchunk_model():
    """Test that KbChunk model has proper embedding column"""
    print("[TEST] Testing KbChunk model with ARRAY(Float) embedding column...")
    
    try:
        # Set test environment variables
        os.environ['OPENAI_API_KEY'] = 'test_api_key'
        os.environ['SECRET_KEY'] = 'test_secret_key'
        os.environ['DB_VENDOR'] = 'postgresql'
        os.environ['DB_URL'] = 'postgresql+psycopg2://test:test@localhost:5432/test_db'
        os.environ['EMBEDDINGS_PROVIDER'] = 'openai'
        os.environ['RAG_FAISS_PATH'] = 'test_rag'
        
        from domain.dto.KbDto import KbChunk
        from sqlalchemy.dialects.postgresql import ARRAY
        from sqlalchemy import Float
        
        # Check that embedding column exists and has correct type
        embedding_column = KbChunk.__table__.columns.get('embedding')
        
        if embedding_column is None:
            print("✗ ERROR: embedding column not found in KbChunk model")
            return False
        
        # Check if column type is PostgreSQL ARRAY
        column_type = embedding_column.type
        is_array = isinstance(column_type, ARRAY)
        is_float_array = is_array and isinstance(column_type.item_type, Float)
        
        if not is_array:
            print(f"✗ ERROR: embedding column type is {type(column_type)}, expected ARRAY")
            return False
            
        if not is_float_array:
            print(f"✗ ERROR: embedding column item type is {type(column_type.item_type)}, expected Float")
            return False
        
        print("✓ KbChunk model has correct ARRAY(Float) embedding column")
        return True
        
    except Exception as e:
        print(f"✗ KbChunk model test failed: {e}")
        traceback.print_exc()
        return False

def test_rag_retrieval_import():
    """Test that RAG retrieval imports correctly without SQLite"""
    print("\n[TEST] Testing RAG retrieval import without SQLite dependencies...")
    
    try:
        from rag.retrieval import RAGRetrieval
        
        # Create instance without database_url parameter (should not default to SQLite)
        retrieval = RAGRetrieval()
        
        # Check that no SQLite-specific attributes exist
        if hasattr(retrieval, 'database_url'):
            print("✗ ERROR: RAGRetrieval still has database_url attribute")
            return False
            
        if hasattr(retrieval, 'engine'):
            print("✗ ERROR: RAGRetrieval still has custom engine attribute")
            return False
            
        if hasattr(retrieval, 'SessionLocal'):
            print("✗ ERROR: RAGRetrieval still has SessionLocal attribute")
            return False
        
        print("✓ RAGRetrieval no longer has SQLite-specific attributes")
        return True
        
    except Exception as e:
        print(f"✗ RAG retrieval import test failed: {e}")
        traceback.print_exc()
        return False

def test_database_config():
    """Test that database configuration works with PostgreSQL"""
    print("\n[TEST] Testing database configuration with PostgreSQL...")
    
    try:
        from application.config.FlaskConfig import create_api
        
        app = create_api()
        
        with app.app_context():
            from domain.interfaces.dataprovider.DatabaseConfig import db
            
            # Check that database URI is PostgreSQL
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            
            if 'sqlite' in db_uri.lower():
                print(f"✗ ERROR: Database still using SQLite: {db_uri}")
                return False
                
            if 'postgresql' not in db_uri.lower():
                print(f"✗ ERROR: Database not using PostgreSQL: {db_uri}")
                return False
            
            print(f"✓ Database configured with PostgreSQL: {db_uri[:50]}...")
            return True
        
    except Exception as e:
        print(f"✗ Database configuration test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("Testing RAG fixes for embedding column and PostgreSQL connection\n")
    
    tests = [
        test_kbchunk_model,
        test_rag_retrieval_import,
        test_database_config,
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test_func.__name__} crashed: {e}")
            traceback.print_exc()
    
    print(f"\n=== RESULTS ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! RAG fixes should resolve the issues.")
        print("✓ KbChunk model now uses ARRAY(Float) for embeddings")
        print("✓ RAG retrieval no longer uses custom SQLite connections")
        print("✓ Database configuration properly uses PostgreSQL")
    else:
        print(f"✗ {total - passed} tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)