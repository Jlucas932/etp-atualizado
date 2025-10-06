"""
Interpretador conversacional melhorado para comandos em linguagem natural
Substitui o requirements_interpreter.py com foco em fluidez conversacional
"""

import re
from typing import Dict, List, Any, Tuple


def parse_conversational_command(user_message: str, current_requirement: Dict = None, context: Dict = None) -> Dict[str, Any]:
    """
    Parse user commands in natural conversational language
    
    Args:
        user_message: User's message in natural language
        current_requirement: Current requirement being discussed
        context: Additional context (session info, etc.)
    
    Returns:
        Dict with parsed intent and actions
    """
    if not user_message or not isinstance(user_message, str):
        return {'intent': 'unclear', 'action': 'ask_clarification', 'message': 'Não entendi. Pode repetir?'}
    
    message_lower = user_message.lower().strip()
    
    # 1. REJEIÇÃO/NÃO GOSTOU - Mais comum em conversas naturais
    reject_patterns = [
        r'não\s+gost(ei|o)', r'não\s+curto', r'não\s+quero', r'não\s+serve',
        r'ruim', r'não\s+está\s+bom', r'inadequado', r'inapropriado',
        r'pode\s+sugerir\s+outro', r'sugere\s+outro', r'outro\s+requisito',
        r'diferente', r'não\s+funciona', r'não\s+combina'
    ]
    
    if any(re.search(pattern, message_lower) for pattern in reject_patterns):
        return {
            'intent': 'reject_current',
            'action': 'suggest_alternative',
            'message': 'Entendi que você não gostou deste requisito. Vou sugerir uma alternativa.',
            'current_requirement_id': current_requirement.get('id') if current_requirement else None
        }
    
    # 2. APROVAÇÃO/CONFIRMAÇÃO
    approve_patterns = [
        r'\b(ok|okay)\b', r'\bsim\b', r'está\s+bom', r'perfeito', r'ótimo',
        r'excelente', r'ideal', r'adequado', r'apropriado', r'funciona',
        r'pode\s+ser', r'concordo', r'aceito', r'aprovado', r'beleza',
        r'correto', r'certo', r'pode\s+manter', r'assim\s+está\s+bom'
    ]
    
    if any(re.search(pattern, message_lower) for pattern in approve_patterns):
        return {
            'intent': 'approve_current',
            'action': 'move_to_next',
            'message': 'Ótimo! Requisito aprovado. Vamos para o próximo?',
            'current_requirement_id': current_requirement.get('id') if current_requirement else None
        }
    
    # 3. PEDIDO DE CONTINUAÇÃO
    continue_patterns = [
        r'próximo', r'continuar', r'seguir', r'avançar', r'próximo\s+requisito',
        r'vamos\s+em\s+frente', r'pode\s+continuar', r'siga', r'prosseguir',
        r'e\s+agora', r'qual\s+o\s+próximo'
    ]
    
    if any(re.search(pattern, message_lower) for pattern in continue_patterns):
        return {
            'intent': 'continue',
            'action': 'move_to_next',
            'message': 'Vamos para o próximo requisito.',
            'current_requirement_id': current_requirement.get('id') if current_requirement else None
        }
    
    # 4. PEDIDO DE MODIFICAÇÃO ESPECÍFICA
    modify_patterns = [
        r'alterar', r'modificar', r'trocar', r'mudar', r'editar', r'ajustar',
        r'melhorar', r'aprimorar', r'refinar', r'corrigir', r'adaptar',
        r'personalizar', r'customizar'
    ]
    
    if any(re.search(pattern, message_lower) for pattern in modify_patterns):
        # Tentar extrair o que o usuário quer modificar
        modification_request = extract_modification_request(user_message)
        return {
            'intent': 'modify_current',
            'action': 'apply_modification',
            'message': f'Vou ajustar o requisito conforme solicitado.',
            'modification_request': modification_request,
            'current_requirement_id': current_requirement.get('id') if current_requirement else None
        }
    
    # 5. PEDIDO PARA VER TODOS OS REQUISITOS
    show_all_patterns = [
        r'mostrar?\s+todos', r'ver\s+todos', r'listar\s+todos', r'todos\s+os\s+requisitos',
        r'resumo', r'lista\s+completa', r'o\s+que\s+temos\s+até\s+agora'
    ]
    
    if any(re.search(pattern, message_lower) for pattern in show_all_patterns):
        return {
            'intent': 'show_all',
            'action': 'display_summary',
            'message': 'Aqui está o resumo dos requisitos até agora:'
        }
    
    # 6. PEDIDO PARA ADICIONAR NOVO REQUISITO
    add_patterns = [
        r'adicionar', r'incluir', r'acrescentar', r'novo\s+requisito',
        r'mais\s+um', r'também\s+precisa', r'faltou', r'esqueceu'
    ]
    
    if any(re.search(pattern, message_lower) for pattern in add_patterns):
        new_requirement = extract_new_requirement(user_message)
        return {
            'intent': 'add_new',
            'action': 'create_new_requirement',
            'message': 'Vou adicionar esse novo requisito.',
            'new_requirement': new_requirement
        }
    
    # 7. FINALIZAÇÃO
    finish_patterns = [
        r'finalizar', r'terminar', r'acabar', r'pronto', r'é\s+isso',
        r'só\s+isso', r'suficiente', r'pode\s+gerar', r'vamos\s+gerar'
    ]
    
    if any(re.search(pattern, message_lower) for pattern in finish_patterns):
        return {
            'intent': 'finish',
            'action': 'finalize_requirements',
            'message': 'Perfeito! Vou finalizar os requisitos e gerar o documento.'
        }
    
    # 8. CASO NÃO IDENTIFICADO - Resposta mais amigável
    return {
        'intent': 'unclear',
        'action': 'ask_clarification',
        'message': 'Não entendi bem. Você pode me dizer se gostou do requisito, se quer modificar algo ou se prefere continuar para o próximo?',
        'suggestions': [
            'Dizer "ok" ou "está bom" para aprovar',
            'Dizer "não gostei" para sugerir outro',
            'Dizer "próximo" para continuar'
        ]
    }


