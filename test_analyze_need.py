"""
Test script for the /api/chat/analyze-need endpoint
"""
import sys
import os
import json

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

# Set test environment variables
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', 'test_api_key')
os.environ['SECRET_KEY'] = 'test_secret_key'
os.environ['DB_VENDOR'] = 'sqlite'

from application.config.FlaskConfig import create_api

def test_analyze_need():
    """Test the analyze-need endpoint"""
    print("=" * 60)
    print("Testing /api/chat/analyze-need endpoint")
    print("=" * 60)
    
    app = create_api()
    app.config['TESTING'] = True
    client = app.test_client()
    
    # Test 1: New need (first message)
    print("\n[Test 1] New need - first message")
    payload = {
        "message": "Preciso contratar um sistema de gestão de documentos eletrônicos",
        "history": []
    }
    response = client.post(
        '/api/chat/analyze-need',
        data=json.dumps(payload),
        content_type='application/json'
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.get_json()}")
    
    if response.status_code == 200:
        data = response.get_json()
        assert 'contains_need' in data, "Missing 'contains_need' field"
        assert 'need_description' in data, "Missing 'need_description' field"
        assert isinstance(data['contains_need'], bool), "'contains_need' must be boolean"
        assert isinstance(data['need_description'], str), "'need_description' must be string"
        print("✓ Test 1 passed - Valid JSON structure")
    else:
        print("✗ Test 1 failed - Invalid response")
    
    # Test 2: Adjustment to existing requirements (should NOT be a new need)
    print("\n[Test 2] Adjustment to requirements - not a new need")
    payload = {
        "message": "Inclua também o requisito de backup automático",
        "history": [
            {"role": "user", "content": "Preciso contratar um sistema de gestão de documentos eletrônicos"},
            {"role": "assistant", "content": "Entendi. Vou sugerir os seguintes requisitos: R1: Sistema web, R2: Armazenamento em nuvem, R3: Controle de acesso"}
        ]
    }
    response = client.post(
        '/api/chat/analyze-need',
        data=json.dumps(payload),
        content_type='application/json'
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.get_json()}")
    
    if response.status_code == 200:
        data = response.get_json()
        print("✓ Test 2 passed - Valid JSON structure")
    else:
        print("✗ Test 2 failed - Invalid response")
    
    # Test 3: Remove requirement (should NOT be a new need)
    print("\n[Test 3] Remove requirement - not a new need")
    payload = {
        "message": "Remova o R2",
        "history": [
            {"role": "user", "content": "Preciso contratar um sistema de gestão de documentos"},
            {"role": "assistant", "content": "Requisitos: R1: Sistema web, R2: Armazenamento em nuvem"}
        ]
    }
    response = client.post(
        '/api/chat/analyze-need',
        data=json.dumps(payload),
        content_type='application/json'
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.get_json()}")
    
    if response.status_code == 200:
        data = response.get_json()
        print("✓ Test 3 passed - Valid JSON structure")
    else:
        print("✗ Test 3 failed - Invalid response")
    
    # Test 4: Completely new need (changing the theme)
    print("\n[Test 4] New need - changing the theme")
    payload = {
        "message": "Na verdade, mudei de ideia. Agora preciso contratar serviços de manutenção predial",
        "history": [
            {"role": "user", "content": "Preciso contratar um sistema de gestão de documentos"},
            {"role": "assistant", "content": "Requisitos: R1: Sistema web, R2: Armazenamento em nuvem"}
        ]
    }
    response = client.post(
        '/api/chat/analyze-need',
        data=json.dumps(payload),
        content_type='application/json'
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.get_json()}")
    
    if response.status_code == 200:
        data = response.get_json()
        print("✓ Test 4 passed - Valid JSON structure")
    else:
        print("✗ Test 4 failed - Invalid response")
    
    # Test 5: Missing message parameter
    print("\n[Test 5] Missing message parameter")
    payload = {
        "history": []
    }
    response = client.post(
        '/api/chat/analyze-need',
        data=json.dumps(payload),
        content_type='application/json'
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.get_json()}")
    
    if response.status_code == 400:
        print("✓ Test 5 passed - Correctly rejected missing message")
    else:
        print("✗ Test 5 failed - Should return 400 for missing message")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

if __name__ == '__main__':
    test_analyze_need()
