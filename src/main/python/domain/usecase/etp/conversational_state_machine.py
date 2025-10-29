"""
Conversational State Machine for ETP Generation (Buttonless Flow)
Complete implementation of the 13-state conversation flow as per issue specification.
"""

import re
import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime


# ============================================================================
# STATE DEFINITIONS
# ============================================================================

VALID_STATES = [
    'collect_need',
    'suggest_requirements',
    'solution_strategies',
    'pca',
    'legal_norms',
    'qty_value',
    'installment',
    'summary',
    'preview'
]

VALID_TRANSITIONS = {
    'collect_need': ['suggest_requirements'],
    'suggest_requirements': ['solution_strategies'],
    'solution_strategies': ['pca'],
    'pca': ['legal_norms'],
    'legal_norms': ['qty_value'],
    'qty_value': ['installment'],
    'installment': ['summary'],
    'summary': ['preview'],
    'preview': []
}


# ============================================================================
# INTENT RECOGNITION
# ============================================================================

def parse_user_intent(user_message: str, current_state: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse user message into intent and slots.
    
    Returns:
        {
            'intent': str,  # Type of intent
            'slots': dict,  # Extracted data
            'confidence': float  # 0.0 to 1.0
        }
    """
    msg_lower = user_message.lower().strip()
    
    # Check for generic confirmation first (works across all states)
    if is_generic_confirmation(user_message):
        return {
            'intent': 'confirm',
            'slots': {},
            'confidence': 1.0
        }
    
    # Check for generate confirmation (only in confirm_summary state)
    if current_state == 'confirm_summary' and is_generate_confirmation(user_message):
        return {
            'intent': 'confirm_generate',
            'slots': {},
            'confidence': 1.0
        }
    
    # Check for "não sei" / "pular" patterns
    if is_skip_response(user_message):
        return {
            'intent': 'skip',
            'slots': {'value': 'não informado'},
            'confidence': 1.0
        }
    
    # State-specific parsing
    if current_state == 'refine_requirements':
        return parse_requirements_edit(user_message, session_data)
    
    elif current_state == 'recommend_solution_path':
        return parse_solution_path(user_message)
    
    elif current_state == 'ask_pca':
        return parse_pca_answer(user_message)
    
    elif current_state == 'ask_legal_norms':
        return parse_legal_norms(user_message)
    
    elif current_state == 'ask_quant_value':
        return parse_quant_value(user_message)
    
    elif current_state == 'ask_parcelamento':
        return parse_parcelamento(user_message)
    
    elif current_state == 'confirm_summary':
        return parse_summary_adjustment(user_message)
    
    # Default: treat as text answer for current state
    return {
        'intent': 'answer',
        'slots': {'text': user_message},
        'confidence': 0.5
    }


def is_generic_confirmation(user_message: str) -> bool:
    """Check for generic confirmation patterns."""
    msg_lower = user_message.lower().strip()
    
    patterns = [
        r'\bok\b',
        r'\bpode seguir\b',
        r'\bseguir\b',
        r'\bsegue\b',
        r'\bprosseguir\b',
        r'\bmanter\b',
        r'\baceito\b',
        r'\bacordo\b',
        r'\bconcordo\b',
        r'\bfechou\b',
        r'\bconfirmo\b',
        r'\bconfirmado\b',
        r'\bperfeito\b',
        r'\bestá bom\b',
        r'\btá bom\b',
        r'\bpode manter\b',
        r'\bsim\b',
        r'\bcorreto\b'
    ]
    
    for pattern in patterns:
        if re.search(pattern, msg_lower):
            return True
    
    return False


def is_generate_confirmation(user_message: str) -> bool:
    """Check for ETP generation confirmation patterns."""
    msg_lower = user_message.lower().strip()
    
    patterns = [
        r'\bpode gerar\b',
        r'\bgerar etp\b',
        r'\bgera etp\b',
        r'\bfechou gerar\b',
        r'\bok gerar\b',
        r'\bgerar\b'
    ]
    
    for pattern in patterns:
        if re.search(pattern, msg_lower):
            return True
    
    return False


def is_skip_response(user_message: str) -> bool:
    """Check if user wants to skip/doesn't know."""
    msg_lower = user_message.lower().strip()
    
    patterns = [
        r'\bnão sei\b',
        r'\bnao sei\b',
        r'\bpular\b',
        r'\bdepois\b',
        r'\bsem informação\b',
        r'\bnão tenho\b',
        r'\bnao tenho\b',
        r'\bnão informado\b',
        r'\bnao informado\b'
    ]
    
    for pattern in patterns:
        if re.search(pattern, msg_lower):
            return True
    
    return False


# ============================================================================
# STATE-SPECIFIC PARSERS
# ============================================================================

def parse_requirements_edit(user_message: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse requirements editing commands."""
    msg_lower = user_message.lower()
    current_requirements = session_data.get('requirements', [])
    
    # Check for adjustment commands
    # Pattern: "ajustar 3: texto" or "ajustar R3: texto"
    adjust_match = re.search(r'ajustar\s+[rR]?(\d+)[:\s]+(.+)', user_message, re.IGNORECASE)
    if adjust_match:
        index = int(adjust_match.group(1))
        text = adjust_match.group(2).strip()
        return {
            'intent': 'requirements_edit',
            'slots': {
                'actions': [{'type': 'ajustar', 'index': index, 'text': text}]
            },
            'confidence': 0.9
        }
    
    # Pattern: "remover 2" or "remover R2"
    remove_match = re.search(r'remover\s+[rR]?(\d+)', user_message, re.IGNORECASE)
    if remove_match:
        index = int(remove_match.group(1))
        return {
            'intent': 'requirements_edit',
            'slots': {
                'actions': [{'type': 'remover', 'index': index}]
            },
            'confidence': 0.9
        }
    
    # Pattern: "incluir: texto"
    include_match = re.search(r'incluir[:\s]+(.+)', user_message, re.IGNORECASE)
    if include_match:
        text = include_match.group(1).strip()
        return {
            'intent': 'requirements_edit',
            'slots': {
                'actions': [{'type': 'incluir', 'text': text}]
            },
            'confidence': 0.9
        }
    
    # Generic remove/include keywords
    if any(word in msg_lower for word in ['remover', 'tirar', 'excluir', 'deletar']):
        return {
            'intent': 'ask_clarification',
            'slots': {'question': 'Qual requisito você gostaria de remover? Pode indicar o número.'},
            'confidence': 0.6
        }
    
    if any(word in msg_lower for word in ['adicionar', 'incluir', 'acrescentar']):
        # Try to extract text after the command
        for word in ['adicionar', 'incluir', 'acrescentar']:
            if word in msg_lower:
                parts = user_message.split(word, 1)
                if len(parts) > 1 and parts[1].strip():
                    return {
                        'intent': 'requirements_edit',
                        'slots': {
                            'actions': [{'type': 'incluir', 'text': parts[1].strip()}]
                        },
                        'confidence': 0.8
                    }
        
        return {
            'intent': 'ask_clarification',
            'slots': {'question': 'O que você gostaria de incluir?'},
            'confidence': 0.6
        }
    
    # If no edit command detected, check for confirmation
    if is_generic_confirmation(user_message):
        return {
            'intent': 'confirm',
            'slots': {},
            'confidence': 1.0
        }
    
    # Default: treat as unclear
    return {
        'intent': 'ask_clarification',
        'slots': {'question': 'Você quer ajustar, remover ou incluir algum requisito? Ou está tudo certo para seguir?'},
        'confidence': 0.4
    }


def parse_solution_path(user_message: str) -> Dict[str, Any]:
    """Parse solution path choice (compra/locacao/servico)."""
    msg_lower = user_message.lower()
    
    # Map variations to standard values
    if any(word in msg_lower for word in ['compra', 'comprar', 'aquisição', 'aquisicao']):
        return {
            'intent': 'choose_path',
            'slots': {'path': 'compra'},
            'confidence': 0.9
        }
    
    if any(word in msg_lower for word in ['locação', 'locacao', 'aluguel', 'alugar', 'locar']):
        return {
            'intent': 'choose_path',
            'slots': {'path': 'locacao'},
            'confidence': 0.9
        }
    
    if any(word in msg_lower for word in ['serviço', 'servico', 'terceirizar', 'terceirizado', 'gestão', 'gestao']):
        return {
            'intent': 'choose_path',
            'slots': {'path': 'servico'},
            'confidence': 0.9
        }
    
    if any(word in msg_lower for word in ['comparar', 'comparação', 'comparacao', 'compare']):
        return {
            'intent': 'choose_path',
            'slots': {'path': 'comparar'},
            'confidence': 0.9
        }
    
    if any(word in msg_lower for word in ['recomende', 'recomenda', 'sugira', 'sugestão', 'sugestao']):
        return {
            'intent': 'choose_path',
            'slots': {'path': 'recomendacao'},
            'confidence': 0.9
        }
    
    # Check for confirmation (user agreeing with suggested path)
    if is_generic_confirmation(user_message):
        return {
            'intent': 'confirm',
            'slots': {},
            'confidence': 1.0
        }
    
    return {
        'intent': 'answer',
        'slots': {'text': user_message},
        'confidence': 0.5
    }


def parse_pca_answer(user_message: str) -> Dict[str, Any]:
    """Parse PCA (Plano de Contratações Anual) answer."""
    msg_lower = user_message.lower()
    
    # Positive responses
    if any(word in msg_lower for word in ['sim', 'tenho', 'possuo', 'previsto', 'consta', 'há previsão', 'tem']):
        return {
            'intent': 'answer_pca',
            'slots': {'value': 'sim'},
            'confidence': 0.9
        }
    
    # Negative responses
    if any(word in msg_lower for word in ['não', 'nao', 'sem pca', 'não tenho', 'nao tenho', 'não consta', 'nao consta']):
        return {
            'intent': 'answer_pca',
            'slots': {'value': 'nao'},
            'confidence': 0.9
        }
    
    # Skip/don't know
    if is_skip_response(user_message):
        return {
            'intent': 'answer_pca',
            'slots': {'value': 'nao_informado'},
            'confidence': 1.0
        }
    
    # If answer is longer, treat as descriptive answer
    if len(user_message) > 20:
        return {
            'intent': 'answer_pca',
            'slots': {'value': 'sim', 'description': user_message},
            'confidence': 0.7
        }
    
    return {
        'intent': 'answer_pca',
        'slots': {'value': 'nao_informado', 'description': user_message},
        'confidence': 0.6
    }


def parse_legal_norms(user_message: str) -> Dict[str, Any]:
    """Parse legal norms answer."""
    msg_lower = user_message.lower()
    
    # Skip/don't know
    if is_skip_response(user_message):
        return {
            'intent': 'answer_legal_norms',
            'slots': {'text': 'não informado'},
            'confidence': 1.0
        }
    
    # If message contains lei/decreto/instrução normativa, treat as legal norm
    if any(word in msg_lower for word in ['lei', 'decreto', 'instrução', 'instrucao', 'normativa', 'portaria', 'resolução', 'resolucao']):
        return {
            'intent': 'answer_legal_norms',
            'slots': {'text': user_message},
            'confidence': 0.9
        }
    
    # Any text is acceptable as legal norms
    return {
        'intent': 'answer_legal_norms',
        'slots': {'text': user_message},
        'confidence': 0.7
    }


def parse_quant_value(user_message: str) -> Dict[str, Any]:
    """Parse quantitative and value information."""
    msg_lower = user_message.lower()
    
    # Skip/don't know
    if is_skip_response(user_message):
        return {
            'intent': 'answer_quant_value',
            'slots': {'quantitativo': 'não informado', 'valor': 'não informado'},
            'confidence': 1.0
        }
    
    # Try to extract numbers and currency
    slots = {}
    
    # Extract quantity (numbers followed by unidades/itens/etc)
    quant_match = re.search(r'(\d+)\s*(unidade|unidades|item|itens|aeronave|aeronaves|servidor|servidores|equipamento|equipamentos)?', msg_lower)
    if quant_match:
        slots['quantitativo'] = int(quant_match.group(1))
        if quant_match.group(2):
            slots['unidade'] = quant_match.group(2)
    
    # Extract currency values
    # Patterns: R$ 1.200.000, 1,2 mi, 1.2 milhões, etc.
    valor_match = re.search(r'R?\$?\s*(\d+[.,]?\d*)\s*(mil|milhão|milhões|mi|k)?', user_message, re.IGNORECASE)
    if valor_match:
        valor_str = valor_match.group(1).replace('.', '').replace(',', '.')
        valor = float(valor_str)
        
        # Multiply by scale
        multiplier = valor_match.group(2)
        if multiplier:
            multiplier_lower = multiplier.lower()
            if multiplier_lower in ['mil', 'k']:
                valor *= 1000
            elif multiplier_lower in ['milhão', 'milhões', 'mi']:
                valor *= 1000000
        
        slots['valor'] = valor
    
    # Extract period
    if any(word in msg_lower for word in ['ano', '/ano', 'anual']):
        slots['periodo'] = 'ano'
    elif any(word in msg_lower for word in ['mês', 'mes', '/mês', 'mensal']):
        slots['periodo'] = 'mes'
    
    # If we extracted something, return it
    if slots:
        return {
            'intent': 'answer_quant_value',
            'slots': slots,
            'confidence': 0.8
        }
    
    # Otherwise, treat as text description
    return {
        'intent': 'answer_quant_value',
        'slots': {'text': user_message},
        'confidence': 0.6
    }


def parse_parcelamento(user_message: str) -> Dict[str, Any]:
    """Parse parcelamento (installment) information."""
    msg_lower = user_message.lower()
    
    # Skip/don't know
    if is_skip_response(user_message):
        return {
            'intent': 'answer_parcelamento',
            'slots': {'value': 'nao_informado'},
            'confidence': 1.0
        }
    
    # Yes/No responses
    if any(word in msg_lower for word in ['sim', 'haverá', 'havera', 'terá', 'tera', 'será', 'sera']):
        return {
            'intent': 'answer_parcelamento',
            'slots': {'value': 'sim', 'text': user_message},
            'confidence': 0.9
        }
    
    if any(word in msg_lower for word in ['não', 'nao', 'sem parcelamento', 'não haverá', 'nao havera']):
        return {
            'intent': 'answer_parcelamento',
            'slots': {'value': 'nao'},
            'confidence': 0.9
        }
    
    # If mentions lotes/fases/regiões, it's likely yes with description
    if any(word in msg_lower for word in ['lote', 'lotes', 'fase', 'fases', 'região', 'regiao', 'regiões', 'regioes', 'etapa', 'etapas']):
        return {
            'intent': 'answer_parcelamento',
            'slots': {'value': 'sim', 'text': user_message},
            'confidence': 0.9
        }
    
    # Otherwise, treat as text description
    return {
        'intent': 'answer_parcelamento',
        'slots': {'text': user_message},
        'confidence': 0.6
    }


def parse_summary_adjustment(user_message: str) -> Dict[str, Any]:
    """Parse summary adjustment requests."""
    msg_lower = user_message.lower()
    
    # Check for generate confirmation first
    if is_generate_confirmation(user_message):
        return {
            'intent': 'confirm_generate',
            'slots': {},
            'confidence': 1.0
        }
    
    # Check for adjustment requests
    if any(word in msg_lower for word in ['mudar', 'alterar', 'trocar', 'ajustar', 'corrigir']):
        return {
            'intent': 'request_adjustment',
            'slots': {'text': user_message},
            'confidence': 0.8
        }
    
    return {
        'intent': 'answer',
        'slots': {'text': user_message},
        'confidence': 0.5
    }


# ============================================================================
# STATE MACHINE LOGIC
# ============================================================================

def validate_state_transition(current_state: str, next_state: str, user_confirmed: bool) -> Tuple[bool, Optional[str]]:
    """Validate if state transition is allowed."""
    if current_state not in VALID_STATES:
        return False, f"Estado inválido: {current_state}"
    
    if next_state not in VALID_STATES:
        return False, f"Estado de destino inválido: {next_state}"
    
    allowed_next = VALID_TRANSITIONS.get(current_state, [])
    if next_state not in allowed_next:
        return False, f"Transição não permitida de {current_state} para {next_state}"
    
    # refine_requirements can loop to itself without confirmation
    if current_state == 'refine_requirements' and next_state == 'refine_requirements':
        return True, None
    
    # generate_etp can retry itself on error
    if current_state == 'generate_etp' and next_state == 'generate_etp':
        return True, None
    
    # All other transitions require confirmation
    if current_state != next_state and not user_confirmed:
        return False, "Transição requer confirmação explícita do usuário"
    
    return True, None


def get_next_state(current_state: str, intent: Dict[str, Any], session_data: Dict[str, Any]) -> str:
    """Determine next state based on current state and intent."""
    intent_type = intent.get('intent')
    
    # Handle confirmation intent
    if intent_type == 'confirm':
        allowed_next = VALID_TRANSITIONS.get(current_state, [])
        if allowed_next:
            # Move to first allowed next state
            return allowed_next[0] if allowed_next[0] != current_state else current_state
        return current_state
    
    # Handle confirm_generate intent
    if intent_type == 'confirm_generate' and current_state == 'confirm_summary':
        return 'generate_etp'
    
    # Handle skip intent - move to next state
    if intent_type == 'skip':
        allowed_next = VALID_TRANSITIONS.get(current_state, [])
        if allowed_next:
            return allowed_next[0] if allowed_next[0] != current_state else current_state
        return current_state
    
    # State-specific transitions
    if current_state == 'collect_need' and intent_type == 'answer':
        return 'suggest_requirements'
    
    if current_state == 'suggest_requirements':
        return 'refine_requirements'
    
    if current_state == 'refine_requirements':
        if intent_type == 'requirements_edit':
            return 'refine_requirements'  # Stay in refine mode
        elif intent_type == 'confirm':
            return 'confirm_requirements'
    
    if current_state == 'confirm_requirements' and intent_type == 'confirm':
        return 'recommend_solution_path'
    
    if current_state == 'recommend_solution_path':
        if intent_type == 'choose_path':
            # Stay in same state to confirm choice
            return 'recommend_solution_path'
        elif intent_type == 'confirm' and session_data.get('solution_path'):
            return 'ask_pca'
    
    if current_state == 'ask_pca' and intent_type == 'answer_pca':
        return 'ask_legal_norms'
    
    if current_state == 'ask_legal_norms' and intent_type == 'answer_legal_norms':
        return 'ask_quant_value'
    
    if current_state == 'ask_quant_value' and intent_type == 'answer_quant_value':
        return 'ask_parcelamento'
    
    if current_state == 'ask_parcelamento' and intent_type == 'answer_parcelamento':
        return 'confirm_summary'
    
    if current_state == 'confirm_summary':
        if intent_type == 'confirm_generate':
            return 'generate_etp'
        elif intent_type == 'request_adjustment':
            return 'confirm_summary'  # Stay for adjustment
    
    if current_state == 'generate_etp':
        # On success, move to preview
        # On error, stay in generate_etp
        return current_state  # Let handler decide based on result
    
    if current_state == 'preview' and intent_type in ['confirm', 'answer']:
        return 'finalize'
    
    # Default: stay in current state
    return current_state


# ============================================================================
# STATE RESPONSE GENERATORS
# ============================================================================

def generate_state_response(state: str, session_data: Dict[str, Any], intent: Dict[str, Any] = None) -> str:
    """Generate natural language response for each state without command templates."""
    
    if state == 'collect_need':
        return "Olá! Para começar, me descreva qual a necessidade desta contratação."
    
    elif state == 'suggest_requirements':
        reqs = session_data.get('requirements', [])
        if reqs:
            req_text = "\n".join([f"{req.get('id', '')} — {req.get('text', '')}" for req in reqs])
            return f"""Baseado na sua necessidade, sugiro estes requisitos:

{req_text}

Eles cobrem os aspectos principais de conformidade, operação e suporte. Se quiser que eu ajuste algo, me diga naturalmente o que mudar. Caso contrário, posso seguir para as estratégias de contratação."""
        return "Vou preparar os requisitos para você. Um momento..."
    
    elif state == 'solution_strategies':
        need = session_data.get('necessity', 'sua necessidade')
        return f"""Agora vamos definir a melhor estratégia de contratação para "{need}". Posso sugerir algumas opções:

1. **Compra Direta**: Aquisição patrimonial, controle total, ideal quando há verba CAPEX e vida útil longa.
2. **Leasing Operacional**: Aluguel com manutenção incluída, menor investimento inicial, ideal para ativos com obsolescência rápida.
3. **Serviço por Desempenho**: Contratado assume operação e entrega resultado (ex.: disponibilidade 98%), transfere riscos operacionais.
4. **Comodato**: Equipamento cedido gratuitamente vinculado a contrato de consumíveis/serviço.
5. **ARP (Acordo de Reconhecimento de Preços)**: Registro de preços com múltiplas contratações futuras.

Qual dessas faz mais sentido para o seu caso? Ou quer que eu recomende com base no contexto?"""
    
    elif state == 'pca':
        # Check if user said "não sei" via intent
        if intent and intent.get('intent') not in ['answer', 'skip', 'confirm']:
            return """Entendo. O PCA (Plano de Contratações Anual) é o cronograma de contratações da organização. Vou sugerir três situações comuns:

1. **Não previsto no PCA atual** — Precisará incluir via atualização do plano
2. **Previsto para o segundo semestre** — Aguardando aprovação e liberação de verba
3. **Previsto e aprovado** — Pode seguir com o processo imediatamente

Qual delas se aproxima mais da sua situação? Ou me diga como está o PCA para essa contratação."""
        return "Sobre o PCA (Plano de Contratações Anual): essa demanda já aparece no seu planejamento deste ano? Se não tiver certeza, eu explico rapidamente e te proponho dois caminhos simples."
    
    elif state == 'legal_norms':
        # Check if user said "não sei"
        if intent and intent.get('intent') not in ['answer', 'skip', 'confirm']:
            obj = session_data.get('necessity', 'esse objeto')
            return f"""Sem problema. Para {obj}, as normas mais comuns são:

1. **Lei 14.133/2021** (Nova Lei de Licitações) — Base geral para contratações públicas
2. **Decreto 11.462/2023** — Regulamenta pregão eletrônico e contratação direta
3. **IN SEGES 65/2021** — Gestão de contratos administrativos federais
4. **Normas técnicas ABNT** — Específicas do objeto (ex.: ABNT NBR para equipamentos)

Quais dessas fazem sentido incluir? Ou tem alguma norma específica do seu órgão?"""
        return "Normas e base legal: posso te sugerir um pacote inicial típico do setor (Lei 14.133/2021 + regulatórias aplicáveis) e você me diz se mantemos, ajustamos ou deixamos como rascunho?"
    
    elif state == 'qty_value':
        # Check if user said "não sei"
        if intent and intent.get('intent') not in ['answer', 'skip', 'confirm']:
            return """Entendo que ainda não tem o valor definido. Vou propor três abordagens de estimativa:

1. **Estimativa conservadora** — Usar média de mercado acrescida de 20-30% de margem de segurança
2. **Estimativa equilibrada** — Pesquisa de preço em 3 fornecedores + média ajustada
3. **Estimativa agressiva** — Menor preço de mercado com negociação forte

Qual abordagem prefere que eu registre? Ou pode me passar uma faixa aproximada (ex.: 'entre R$ 500k e R$ 800k')."""
        return "Sobre quantitativo e valor: dá para chutar uma ordem de grandeza? Se estiver nebuloso, eu te mostro duas formas rápidas de chegar a um número defensável e já deixo uma faixa inicial para você aprovar."
    
    elif state == 'installment':
        # Check if user said "não sei"
        if intent and intent.get('intent') not in ['answer', 'skip', 'confirm']:
            return """Vou explicar as opções de parcelamento:

**Prós do parcelamento (por lotes/fases):**
- Reduz risco de fornecedor único
- Permite ajustes entre fases
- Facilita planejamento orçamentário

**Contras:**
- Maior complexidade de gestão
- Possível variação de preços entre lotes
- Necessita múltiplos processos

Para o seu caso, recomendo **não parcelar** se o valor total for comportável no orçamento e a entrega for rápida (< 6 meses). **Parcelar** faz sentido se houver restrição orçamentária ou implantação gradual por região/unidade.

O que acha? Parcelar ou contratação única?"""
        return "Sobre parcelamento: você acha que faz sentido dividir em lotes ou fases? Se não tiver certeza, eu explico os prós e contras rapidamente e te ajudo a escolher o melhor para o seu caso."
    
    elif state == 'summary':
        # Build summary from session data
        answers = session_data.get('answers', {})
        reqs = session_data.get('requirements', [])
        need = session_data.get('necessity', 'não informado')
        strategy = answers.get('solution_strategy', 'não informado')
        pca = answers.get('pca', 'não informado')
        legal_norms = answers.get('legal_norms', 'não informado')
        quant_value = answers.get('quant_value', 'não informado')
        installment = answers.get('installment', 'não informado')
        
        req_count = len(reqs)
        req_summary = f"{req_count} requisitos definidos" if req_count > 0 else "requisitos pendentes"
        
        return f"""Pronto! Aqui está o resumo do ETP:

**Necessidade:** {need}
**Requisitos:** {req_summary}
**Estratégia de contratação:** {strategy}
**PCA:** {pca}
**Normas legais:** {legal_norms}
**Quantitativo/Valor:** {quant_value}
**Parcelamento:** {installment}

Tudo certo? Se sim, posso gerar a prévia do documento."""
    
    elif state == 'preview':
        return "Aqui está a prévia do ETP gerado com todas as informações que coletamos. Você pode baixar o documento ou solicitar ajustes."
    
    return "Como posso ajudar?"


# ============================================================================
# ERROR HANDLING
# ============================================================================

def handle_service_error(current_state: str, error_message: str) -> Dict[str, Any]:
    """
    Handle service errors without advancing state.
    
    Returns response dict with error message and unchanged state.
    """
    return {
        'success': False,
        'error': error_message,
        'ai_response': f"Ocorreu um erro técnico: {error_message}. Vou permanecer nesta etapa. Quando quiser tentar novamente, me avise.",
        'conversation_stage': current_state,
        'state_changed': False
    }


def handle_unclear_intent(current_state: str, question: str) -> Dict[str, Any]:
    """Handle unclear user intent by asking for clarification."""
    return {
        'success': True,
        'ai_response': question,
        'conversation_stage': current_state,
        'state_changed': False,
        'requires_clarification': True
    }
