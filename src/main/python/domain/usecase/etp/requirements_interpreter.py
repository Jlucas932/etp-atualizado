"""
PASSO 3 - Interpretador de comandos para revisão de requisitos
Suporte robusto para variações em português brasileiro
"""

import re
from typing import Dict, List, Any, Tuple


def parse_update_command(user_message: str, current_requirements: List[Dict]) -> Dict[str, Any]:
    """
    Parse user commands for requirement updates
    Returns dict with:
    - intent: 'remove', 'edit', 'keep_only', 'add', 'confirm', 'restart_necessity', 'unclear'
    - items: list of requirement IDs or content
    - message: explanation of what was done
    """
    if not user_message or not isinstance(user_message, str):
        return {'intent': 'unclear', 'items': [], 'message': 'Mensagem vazia ou inválida'}
    
    message_lower = user_message.lower().strip()
    
    # PASSO 4: Check for explicit necessity restart keywords
    restart_keywords = [
        r'nova\s*necessidade',
        r'trocar\s*a\s*necessidade', 
        r'na\s*verdade\s*a\s*necessidade\s*é',
        r'mudou\s*a\s*necessidade',
        r'preciso\s*trocar\s*a\s*necessidade'
    ]
    
    for keyword in restart_keywords:
        if re.search(keyword, message_lower):
            return {
                'intent': 'restart_necessity',
                'items': [],
                'message': 'Detectada solicitação para reiniciar necessidade'
            }
    
    # Extract requirement numbers/indices
    req_indices = extract_requirement_indices(user_message, current_requirements)
    
    # Determine action type based on verbs and patterns
    intent = determine_intent(message_lower, req_indices)
    
    if intent == 'remove':
        if req_indices:
            return {
                'intent': 'remove',
                'items': req_indices,
                'message': f'Removidos requisitos: {", ".join(req_indices)}'
            }
        else:
            return {'intent': 'unclear', 'items': [], 'message': 'Não foi possível identificar quais requisitos remover'}
    
    elif intent == 'keep_only':
        if req_indices:
            return {
                'intent': 'keep_only',
                'items': req_indices,
                'message': f'Mantidos apenas requisitos: {", ".join(req_indices)}'
            }
        else:
            return {'intent': 'unclear', 'items': [], 'message': 'Não foi possível identificar quais requisitos manter'}
    
    elif intent == 'edit':
        if req_indices:
            # Check for explicit new text after ":"
            new_text = extract_new_text_after_colon(user_message)
            return {
                'intent': 'edit',
                'items': req_indices,
                'new_text': new_text,
                'message': f'Requisitos para edição: {", ".join(req_indices)}'
            }
        else:
            return {'intent': 'unclear', 'items': [], 'message': 'Não foi possível identificar quais requisitos alterar'}
    
    elif intent == 'add':
        # Extract the content after the add command
        add_content = extract_add_content(user_message, message_lower)
        return {
            'intent': 'add',
            'items': [add_content],
            'message': f'Novo requisito adicionado: {add_content}'
        }
    
    elif intent == 'confirm':
        return {
            'intent': 'confirm',
            'items': [],
            'message': 'Requisitos confirmados'
        }
    
    # If nothing clear was detected
    return {
        'intent': 'unclear',
        'items': [],
        'message': 'Comando não reconhecido. Use: "ajustar 5", "remover 2 e 4", "trocar 3: <novo texto>"'
    }


