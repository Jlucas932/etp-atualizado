"""
PASSO 5 - Parser robusto e seguro para respostas do LLM
Tolerante a cercas ```json``` e sem fallback suicida
"""

import json
import re
import logging

logger = logging.getLogger(__name__)


def _strip_code_fences(s: str) -> str:
    """Remove code fences from JSON responses"""
    if not isinstance(s, str):
        return s
        
    s = s.strip()
    
    # Try to match ```json ... ``` pattern
    json_fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if json_fence_match:
        return json_fence_match.group(1)
    
    # Try to find JSON object boundaries
    start_brace = s.find('{')
    end_brace = s.rfind('}')
    
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        return s[start_brace:end_brace + 1]
    
    return s


def parse_json_relaxed(s: str):
    """
    Parse JSON with relaxed error handling
    Returns None if parsing fails instead of raising exceptions
    """
    if not isinstance(s, str) or not s.strip():
        logger.warning("parse_json_relaxed: Empty or invalid input")
        return None
    
    try:
        cleaned = _strip_code_fences(s)
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"parse_json_relaxed: JSON decode failed - {e}")
        return None
    except Exception as e:
        logger.warning(f"parse_json_relaxed: Unexpected error - {e}")
        return None


def analyze_need_safely(user_msg: str, openai_client):
    """
    Safely analyze if user message contains a necessity description
    NEVER promotes user_msg to necessity when contains_need=False or parse fails
    
    Returns:
        Tuple[bool, str]: (contains_need, need_description or None)
    """
    if not user_msg or not isinstance(user_msg, str):
        logger.warning("analyze_need_safely: Empty or invalid user message")
        return False, None
    
    try:
        # Call OpenAI need analyzer
        need_analysis_prompt = f"""
        Você é um assistente que responde sempre em JSON válido, sem adicionar explicações fora do JSON.

        Analise se a seguinte mensagem contém uma resposta para "Qual a descrição da necessidade da contratação?":

        Mensagem: "{user_msg}"

        Retorne APENAS um JSON válido com:
        - "contains_need": true/false
        - "need_description": texto extraído se contains_need for true
        """

        response = openai_client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": need_analysis_prompt}],
            max_tokens=200,
            temperature=0.1
        )

        raw_content = response.choices[0].message.content.strip()
        logger.info(f"analyze_need_safely: Raw OpenAI response: {raw_content}")
        
        # PASSO 5: Use robust parser
        parsed_obj = parse_json_relaxed(raw_content)
        
        if parsed_obj and parsed_obj.get("contains_need") is True:
            need_description = parsed_obj.get("need_description") or user_msg.strip()
            logger.info(f"analyze_need_safely: Need identified - {need_description}")
            return True, need_description
        
        # PASSO 5: contains_need False OR parse failed → DO NOT promote user_msg to necessity
        logger.info("analyze_need_safely: contains_need=False or parse failed → maintaining current necessity")
        return False, None
        
    except Exception as e:
        logger.error(f"analyze_need_safely: Error calling OpenAI - {e}")
        # PASSO 5: On error, DO NOT promote user_msg to necessity
        return False, None


