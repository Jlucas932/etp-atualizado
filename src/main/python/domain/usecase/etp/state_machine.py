"""
State Machine Guardrails for ETP Generation
Enforces mandatory state transitions with user confirmation
"""

import re
from typing import Tuple, Optional, Dict, Any


# Mandatory state flow
VALID_STATES = [
    'collect_need',
    'suggest_requirements',
    'refine_requirements',
    'confirm_requirements',
    'generate_etp',
    'preview',
    'finalize'
]

# Valid transitions (from_state -> [allowed_next_states])
VALID_TRANSITIONS = {
    'collect_need': ['suggest_requirements'],
    'suggest_requirements': ['refine_requirements'],
    'refine_requirements': ['refine_requirements', 'confirm_requirements'],
    'confirm_requirements': ['generate_etp'],
    'generate_etp': ['preview'],
    'preview': ['finalize'],
    'finalize': []  # Terminal state
}


def is_user_confirmed(user_message: str) -> bool:
    """
    Check if user message contains explicit confirmation.
    Uses regex pattern covering Portuguese confirmation phrases.
    
    Pattern covers: ok|seguir|prosseguir|manter|aceito|concordo|fechou|pode gerar|pode seguir|segue
    """
    if not user_message:
        return False
    
    msg_lower = user_message.lower().strip()
    
    # Confirmation patterns as per issue spec
    confirmation_patterns = [
        r'\bok\b',
        r'\bseguir\b',
        r'\bprosseguir\b',
        r'\bmanter\b',
        r'\baceito\b',
        r'\bacordado\b',
        r'\bconcordo\b',
        r'\bfechou\b',
        r'\bpode gerar\b',
        r'\bpode seguir\b',
        r'\bsegue\b',
        r'\bconfirmo\b',
        r'\bconfirmado\b',
        r'\bconfirmar\b',
        r'\baprovado\b',
        r'\baprovada\b',
        r'\baprove\b',
        r'\bpode prosseguir\b',
        r'\bpode continuar\b',
        r'\bsem alterações\b',
        r'\bsem alteracoes\b',
        r'\bsem ajustes\b',
        r'\bmanter assim\b',
        r'\bestá bom\b',
        r'\besta bom\b',
        r'\btá bom\b',
        r'\bta bom\b',
        r'\bpode manter\b',
        r'\bperfeito\b',
        r'\bcorreto\b',
        r'\bcerto\b'
    ]
    
    for pattern in confirmation_patterns:
        if re.search(pattern, msg_lower):
            return True
    
    return False


def validate_state_transition(
    current_state: str,
    next_state: str,
    user_confirmed: bool
) -> Tuple[bool, Optional[str]]:
    """
    Validate if a state transition is allowed.
    
    Args:
        current_state: Current conversation stage
        next_state: Desired next stage
        user_confirmed: Whether user has explicitly confirmed
    
    Returns:
        (is_valid, error_message)
    """
    # Check if states are valid
    if current_state not in VALID_STATES:
        return False, f"Estado inválido: {current_state}"
    
    if next_state not in VALID_STATES:
        return False, f"Estado de destino inválido: {next_state}"
    
    # Check if transition is allowed
    allowed_next = VALID_TRANSITIONS.get(current_state, [])
    if next_state not in allowed_next:
        return False, f"Transição não permitida de {current_state} para {next_state}"
    
    # CRITICAL: Never transition without user confirmation
    # Exception: refine_requirements can loop to itself without confirmation (for edits)
    if current_state != next_state:  # Only check confirmation when actually changing states
        if not user_confirmed:
            return False, "Transição requer confirmação explícita do usuário"
    
    # Special case: refine_requirements looping to itself is allowed without confirmation
    # This allows users to edit requirements multiple times before confirming
    if current_state == 'refine_requirements' and next_state == 'refine_requirements':
        return True, None
    
    return True, None


def get_next_state_after_suggestion(current_state: str) -> str:
    """
    After suggest_requirements, ALWAYS go to refine_requirements.
    This enforces the mandatory flow as per issue spec.
    """
    if current_state == 'suggest_requirements':
        return 'refine_requirements'
    return current_state


def can_generate_etp(current_state: str, user_confirmed: bool) -> Tuple[bool, Optional[str]]:
    """
    Check if ETP generation is allowed.
    Only allowed when state = confirm_requirements and user_confirmed = true.
    
    Returns:
        (is_allowed, error_message)
    """
    if current_state != 'confirm_requirements':
        return False, f"Geração de ETP só é permitida no estado 'confirm_requirements'. Estado atual: {current_state}"
    
    if not user_confirmed:
        return False, "Geração de ETP requer confirmação explícita do usuário"
    
    return True, None


def handle_other_intent() -> Dict[str, Any]:
    """
    Handle 'other' intent by asking for clarification.
    Never return "comando não reconhecido" - always ask a specific question.
    """
    return {
        'message_type': 'ask_clarification',
        'ai_response': 'Não entendi completamente. Você quer confirmar os requisitos atuais, fazer alguma alteração, ou tem alguma dúvida sobre eles?',
        'message': 'Não entendi completamente. Você quer confirmar os requisitos atuais, fazer alguma alteração, ou tem alguma dúvida sobre eles?',
        'requires_user_action': True
    }


def handle_http_error(error_code: int, error_message: str, current_state: str) -> Dict[str, Any]:
    """
    Handle HTTP errors without changing state.
    Emit controlled error message and keep state unchanged.
    
    Args:
        error_code: HTTP error code (>=400)
        error_message: Error description
        current_state: Current state to maintain
    
    Returns:
        Error response dict with message_type = error and state = unchanged
    """
    return {
        'message_type': 'error',
        'error': error_message,
        'ai_response': f'Ocorreu um erro ao processar sua solicitação: {error_message}. Por favor, tente novamente.',
        'message': f'Ocorreu um erro ao processar sua solicitação: {error_message}. Por favor, tente novamente.',
        'state': current_state,  # State remains unchanged
        'conversation_stage': current_state
    }


def validate_generator_exists(generator) -> Tuple[bool, Optional[str]]:
    """
    Check if the configured generator exists before calling generate_etp.
    If not, emit controlled error message without calling generation endpoints.
    Also checks if generator is FallbackGenerator to avoid calling endpoints that require OpenAI.
    
    Returns:
        (is_valid, error_message)
    """
    if generator is None:
        return False, "Gerador de ETP não está configurado. Verifique a configuração do sistema."
    
    # Check if generator is FallbackGenerator (doesn't have OpenAI client)
    generator_class_name = generator.__class__.__name__
    if generator_class_name == "FallbackGenerator":
        return False, "Não consegui carregar o gerador consultivo. Continuo aqui. Quer que eu tente gerar o ETP diretamente ou ajustamos os requisitos antes?"
    
    return True, None
