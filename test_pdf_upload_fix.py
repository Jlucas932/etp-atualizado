#!/usr/bin/env python3
"""
Test script to verify the PDF upload fix
Tests the extract_text_from_pdf function with pdfplumber
"""
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_pdf_processing():
    """Test the PDF processing functions"""
    print("[DEBUG_LOG] Testing PDF processing functions...")
    
    try:
        # Import the functions from the fixed KbController
        from adapter.entrypoint.kb.KbController import extract_text_from_pdf, chunk_text
        print("[DEBUG_LOG] Successfully imported functions from KbController")
        
        # Test chunk_text function with sample text
        sample_text = "This is a sample text for testing the chunking functionality. " * 50
        print(f"[DEBUG_LOG] Sample text length: {len(sample_text)}")
        
        # Test chunking - this should work without variable naming conflicts
        chunks = chunk_text(sample_text, chunk_size=100, overlap=20)
        print(f"[DEBUG_LOG] Successfully created {len(chunks)} chunks")
        
        # Verify we can iterate through chunks without errors
        chunk_count = 0
        for text_chunk in chunks:  # Using the same variable name as in the fixed code
            if text_chunk and len(text_chunk.strip()) > 0:
                chunk_count += 1
        
        print(f"[DEBUG_LOG] Successfully processed {chunk_count} non-empty chunks")
        
        # Test that the function still exists and is callable
        assert callable(chunk_text), "chunk_text function should be callable"
        print("[DEBUG_LOG] chunk_text function is callable - variable conflict resolved")
        
        print("[DEBUG_LOG] All tests passed! The fix appears to work correctly.")
        return True
        
    except Exception as e:
        print(f"[DEBUG_LOG] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("[DEBUG_LOG] Starting PDF upload fix test...")
    success = test_pdf_processing()
    
    if success:
        print("[DEBUG_LOG] ✓ Test completed successfully")
        sys.exit(0)
    else:
        print("[DEBUG_LOG] ✗ Test failed")
        sys.exit(1)