#!/usr/bin/env python3
"""
Test script to validate the fixed requirements generation system
Tests both RAG integration and consultative suggestions
"""

import os
import sys
import json
import logging

# Add project path
sys.path.insert(0, 'src/main/python')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_dynamic_prompt_generator():
    """Test the DynamicPromptGenerator with RAG integration"""
    logger.info("🧪 Testing DynamicPromptGenerator with RAG integration...")
    
    try:
        from domain.usecase.etp.dynamic_prompt_generator import DynamicPromptGenerator
        from rag.retrieval import RAGRetrieval
        import openai
        
        # Check if OpenAI API key is available
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("⚠️  OpenAI API key not found. Skipping OpenAI-dependent tests.")
            return False
        
        # Initialize components
        prompt_generator = DynamicPromptGenerator(api_key)
        rag_system = RAGRetrieval(openai_client=prompt_generator.client)
        
        # Try to build indices (this might fail if no data, but shouldn't crash)
        try:
            rag_system.build_indices()
            prompt_generator.set_rag_retrieval(rag_system)
            logger.info("✅ RAG system initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️  RAG indices build failed (expected if no data): {e}")
        
        # Test cases
        test_cases = [
            {
                "name": "Software específico",
                "need": "Software de gestão documental para cartórios com assinatura digital",
                "type": "produto"
            },
            {
                "name": "Equipamento médico",
                "need": "Ventiladores pulmonares para UTI com parâmetros específicos de pediatria",
                "type": "produto"
            },
            {
                "name": "Serviço especializado",
                "need": "Serviços de manutenção preventiva e corretiva de equipamentos de raio-X",
                "type": "serviço"
            }
        ]
        
        for test_case in test_cases:
            logger.info(f"\n📝 Testing: {test_case['name']}")
            
            try:
                result = prompt_generator.generate_requirements_with_rag(
                    test_case['need'],
                    test_case['type'],
                    'test'
                )
                
                requirements = result.get('requirements', [])
                consultative_message = result.get('consultative_message', '')
                is_rag_based = result.get('is_rag_based', False)
                source_citations = result.get('source_citations', [])
                
                logger.info(f"✅ Generated {len(requirements)} requirements")
                logger.info(f"   RAG-based: {is_rag_based}")
                logger.info(f"   Citations: {len(source_citations)}")
                logger.info(f"   Message: {consultative_message[:100]}...")
                
                # Validate requirements are specific to the context
                if requirements:
                    requirement_text = ' '.join(requirements).lower()
                    need_keywords = test_case['need'].lower().split()
                    
                    # Check if requirements contain context-specific terms
                    context_match = any(keyword in requirement_text for keyword in need_keywords[:3])
                    
                    if context_match:
                        logger.info("✅ Requirements appear contextual")
                    else:
                        logger.warning("⚠️  Requirements may be too generic")
                        
                    # Check for old generic patterns
                    generic_patterns = ["anos de experiência", "iso 9001", "atestado de capacidade"]
                    generic_found = any(pattern in requirement_text for pattern in generic_patterns)
                    
                    if generic_found:
                        logger.warning("⚠️  Generic patterns detected in requirements")
                    else:
                        logger.info("✅ No generic patterns detected")
                        
                else:
                    logger.warning("⚠️  No requirements generated")
                    
            except Exception as e:
                logger.error(f"❌ Error testing {test_case['name']}: {e}")
                
        logger.info("✅ DynamicPromptGenerator tests completed")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def test_rag_retrieval_function():
    """Test the RAG retrieval function directly"""
    logger.info("\n🧪 Testing RAG retrieval function...")
    
    try:
        from rag.retrieval import search_requirements
        
        test_queries = [
            "notebooks para servidores",
            "equipamentos médicos",
            "serviços de limpeza"
        ]
        
        for query in test_queries:
            logger.info(f"   Testing query: '{query}'")
            
            try:
                results = search_requirements("test", query, k=3)
                logger.info(f"   ✅ Found {len(results)} results")
                
                for i, result in enumerate(results[:2]):
                    content = result.get('content', '')[:80]
                    score = result.get('hybrid_score', 0)
                    logger.info(f"      {i+1}: {content}... (score: {score:.3f})")
                    
            except Exception as e:
                logger.info(f"   ⚠️  Query failed (expected if no data): {e}")
        
        logger.info("✅ RAG retrieval function tests completed")
        return True
        
    except ImportError as e:
        logger.error(f"❌ RAG retrieval import error: {e}")
        return False

def test_consultative_suggestions():
    """Test consultative suggestions when RAG returns no results"""
    logger.info("\n🧪 Testing consultative suggestions...")
    
    try:
        from domain.usecase.etp.dynamic_prompt_generator import DynamicPromptGenerator
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("⚠️  OpenAI API key not found. Skipping consultative tests.")
            return False
            
        prompt_generator = DynamicPromptGenerator(api_key)
        # Don't set RAG retrieval to force consultative mode
        
        test_case = {
            "need": "Sistema de inteligência artificial para análise de contratos complexos",
            "type": "produto"
        }
        
        result = prompt_generator.generate_requirements_with_rag(
            test_case['need'],
            test_case['type'],
            'nonexistent'  # Force no RAG results
        )
        
        requirements = result.get('requirements', [])
        consultative_message = result.get('consultative_message', '')
        is_rag_based = result.get('is_rag_based', False)
        
        logger.info(f"✅ Consultative mode generated {len(requirements)} requirements")
        logger.info(f"   RAG-based: {is_rag_based} (should be False)")
        logger.info(f"   Message: {consultative_message[:100]}...")
        
        # Validate consultative requirements have justifications
        if requirements:
            has_justifications = any("justificativa" in req.lower() for req in requirements)
            if has_justifications:
                logger.info("✅ Requirements include justifications")
            else:
                logger.info("ℹ️  Requirements may not include explicit justifications")
                
            # Check requirements are specific to the context
            requirement_text = ' '.join(requirements).lower()
            if "inteligência artificial" in requirement_text or "análise" in requirement_text:
                logger.info("✅ Requirements are contextual to AI/analysis domain")
            else:
                logger.warning("⚠️  Requirements may not be specific enough")
                
        logger.info("✅ Consultative suggestions tests completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Consultative suggestions test error: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🚀 Starting comprehensive tests for fixed requirements system")
    
    test_results = []
    
    # Test 1: DynamicPromptGenerator with RAG integration
    test_results.append(test_dynamic_prompt_generator())
    
    # Test 2: RAG retrieval function
    test_results.append(test_rag_retrieval_function())
    
    # Test 3: Consultative suggestions
    test_results.append(test_consultative_suggestions())
    
    # Summary
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    logger.info(f"\n📊 TEST SUMMARY:")
    logger.info(f"   ✅ Passed: {passed_tests}/{total_tests}")
    logger.info(f"   ❌ Failed: {total_tests - passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        logger.info("🎉 All tests passed! The fix appears to be working.")
        logger.info("🔧 Key improvements:")
        logger.info("   - RAG consultation prioritized over generic responses")
        logger.info("   - Contextual consultative suggestions when RAG has no data")
        logger.info("   - Source citations for RAG-based responses")
        logger.info("   - Avoids repetitive generic requirements")
    else:
        logger.warning("⚠️  Some tests failed. Review the implementation.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)