def extract_modification_request(user_message: str) -> str:
    """Extract what the user wants to modify"""
    # Procurar por padrões como "trocar X por Y", "mudar para X", etc.
    
    # Padrão: "trocar X por Y"
    replace_match = re.search(r'trocar\s+(.+?)\s+por\s+(.+)', user_message, re.IGNORECASE)
    if replace_match:
        return f"Substituir '{replace_match.group(1)}' por '{replace_match.group(2)}'"
    
    # Padrão: "mudar para X"
    change_match = re.search(r'mudar\s+para\s+(.+)', user_message, re.IGNORECASE)
    if change_match:
        return f"Alterar para: {change_match.group(1)}"
    
    # Padrão: "ajustar X"
    adjust_match = re.search(r'ajustar\s+(.+)', user_message, re.IGNORECASE)
    if adjust_match:
        return f"Ajustar: {adjust_match.group(1)}"
    
    # Caso geral - retornar a mensagem completa
    return user_message


def extract_new_requirement(user_message: str) -> str:
    """Extract new requirement from user message"""
    # Procurar por padrões como "adicionar X", "incluir Y", etc.
    
    add_patterns = [
        r'adicionar\s+(.+)',
        r'incluir\s+(.+)',
        r'acrescentar\s+(.+)',
        r'novo\s+requisito:?\s*(.+)',
        r'também\s+precisa\s+(.+)',
        r'faltou\s+(.+)'
    ]
    
    for pattern in add_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Se não encontrou padrão específico, retornar a mensagem completa
    return user_message


def generate_conversational_response(intent_result: Dict[str, Any], context: Dict = None) -> str:
    """Generate a natural conversational response based on intent"""
    
    action = intent_result.get('action', 'ask_clarification')
    
    if action == 'suggest_alternative':
        return "Entendi que você não gostou deste requisito. Deixe-me sugerir uma alternativa..."
    
    elif action == 'move_to_next':
        return "Perfeito! Vamos para o próximo requisito então."
    
    elif action == 'apply_modification':
        return f"Vou ajustar o requisito. {intent_result.get('modification_request', '')}"
    
    elif action == 'display_summary':
        return "Aqui está o que temos até agora:"
    
    elif action == 'create_new_requirement':
        return f"Ótima sugestão! Vou adicionar: {intent_result.get('new_requirement', '')}"
    
    elif action == 'finalize_requirements':
        return "Excelente! Vou finalizar os requisitos e preparar o documento."
    
    else:
        return intent_result.get('message', 'Como posso ajudar?')
