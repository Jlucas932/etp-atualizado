#!/usr/bin/env python3
"""
Test script for KbController multiple PDF upload functionality
"""
import os
import sys
import tempfile
import requests
from fpdf import FPDF

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def create_test_pdf(filename, content):
    """Create a test PDF file"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(40, 10, content)
    pdf.output(filename, 'F')
    return filename

def test_single_file_upload():
    """Test single file upload (backward compatibility)"""
    print("\n=== Testing Single File Upload ===")
    
    # Create test PDF
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        test_pdf = create_test_pdf(tmp.name, "Test PDF Content 1")
    
    try:
        # Test single file upload
        with open(test_pdf, 'rb') as f:
            files = {'file': ('test1.pdf', f, 'application/pdf')}
            response = requests.post(
                'http://localhost:5002/api/kb/upload',
                files=files,
                data={'objective_slug': 'test'}
            )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and len(data['results']) == 1:
                print("✓ Single file upload working correctly")
                return True
            else:
                print("✗ Single file upload response format incorrect")
                return False
        else:
            print(f"✗ Single file upload failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing single file upload: {e}")
        return False
    finally:
        if os.path.exists(test_pdf):
            os.remove(test_pdf)

def test_multiple_files_upload():
    """Test multiple files upload"""
    print("\n=== Testing Multiple Files Upload ===")
    
    # Create test PDFs
    test_pdfs = []
    try:
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                test_pdf = create_test_pdf(tmp.name, f"Test PDF Content {i+1}")
                test_pdfs.append(test_pdf)
        
        # Test multiple files upload
        files = []
        file_handles = []
        for i, pdf_path in enumerate(test_pdfs):
            f = open(pdf_path, 'rb')
            file_handles.append(f)
            files.append(('files', (f'test{i+1}.pdf', f, 'application/pdf')))
        
        try:
            response = requests.post(
                'http://localhost:5002/api/kb/upload',
                files=files,
                data={'objective_slug': 'test'}
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
            
            if response.status_code == 200:
                data = response.json()
                if 'results' in data and len(data['results']) == 3:
                    print("✓ Multiple files upload working correctly")
                    return True
                else:
                    print("✗ Multiple files upload response format incorrect")
                    return False
            else:
                print(f"✗ Multiple files upload failed: {response.text}")
                return False
                
        finally:
            for f in file_handles:
                f.close()
            
    except Exception as e:
        print(f"✗ Error testing multiple files upload: {e}")
        return False
    finally:
        for pdf_path in test_pdfs:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

def test_no_files_error():
    """Test error handling when no files are sent"""
    print("\n=== Testing No Files Error ===")
    
    try:
        response = requests.post(
            'http://localhost:5002/api/kb/upload',
            data={'objective_slug': 'test'}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 400:
            data = response.json()
            if 'error' in data and 'Nenhum arquivo enviado' in data['error']:
                print("✓ No files error handling working correctly")
                return True
            else:
                print("✗ No files error message incorrect")
                return False
        else:
            print("✗ No files error should return 400")
            return False
            
    except Exception as e:
        print(f"✗ Error testing no files error: {e}")
        return False

def test_non_pdf_error():
    """Test error handling for non-PDF files"""
    print("\n=== Testing Non-PDF Error ===")
    
    # Create a text file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as tmp:
        tmp.write("This is not a PDF")
        test_txt = tmp.name
    
    try:
        with open(test_txt, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            response = requests.post(
                'http://localhost:5002/api/kb/upload',
                files=files,
                data={'objective_slug': 'test'}
            )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 400:
            data = response.json()
            if 'error' in data and 'PDF' in data['error']:
                print("✓ Non-PDF error handling working correctly")
                return True
            else:
                print("✗ Non-PDF error message incorrect")
                return False
        else:
            print("✗ Non-PDF error should return 400")
            return False
            
    except Exception as e:
        print(f"✗ Error testing non-PDF error: {e}")
        return False
    finally:
        if os.path.exists(test_txt):
            os.remove(test_txt)

def main():
    """Run all tests"""
    print("Starting KbController Upload Tests...")
    
    # Check if server is running
    try:
        response = requests.get('http://localhost:5002/api/kb/health')
        if response.status_code != 200:
            print("✗ Server is not running or KB endpoint not available")
            return
    except:
        print("✗ Cannot connect to server at localhost:5002")
        return
    
    results = []
    results.append(test_single_file_upload())
    results.append(test_multiple_files_upload())
    results.append(test_no_files_error())
    results.append(test_non_pdf_error())
    
    print(f"\n=== Test Results ===")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")

if __name__ == '__main__':
    main()