def parse_requirements_response_safely(raw_response):
    """
    Safely parse requirements generation response from LLM
    
    Args:
        raw_response: Can be string (JSON), dict, or list
    
    Returns:
        Dict with parsed requirements or safe fallback
    """
    # Handle different input types
    if raw_response is None:
        logger.warning("parse_requirements_response_safely: None response")
        return {
            'suggested_requirements': [],
            'consultative_message': 'Resposta vazia do sistema'
        }
    
    # If it's already a dict, use it directly
    if isinstance(raw_response, dict):
        logger.info("parse_requirements_response_safely: Response is already a dict")
        parsed = raw_response
    
    # If it's a string, try to parse as JSON
    elif isinstance(raw_response, str):
        if not raw_response.strip():
            logger.warning("parse_requirements_response_safely: Empty string response")
            return {
                'suggested_requirements': [],
                'consultative_message': 'Resposta vazia do sistema'
            }
        
        try:
            parsed = parse_json_relaxed(raw_response)
            if parsed is None:
                logger.warning("parse_requirements_response_safely: Failed to parse JSON string")
                return {
                    'suggested_requirements': [],
                    'consultative_message': 'Não foi possível processar a resposta do sistema. Tente novamente.'
                }
        except Exception as e:
            logger.error(f"parse_requirements_response_safely: Error parsing JSON string - {e}")
            return {
                'suggested_requirements': [],
                'consultative_message': 'Erro ao processar resposta do sistema'
            }
    
    # If it's a list, assume it's a list of requirements
    elif isinstance(raw_response, list):
        logger.info("parse_requirements_response_safely: Response is a list, converting to standard format")
        legacy_requirements = []
        for i, req in enumerate(raw_response):
            if isinstance(req, str):
                legacy_requirements.append({
                    "id": f"R{i+1}",
                    "text": req,
                    "description": req
                })
            elif isinstance(req, dict):
                # Ensure required fields exist
                req_dict = {
                    "id": req.get("id", f"R{i+1}"),
                    "text": req.get("text", req.get("description", "")),
                    "description": req.get("description", req.get("text", ""))
                }
                legacy_requirements.append(req_dict)
            else:
                logger.warning(f"parse_requirements_response_safely: Skipping invalid requirement item: {type(req)}")
        
        return {
            'suggested_requirements': legacy_requirements,
            'consultative_message': 'Requisitos processados com sucesso'
        }
    
    else:
        logger.error(f"parse_requirements_response_safely: Unsupported response type: {type(raw_response)}")
        return {
            'suggested_requirements': [],
            'consultative_message': 'Tipo de resposta não suportado'
        }
    
    # Now we have a parsed dict, process it
    try:
        if parsed and isinstance(parsed, dict):
            # Check if we have the new expected structure
            if 'suggested_requirements' in parsed and 'consultative_message' in parsed:
                requirements = parsed.get('suggested_requirements', [])
                message = parsed.get('consultative_message', '')
                
                if isinstance(requirements, list) and isinstance(message, str):
                    logger.info(f"parse_requirements_response_safely: Successfully parsed {len(requirements)} requirements")
                    return parsed
            
            # Handle legacy format with "requirements" field
            elif 'requirements' in parsed:
                raw_reqs = parsed.get('requirements', [])
                if isinstance(raw_reqs, list):
                    logger.info(f"parse_requirements_response_safely: Converting legacy format with {len(raw_reqs)} requirements")
                    
                    # Converting legacy format - handle both strings and dicts
                    legacy_requirements = []
                    for i, req in enumerate(raw_reqs):
                        if isinstance(req, str):
                            legacy_requirements.append({
                                "id": f"R{i+1}",
                                "text": req,
                                "description": req
                            })
                        elif isinstance(req, dict):
                            # Ensure required fields exist
                            req_dict = {
                                "id": req.get("id", f"R{i+1}"),
                                "text": req.get("text", req.get("description", "")),
                                "description": req.get("description", req.get("text", ""))
                            }
                            legacy_requirements.append(req_dict)
                        else:
                            # Skip invalid items but log the issue
                            logger.warning(f"parse_requirements_response_safely: Skipping invalid requirement item: {type(req)}")
                    
                    return {
                        'suggested_requirements': legacy_requirements,
                        'consultative_message': 'Requisitos convertidos do formato legado'
                    }
            
            # Handle case where parsed dict has other structure
            else:
                logger.warning(f"parse_requirements_response_safely: Unexpected dict structure: {list(parsed.keys())}")
                return {
                    'suggested_requirements': [],
                    'consultative_message': 'Estrutura de resposta não reconhecida'
                }
        
        # Fallback for malformed response
        logger.warning("parse_requirements_response_safely: Malformed response, using fallback")
        return {
            'suggested_requirements': [],
            'consultative_message': 'Não foi possível processar a resposta do sistema. Tente novamente.'
        }
        
    except Exception as e:
        logger.error(f"parse_requirements_response_safely: Error processing parsed response - {e}")
        return {
            'suggested_requirements': [],
            'consultative_message': 'Erro ao processar resposta do sistema'
        }


def parse_classification_response_safely(raw_response: str):
    """
    Safely parse contract type classification response
    
    Returns:
        Dict with classification or safe fallback
    """
    if not raw_response or not isinstance(raw_response, str):
        logger.warning("parse_classification_response_safely: Empty or invalid response")
        return {'type': 'produto', 'reasoning': 'Classificação automática por fallback'}
    
    try:
        parsed = parse_json_relaxed(raw_response)
        
        if parsed and isinstance(parsed, dict):
            contract_type = parsed.get('type', 'produto')
            reasoning = parsed.get('reasoning', 'Classificação automática')
            
            # Validate type is one of expected values
            if contract_type in ['produto', 'serviço', 'servico']:
                logger.info(f"parse_classification_response_safely: Classified as {contract_type}")
                return {'type': contract_type, 'reasoning': reasoning}
        
        # Fallback for malformed response
        logger.warning("parse_classification_response_safely: Malformed response, using fallback")
        return {'type': 'produto', 'reasoning': 'Classificação automática por fallback'}
        
    except Exception as e:
        logger.error(f"parse_classification_response_safely: Error parsing response - {e}")
        return {'type': 'produto', 'reasoning': 'Classificação automática por fallback'}
