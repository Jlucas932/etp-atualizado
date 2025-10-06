#!/usr/bin/env python3
"""
Test script to verify the conversation flow fix for ETP Dynamic Controller
Tests that:
1. Necessity is locked after first identification
2. conversation_stage progresses correctly
3. Requirement modifications work properly
4. Restart keywords work correctly
"""

import os
import sys
import json
import requests
import time

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

BASE_URL = "http://localhost:5002"
API_BASE = f"{BASE_URL}/api/etp-dynamic"

def test_conversation_flow():
    """Test the complete conversation flow"""
    print("🧪 Testing ETP Dynamic Conversation Flow")
    print("=" * 50)
    
    session_id = f"test-{int(time.time())}"
    
    # Test 1: First message should capture necessity and set conversation_stage to suggest_requirements
    print("\n1. Testing necessity capture and conversation_stage update...")
    
    response = requests.post(f"{API_BASE}/conversation", json={
        "message": "Preciso contratar notebooks para os funcionários da empresa",
        "session_id": session_id,
        "conversation_history": []
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ First response successful")
        print(f"   - Success: {data.get('success')}")
        print(f"   - Conversation stage: {data.get('conversation_stage')}")
        print(f"   - Kind: {data.get('kind')}")
        print(f"   - Necessity: {data.get('necessity')}")
        
        if data.get('conversation_stage') == 'suggest_requirements':
            print("✅ Conversation stage correctly set to 'suggest_requirements'")
        else:
            print("❌ Conversation stage should be 'suggest_requirements'")
            return False
            
        if data.get('necessity'):
            print("✅ Necessity captured successfully")
        else:
            print("❌ Necessity not captured")
            return False
    else:
        print(f"❌ First request failed: {response.status_code} - {response.text}")
        return False
    
    # Test 2: Modification message should update requirements, not restart necessity
    print("\n2. Testing requirement modification (should NOT restart necessity)...")
    
    response = requests.post(f"{API_BASE}/conversation", json={
        "message": "não gostei do R5, pode sugerir outro?",
        "session_id": session_id,
        "conversation_history": []
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Modification response successful")
        print(f"   - Success: {data.get('success')}")
        print(f"   - Kind: {data.get('kind')}")
        print(f"   - Conversation stage: {data.get('conversation_stage')}")
        
        if data.get('kind') == 'requirements_update':
            print("✅ Correctly identified as requirements_update")
        elif data.get('conversation_stage') in ['suggest_requirements', 'review_requirements']:
            print("✅ Conversation stage maintained correctly")
        else:
            print(f"❌ Unexpected response kind: {data.get('kind')} or stage: {data.get('conversation_stage')}")
            return False
    else:
        print(f"❌ Modification request failed: {response.status_code} - {response.text}")
        return False
    
    # Test 3: "pode manter" should not restart necessity
    print("\n3. Testing 'pode manter' (should maintain current state)...")
    
    response = requests.post(f"{API_BASE}/conversation", json={
        "message": "pode manter",
        "session_id": session_id,
        "conversation_history": []
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 'Pode manter' response successful")
        print(f"   - Success: {data.get('success')}")
        print(f"   - Kind: {data.get('kind')}")
        print(f"   - Conversation stage: {data.get('conversation_stage')}")
        
        if data.get('conversation_stage') != 'collect_need':
            print("✅ Conversation stage not reset to collect_need")
        else:
            print("❌ Conversation stage incorrectly reset to collect_need")
            return False
    else:
        print(f"❌ 'Pode manter' request failed: {response.status_code} - {response.text}")
        return False
    
    # Test 4: Explicit restart trigger should work
    print("\n4. Testing explicit restart trigger...")
    
    response = requests.post(f"{API_BASE}/conversation", json={
        "message": "na verdade a necessidade é contratar impressoras",
        "session_id": session_id,
        "conversation_history": []
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Restart trigger response successful")
        print(f"   - Success: {data.get('success')}")
        print(f"   - Conversation stage: {data.get('conversation_stage')}")
        
        if data.get('conversation_stage') == 'collect_need':
            print("✅ Conversation stage correctly reset to 'collect_need'")
        else:
            print(f"❌ Conversation stage should be 'collect_need', got: {data.get('conversation_stage')}")
            return False
    else:
        print(f"❌ Restart trigger request failed: {response.status_code} - {response.text}")
        return False
    
    print("\n🎉 All tests passed! The conversation flow is working correctly.")
    return True

def check_server():
    """Check if the server is running"""
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Please start the server first.")
        return False

if __name__ == "__main__":
    print("🚀 Starting ETP Dynamic Conversation Flow Test")
    
    if not check_server():
        print("\nPlease start the server first:")
        print("python3 src/main/python/applicationApi.py")
        sys.exit(1)
    
    success = test_conversation_flow()
    
    if success:
        print("\n✅ All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)