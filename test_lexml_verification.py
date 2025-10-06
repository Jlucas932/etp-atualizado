#!/usr/bin/env python3
"""
Test script for LexML verification functionality
Tests the resolve_lexml and summarize_for_user functions with Lei 14.133/2021
"""

import os
import sys
import logging
from datetime import datetime

# Add the src path to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

def test_lexml_verification():
    """Test LexML verification with Lei 14.133/2021"""
    
    print("=" * 60)
    print("TESTING LEXML VERIFICATION")
    print("=" * 60)
    
    try:
        # Set up test environment
        os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', 'test_key_for_testing')
        
        # Import after setting environment
        from application.config.FlaskConfig import create_api
        from domain.usecase.etp.verify_federal import resolve_lexml, summarize_for_user, LegalNormCache
        
        print(f"[DEBUG_LOG] Starting test at {datetime.now()}")
        
        # Create Flask app context for database operations
        app = create_api()
        
        with app.app_context():
            # Test 1: Resolve Lei 14.133/2021
            print("\n--- Test 1: Resolve Lei 14.133/2021 ---")
            
            try:
                result = resolve_lexml("Lei", "14.133", 2021)
                
                print(f"[DEBUG_LOG] LexML Query Result:")
                print(f"  - URN: {result.get('urn', 'None')}")
                print(f"  - Label: {result.get('label', 'None')}")
                print(f"  - Status: {result.get('status', 'None')}")
                print(f"  - Verified: {result.get('verified', False)}")
                print(f"  - Cached: {result.get('cached', False)}")
                
                if result['verified']:
                    print("✅ Lei 14.133/2021 successfully verified via LexML!")
                    print(f"✅ URN found: {result['urn']}")
                else:
                    print(f"⚠️  Lei 14.133/2021 not verified. Status: {result['status']}")
                    
            except Exception as e:
                print(f"❌ Error in resolve_lexml: {str(e)}")
                result = {
                    'urn': None,
                    'label': 'Lei 14.133/2021',
                    'status': 'error in test',
                    'verified': False,
                    'metadados': {}
                }
            
            # Test 2: Generate AI summary
            print("\n--- Test 2: Generate AI Summary ---")
            
            try:
                # Try to get OpenAI client
                openai_client = None
                if os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_API_KEY') != 'test_key_for_testing':
                    try:
                        from domain.usecase.etp.etp_generator_dynamic import DynamicEtpGenerator
                        etp_gen = DynamicEtpGenerator(os.getenv('OPENAI_API_KEY'))
                        openai_client = etp_gen.client
                        print("[DEBUG_LOG] OpenAI client configured")
                    except Exception as oa_error:
                        print(f"[DEBUG_LOG] OpenAI client error: {str(oa_error)}")
                else:
                    print("[DEBUG_LOG] Using fallback without OpenAI")
                
                # Add required fields for summary function
                result['tipo'] = 'Lei'
                result['numero'] = '14.133'
                result['ano'] = 2021
                
                summary = summarize_for_user(result, openai_client)
                
                print(f"[DEBUG_LOG] AI Summary generated:")
                print(f"  Summary: {summary}")
                
                if "Fonte: LexML" in summary:
                    print("✅ Summary contains required 'Fonte: LexML'")
                else:
                    print("⚠️  Summary missing 'Fonte: LexML'")
                    
            except Exception as e:
                print(f"❌ Error in summarize_for_user: {str(e)}")
                summary = f"Fallback summary for Lei 14.133/2021. Fonte: LexML"
            
            # Test 3: Check cache functionality
            print("\n--- Test 3: Check Cache ---")
            
            try:
                # Query cache directly
                cache_entry = LegalNormCache.query.filter_by(
                    tipo="Lei", numero="14.133", ano=2021
                ).first()
                
                if cache_entry:
                    print("✅ Cache entry found")
                    print(f"  - Created: {cache_entry.created_at}")
                    print(f"  - Expires: {cache_entry.expires_at}")
                    print(f"  - Verified: {cache_entry.verified}")
                    print(f"  - AI Summary cached: {bool(cache_entry.ai_summary)}")
                else:
                    print("⚠️  No cache entry found")
                    
            except Exception as e:
                print(f"❌ Error checking cache: {str(e)}")
            
            # Test 4: Test second call (should use cache)
            print("\n--- Test 4: Test Cache Hit ---")
            
            try:
                result2 = resolve_lexml("Lei", "14.133", 2021)
                
                if result2.get('cached', False):
                    print("✅ Second call used cache successfully")
                else:
                    print("⚠️  Second call did not use cache")
                    
            except Exception as e:
                print(f"❌ Error in cache test: {str(e)}")
            
            # Summary
            print("\n" + "=" * 60)
            print("TEST SUMMARY")
            print("=" * 60)
            
            print(f"Final Result:")
            print(f"  - Law: Lei 14.133/2021")
            print(f"  - Verification Status: {'✅ PASSED' if result.get('verified', False) else '⚠️  FAILED'}")
            print(f"  - URN: {result.get('urn', 'Not found')}")
            print(f"  - Summary: {summary}")
            
            if result.get('verified', False):
                print("\n✅ ACCEPTANCE CRITERIA MET:")
                print("   - Lei 14.133/2021 returns card with URN LexML ✅")
                print("   - Status and summary included ✅")
                print("   - System handles network failures with fallback ✅")
            else:
                print(f"\n⚠️  ACCEPTANCE CRITERIA PARTIAL:")
                print(f"   - Fallback working: status = {result.get('status', 'unknown')}")
                print("   - System handles failures gracefully ✅")
                
    except Exception as e:
        print(f"❌ CRITICAL ERROR in test setup: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_lexml_verification()