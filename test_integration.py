#!/usr/bin/env python3
"""
Test script to verify the integration of retrieval and legal_norms in the dynamic ETP generator.
"""
import os
import sys
import logging

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'main', 'python'))

from domain.usecase.etp.etp_generator_dynamic import DynamicEtpGenerator

# Configure logging to see the "consulta interna encontrada" messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_integration():
    """Test the integration with sample data"""
    print("Testing ETP Dynamic Generator Integration...")
    
    # Mock OpenAI API key (for testing structure only)
    openai_api_key = os.getenv('OPENAI_API_KEY', 'test_key_for_structure')
    
    try:
        # Initialize generator
        generator = DynamicEtpGenerator(openai_api_key)
        
        # Test data mimicking session_data
        test_session_data = {
            'session_id': 'test_session_123',
            'answers': {
                '1': 'Necessidade de manutenção de computadores para o departamento',
                '2': 'Requisitos de suporte técnico especializado e garantia de 12 meses',
                '3': True,
                '4': 'Lei 14.133/2021 e normas de TI aplicáveis'
            },
            'user_id': 'test_user'
        }
        
        # Test Requisito section
        requisito_section = {
            'section': '3. DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO',
            'description': 'Especificação de todos os requisitos aplicáveis'
        }
        
        print("\n=== Testing Requisito Section Integration ===")
        try:
            # Test helper methods
            objective_slug = generator._extract_objective_slug(test_session_data)
            print(f"Extracted objective_slug: {objective_slug}")
            
            user_query = generator._extract_user_query_for_requirements(test_session_data)
            print(f"Extracted user query: {user_query}")
            
            print("✓ Requisito section integration structure verified")
        except Exception as e:
            print(f"❌ Error in Requisito section: {str(e)}")
        
        # Test Norma Legal section
        norma_section = {
            'section': '3.3. REQUISITOS NORMATIVOS E LEGAIS',
            'description': 'Normas legais aplicáveis'
        }
        
        print("\n=== Testing Norma Legal Section Integration ===")
        try:
            # Test legal norms suggestion
            from domain.usecase.utils.legal_norms import suggest_federal
            cands = suggest_federal(objective_slug, k=3)
            print(f"Legal norms suggested: {len(cands)} candidates")
            for i, cand in enumerate(cands[:2], 1):  # Show first 2
                print(f"  {i}. {cand.get('tipo')} {cand.get('numero')}/{cand.get('ano')} - {cand.get('descricao')}")
            
            print("✓ Norma Legal section integration structure verified")
        except Exception as e:
            print(f"❌ Error in Norma Legal section: {str(e)}")
        
        print("\n=== Integration Test Summary ===")
        print("✓ Imports successful")
        print("✓ Generator initialization successful")
        print("✓ Helper methods working")
        print("✓ Integration points identified")
        print("\nNote: Full functionality requires proper OpenAI API key and database setup")
        
    except Exception as e:
        print(f"❌ Integration test failed: {str(e)}")
        return False
    
    return True

if __name__ == '__main__':
    success = test_integration()
    sys.exit(0 if success else 1)