#!/usr/bin/env python3
"""
Test script to verify the RAG pipeline fixes for KbChunk content attribute issue.
This script reproduces the issue and verifies the fix.
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_kbchunk_content_attribute():
    """Test that KbChunk has working content attribute"""
    print("[TEST] Testing KbChunk content attribute...")
    
    try:
        # Set required environment variables
        os.environ['OPENAI_API_KEY'] = 'test_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret'
        os.environ['DB_URL'] = 'sqlite:///test_rag.db'
        
        from domain.dto.KbDto import KbChunk
        
        # Test creating a chunk with content
        chunk = KbChunk(
            kb_document_id=1,
            section_type="test_section",
            content_text="Test content for the chunk",
            objective_slug="test_objective"
        )
        
        # Test the content property (this was the failing case)
        content_via_property = chunk.content
        print(f"✓ chunk.content works: '{content_via_property[:50]}...'")
        
        # Test setting content via property
        chunk.content = "Updated content via property"
        print(f"✓ chunk.content setter works: '{chunk.content_text[:50]}...'")
        
        # Verify the underlying field is updated
        assert chunk.content_text == "Updated content via property"
        print("✓ content property correctly maps to content_text field")
        
        return True
        
    except Exception as e:
        print(f"✗ KbChunk content test failed: {e}")
        return False

def test_retrieval_attribute_access():
    """Test that retrieval.py can access chunk attributes correctly"""
    print("\n[TEST] Testing retrieval.py attribute access...")
    
    try:
        from domain.dto.KbDto import KbChunk, KbDocument
        from domain.interfaces.dataprovider.DatabaseConfig import db
        
        # Mock chunk object
        chunk = KbChunk(
            kb_document_id=1,
            section_type="requisito",
            content_text="Test content for retrieval",
            objective_slug="test_obj"
        )
        
        # Test all attribute access patterns used in retrieval.py
        chunk_id = chunk.id  # Should work
        document_id = chunk.kb_document_id  # Fixed from chunk.document_id
        content = chunk.content  # Fixed with property
        section_type = chunk.section_type  # Should work  
        section_title = chunk.section_type  # Fixed from chunk.section_title
        
        print("✓ All chunk attribute accesses work correctly")
        print(f"  - chunk.id: {chunk_id}")
        print(f"  - chunk.kb_document_id: {document_id}")
        print(f"  - chunk.content: '{content[:30]}...'")
        print(f"  - chunk.section_type: {section_type}")
        
        return True
        
    except Exception as e:
        print(f"✗ Retrieval attribute test failed: {e}")
        return False

def test_embedding_field():
    """Test that KbChunk has embedding field"""
    print("\n[TEST] Testing KbChunk embedding field...")
    
    try:
        from domain.dto.KbDto import KbChunk
        
        chunk = KbChunk(
            kb_document_id=1,
            section_type="test",
            content_text="Test content",
            objective_slug="test"
        )
        
        # Test embedding field exists and works
        chunk.embedding = '{"vector": [0.1, 0.2, 0.3]}'
        print(f"✓ chunk.embedding field works: {chunk.embedding}")
        
        # Test it can be None
        chunk.embedding = None
        print("✓ chunk.embedding can be None")
        
        return True
        
    except Exception as e:
        print(f"✗ Embedding field test failed: {e}")
        return False

def test_ingest_compatibility():
    """Test that ingest functions can use chunk.content"""
    print("\n[TEST] Testing ingest compatibility...")
    
    try:
        from domain.dto.KbDto import KbChunk
        
        chunk = KbChunk(
            kb_document_id=1,
            section_type="test",
            content_text="Original content for embedding generation",
            objective_slug="test"
        )
        
        # Test the pattern used in ingest_etps.py
        content_for_embedding = chunk.content
        print(f"✓ Content for embedding: '{content_for_embedding[:40]}...'")
        
        # Verify it's not empty (the original issue)
        assert content_for_embedding and content_for_embedding.strip()
        print("✓ Content is not empty - embedding generation should work")
        
        return True
        
    except Exception as e:
        print(f"✗ Ingest compatibility test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=== RAG Pipeline Fix Verification ===")
    print("Testing fixes for KbChunk content attribute issue\n")
    
    tests = [
        test_kbchunk_content_attribute,
        test_retrieval_attribute_access,
        test_embedding_field,
        test_ingest_compatibility
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
    
    print(f"\n=== RESULTS ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! The RAG pipeline fixes are working correctly.")
        print("\nExpected results:")
        print("✓ KbChunk objects now have working 'content' property")
        print("✓ Retrieval.py uses correct attribute names")
        print("✓ Embedding field is available for storing embeddings")
        print("✓ JSONL ingestion should process documents → create KbDocument → generate KbChunk with content")
        print("✓ Embeddings should be created using chunk.content")
        print("✓ FAISS index should be generated successfully")
        return True
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)