def extract_requirement_indices(user_message: str, current_requirements: List[Dict]) -> List[str]:
    """Extract requirement indices from user message"""
    req_numbers = []
    message_lower = user_message.lower()
    
    # Look for patterns like "R1", "R2", etc.
    r_patterns = re.findall(r'[rR](\d+)', user_message)
    req_numbers.extend([f"R{n}" for n in r_patterns])
    
    # Look for standalone numbers that might refer to requirements
    number_patterns = re.findall(r'\b(\d+)\b', user_message)
    for n in number_patterns:
        if int(n) <= len(current_requirements):
            req_id = f"R{n}"
            if req_id not in req_numbers:
                req_numbers.append(req_id)
    
    # Handle ranges like "2-4" or "2 a 4"
    range_patterns = re.findall(r'(\d+)\s*[-a]\s*(\d+)', user_message)
    for start, end in range_patterns:
        start_num, end_num = int(start), int(end)
        if start_num <= end_num <= len(current_requirements):
            for i in range(start_num, end_num + 1):
                req_id = f"R{i}"
                if req_id not in req_numbers:
                    req_numbers.append(req_id)
    
    # Handle positional references
    if any(word in message_lower for word in ['último', 'ultima', 'ultimo']):
        if current_requirements:
            last_req = current_requirements[-1]
            req_id = last_req.get('id', f"R{len(current_requirements)}")
            if req_id not in req_numbers:
                req_numbers.append(req_id)
    
    if any(word in message_lower for word in ['primeiro', 'primeira']):
        if current_requirements:
            first_req = current_requirements[0]
            req_id = first_req.get('id', 'R1')
            if req_id not in req_numbers:
                req_numbers.append(req_id)
    
    if any(word in message_lower for word in ['penúltimo', 'penultima', 'penultimo']):
        if len(current_requirements) > 1:
            penult_req = current_requirements[-2]
            req_id = penult_req.get('id', f"R{len(current_requirements)-1}")
            if req_id not in req_numbers:
                req_numbers.append(req_id)
    
    return req_numbers


def determine_intent(message_lower: str, req_indices: List[str]) -> str:
    """Determine the user's intent based on the message"""
    
    # Remove patterns
    remove_patterns = ['remover', 'tirar', 'excluir', 'deletar', 'retirar', 'apagar']
    if any(word in message_lower for word in remove_patterns):
        return 'remove'
    
    # Keep only patterns
    keep_only_patterns = ['manter apenas', 'só manter', 'manter só', 'manter somente', 'apenas']
    if any(pattern in message_lower for pattern in keep_only_patterns):
        return 'keep_only'
    
    # Edit patterns
    edit_patterns = ['alterar', 'modificar', 'trocar', 'mudar', 'editar', 'ajustar', 'ajuste']
    if any(word in message_lower for word in edit_patterns):
        return 'edit'
    
    # Add patterns
    add_patterns = ['adicionar', 'incluir', 'acrescentar', 'novo requisito', 'mais um']
    if any(pattern in message_lower for pattern in add_patterns):
        return 'add'
    
    # Confirmation patterns
    confirm_patterns = [
        'confirmar', 'confirmo', 'manter', 'ok', 'está bom', 'perfeito',
        'concordo', 'aceito', 'pode ser', 'sim', 'correto', 'certo',
        'pode manter', 'mantenha', 'assim está bom'
    ]
    if any(pattern in message_lower for pattern in confirm_patterns):
        return 'confirm'
    
    return 'unclear'


def extract_new_text_after_colon(user_message: str) -> str:
    """Extract new text after colon for edit commands"""
    colon_match = re.search(r':\s*(.+)$', user_message)
    if colon_match:
        return colon_match.group(1).strip()
    return ""


def extract_add_content(user_message: str, message_lower: str) -> str:
    """Extract content to add for add commands"""
    add_patterns = ['adicionar', 'incluir', 'acrescentar', 'novo requisito']
    
    for pattern in add_patterns:
        if pattern in message_lower:
            parts = user_message.lower().split(pattern, 1)
            if len(parts) > 1:
                return parts[1].strip()
    
    return user_message.strip()


def aplicar_comando(cmd: Dict[str, Any], session, necessity: str = None) -> None:
    """
    Apply the parsed command to the session requirements with stable renumbering
    """
    from .session_methods import apply_command_to_session
    apply_command_to_session(session, cmd, necessity)
