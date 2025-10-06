#!/usr/bin/env python3
"""
Test script to reproduce the canned responses issue in AutoDoc-IA
"""

import os
import sys
import json
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://localhost:5002"

def test_canned_responses_issue():
    """Test to reproduce the canned responses issue"""
    logger.info("🧪 Testing canned responses issue...")
    
    test_cases = [
        {
            "name": "Software de gestão documental",
            "message": "Precisamos de um software para gestão documental específico para cartórios",
            "description": "Should return specific requirements for document management software for notary offices"
        },
        {
            "name": "Equipamentos médicos",
            "message": "Necessitamos de equipamentos médicos para UTI neonatal",
            "description": "Should return specific requirements for neonatal ICU medical equipment"
        },
        {
            "name": "Serviços de jardinagem",
            "message": "Contratação de serviços de jardinagem para área verde do hospital",
            "description": "Should return specific requirements for hospital gardening services"
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        logger.info(f"\n📝 Testing: {test_case['name']}")
        
        try:
            # Make request to conversation endpoint
            payload = {
                "message": test_case["message"],
                "conversation_history": [],
                "answered_questions": [],
                "extracted_answers": {},
                "objective_slug": "test"
            }
            
            response = requests.post(
                f"{API_BASE_URL}/api/etp-dynamic/conversation",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                ai_response = data.get('ai_response', '')
                
                logger.info(f"✅ Response received:")
                logger.info(f"   {ai_response[:300]}...")
                
                # Analyze for generic patterns
                generic_indicators = [
                    "anos de experiência",
                    "ISO 9001", 
                    "NBR 9050",
                    "certificação",
                    "regularidade fiscal",
                    "atestados de capacidade técnica"
                ]
                
                found_generic = []
                for indicator in generic_indicators:
                    if indicator.lower() in ai_response.lower():
                        found_generic.append(indicator)
                
                # Check if response is contextual or generic
                is_generic = len(found_generic) >= 3  # If 3+ generic indicators found
                
                results.append({
                    'test_case': test_case['name'],
                    'is_generic': is_generic,
                    'generic_indicators': found_generic,
                    'response_length': len(ai_response),
                    'success': True
                })
                
                if is_generic:
                    logger.warning(f"⚠️  ISSUE CONFIRMED: Generic response detected")
                    logger.warning(f"   Generic indicators found: {', '.join(found_generic)}")
                else:
                    logger.info(f"✅ Response appears contextual")
                    
            else:
                logger.error(f"❌ Request failed - Status: {response.status_code}")
                results.append({
                    'test_case': test_case['name'],
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                })
                
        except Exception as e:
            logger.error(f"❌ Error testing {test_case['name']}: {e}")
            results.append({
                'test_case': test_case['name'],
                'success': False,
                'error': str(e)
            })
    
    # Summary
    logger.info(f"\n📊 ISSUE REPRODUCTION RESULTS:")
    successful_tests = [r for r in results if r.get('success', False)]
    generic_responses = [r for r in successful_tests if r.get('is_generic', False)]
    
    logger.info(f"   ✅ Successful tests: {len(successful_tests)}/{len(test_cases)}")
    logger.info(f"   ⚠️  Generic responses: {len(generic_responses)}/{len(successful_tests)}")
    
    if generic_responses:
        logger.info(f"🔍 CANNED RESPONSES ISSUE CONFIRMED!")
        logger.info(f"   The system is generating generic responses instead of consulting PDFs via RAG")
        for result in generic_responses:
            logger.info(f"   - {result['test_case']}: {', '.join(result['generic_indicators'])}")
    else:
        logger.info(f"✅ No generic responses detected - issue may be resolved or requires different test cases")
    
    return len(generic_responses) > 0

def test_health_first():
    """Test if API is available"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/etp-dynamic/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ API Health OK - OpenAI configured: {data.get('openai_configured')}")
            return True
        else:
            logger.error(f"❌ Health check failed - Status: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Cannot connect to API: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🚀 Starting canned responses issue reproduction test")
    
    # Check if API is available
    if not test_health_first():
        logger.error("❌ API not available. Make sure the application is running on localhost:5002")
        return False
    
    # Run the actual test
    issue_confirmed = test_canned_responses_issue()
    
    if issue_confirmed:
        logger.info("🎯 ISSUE CONFIRMED: System generates canned responses instead of using RAG properly")
        logger.info("🔧 Next steps: Fix the RAG integration and DynamicPromptGenerator")
    else:
        logger.info("🤔 Issue not reproduced with current test cases")
    
    return issue_confirmed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)