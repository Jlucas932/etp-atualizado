"""
PASSO 3 - Interpretador de comandos para revisão de requisitos
Suporte robusto para variações em português brasileiro
Agora com interpretação via OpenAI para entender linguagem natural
"""

import re
import json
import os
from typing import Dict, List, Any, Tuple, Optional


def parse_intent_with_openai(user_message: str, current_requirements: List[Dict], openai_client=None) -> Optional[Dict[str, Any]]:
    """
    Usa OpenAI para interpretar a mensagem do usuário e extrair a intenção estruturada.
    
    Converte linguagem natural em uma das INTENÇÕES:
    - accept_all (aceitar como está)
    - replace_item(index, new_text)
    - remove_items([indexes])
    - add_item(new_text)
    - reorder([new_order])
    - ask_clarification(question) (quando falta dado objetivo)
    - reject_and_restart(reason)
    
    Returns:
        Dict com intent e slots extraídos, ou None se falhar
    """
    if not openai_client:
        # Tentar obter cliente OpenAI do ambiente
        try:
            import openai
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key or api_key == 'test_api_key_for_testing':
                return None
            openai_client = openai.OpenAI(api_key=api_key)
        except:
            return None
    
    # Construir contexto dos requisitos atuais
    requirements_context = ""
    if current_requirements:
        requirements_context = "Requisitos atuais:\n"
        for i, req in enumerate(current_requirements, 1):
            req_text = req.get('description') or req.get('text') or req.get('id', '')
            requirements_context += f"{i}. {req_text}\n"
    
    # Prompt template conforme especificação do issue
    prompt = f"""Você é um assistente que converte mensagens de usuários em português em operações estruturadas sobre requisitos.

Converta a mensagem do usuário em uma das INTENÇÕES:

1. **accept_all** - aceitar como está (usuário confirma tudo)
2. **replace_item** - substituir um requisito específico
   - Slots: index (número do requisito), new_text (novo texto)
3. **remove_items** - remover um ou mais requisitos
   - Slots: indexes (lista de números)
4. **add_item** - adicionar novo requisito
   - Slots: new_text (texto do novo requisito)
5. **reorder** - reordenar requisitos
   - Slots: new_order (lista com nova ordem dos índices)
6. **ask_clarification** - pedir esclarecimento (quando falta informação)
   - Slots: question (texto da pergunta ou dúvida)
7. **reject_and_restart** - recomeçar do início (necessidade mudou)
   - Slots: reason (motivo do reinício)

REGRAS DE EXTRAÇÃO:
- Extraia índices por números em português: "um" = 1, "dois" = 2, "três" = 3, "quatro" = 4, "cinco" = 5, etc.
- Aceite posições: "o primeiro" = 1, "o segundo" = 2, "o terceiro" = 3, "o último" = {len(current_requirements)}
- Aceite variações: "tira manutenção", "troca o 3 por X", "inclui treinamento de 4h"
- Variações de confirmação: "mantém todos", "está bom, segue", "pode seguir", "ok", "confirmo"

{requirements_context}

EXEMPLOS DE ENTRADA → SAÍDA:

"Mantém como está, pode seguir." → {{"intent":"accept_all"}}

"Troca o 3 por 'Compatível com ANAC RBAC 145'." → {{"intent":"replace_item","index":3,"new_text":"Compatível com ANAC RBAC 145"}}

"Remove 2 e 4 e adiciona 'treinamento dos operadores'." → {{"intent":"remove_items","indexes":[2,4],"extra_add":[{{"text":"treinamento dos operadores"}}]}}

"Não entendi esse requisito 5, explica." → {{"intent":"ask_clarification","question":"Explicar requisito 5"}}

"Volta pro começo, necessidade mudou para manutenção predial." → {{"intent":"reject_and_restart","reason":"nova necessidade: manutenção predial"}}

"Tira manutenção" → {{"intent":"remove_items","indexes":[índice do requisito que contém 'manutenção']}}

"Inclui treinamento de 4h" → {{"intent":"add_item","new_text":"treinamento de 4h"}}

Saída sempre em JSON compacto com intent + slots. Se não houver confiança suficiente, retorne ask_clarification com a melhor hipótese.

MENSAGEM DO USUÁRIO:
"{user_message}"

Responda APENAS com o JSON, sem explicações adicionais:"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em interpretar comandos em português para manipulação de requisitos. Sempre responda apenas com JSON válido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        raw_content = response.choices[0].message.content.strip()
        
        # Tentar extrair JSON da resposta (pode vir com markdown)
        if "```json" in raw_content:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
            if json_match:
                raw_content = json_match.group(1)
        elif "```" in raw_content:
            json_match = re.search(r'```\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
            if json_match:
                raw_content = json_match.group(1)
        
        # Parse JSON
        intent_data = json.loads(raw_content)
        return intent_data
        
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao parsear JSON da resposta OpenAI: {e}")
        print(f"Resposta recebida: {raw_content}")
        return None
    except Exception as e:
        print(f"❌ Erro ao chamar OpenAI para interpretar intenção: {e}")
        return None


def convert_openai_intent_to_controller_format(openai_intent: Dict[str, Any], current_requirements: List[Dict]) -> Dict[str, Any]:
    """
    Converte o formato de intent do OpenAI para o formato esperado pelo controller.
    
    OpenAI intents:
    - accept_all -> confirm
    - replace_item -> edit
    - remove_items -> remove
    - add_item -> add
    - reorder -> edit (with special handling)
    - ask_clarification -> ask
    - reject_and_restart -> restart_necessity
    """
    intent = openai_intent.get('intent')
    
    if intent == 'accept_all':
        return {
            'intent': 'confirm',
            'items': [],
            'message': 'Requisitos confirmados pelo usuário.'
        }
    
    elif intent == 'replace_item':
        index = openai_intent.get('index')
        new_text = openai_intent.get('new_text', '')
        req_id = f"R{index}"
        return {
            'intent': 'edit',
            'items': [req_id],
            'new_text': new_text,
            'message': f'Requisito {req_id} será substituído por: {new_text}'
        }
    
    elif intent == 'remove_items':
        indexes = openai_intent.get('indexes', [])
        req_ids = [f"R{idx}" for idx in indexes]
        
        # Check if there's also an add operation (combo command)
        extra_add = openai_intent.get('extra_add', [])
        if extra_add:
            # Return multiple operations - controller needs to handle this
            return {
                'intent': 'remove',
                'items': req_ids,
                'extra_add': extra_add,
                'message': f'Removidos requisitos: {", ".join(req_ids)}'
            }
        
        return {
            'intent': 'remove',
            'items': req_ids,
            'message': f'Removidos requisitos: {", ".join(req_ids)}'
        }
    
    elif intent == 'add_item':
        new_text = openai_intent.get('new_text', '')
        return {
            'intent': 'add',
            'items': [new_text],
            'message': f'Novo requisito adicionado: {new_text}'
        }
    
    elif intent == 'reorder':
        new_order = openai_intent.get('new_order', [])
        return {
            'intent': 'reorder',
            'items': new_order,
            'message': f'Requisitos reordenados: {new_order}'
        }
    
    elif intent == 'ask_clarification':
        question = openai_intent.get('question', '')
        return {
            'intent': 'ask',
            'items': [],
            'message': f'Usuário pediu esclarecimento: {question}'
        }
    
    elif intent == 'reject_and_restart':
        reason = openai_intent.get('reason', '')
        return {
            'intent': 'restart_necessity',
            'items': [],
            'message': f'Usuário pediu para reiniciar: {reason}'
        }
    
    # Fallback para intent desconhecido
    return {
        'intent': 'other',
        'items': [],
        'message': 'Intenção não reconhecida claramente.'
    }


def parse_update_command(user_message: str, current_requirements: List[Dict], openai_client=None) -> Dict[str, Any]:
    """
    Parse user commands for requirement updates usando OpenAI para interpretar linguagem natural.
    
    Primeiro tenta usar OpenAI para interpretar a mensagem em linguagem natural.
    Se OpenAI não estiver disponível ou falhar, usa o parser baseado em regex (fallback).
    
    Returns dict with:
    - intent: 'accept', 'edit', 'ask', 'repeat_need', 'other' (as per issue spec)
      or legacy: 'remove', 'keep_only', 'add', 'confirm', 'restart_necessity', 'unclear'
    - items: list of requirement IDs or content
    - message: explanation of what was done
    """
    # PRIORIDADE 1: Tentar usar OpenAI para interpretar linguagem natural
    openai_intent = parse_intent_with_openai(user_message, current_requirements, openai_client)
    
    if openai_intent:
        print(f"✅ Intent parseado via OpenAI: {openai_intent}")
        controller_format = convert_openai_intent_to_controller_format(openai_intent, current_requirements)
        
        # Handle combo commands (remove + add)
        if controller_format.get('extra_add'):
            controller_format['_combo_add'] = controller_format.pop('extra_add')
        
        return controller_format
    
    # FALLBACK: Usar parser baseado em regex (sistema legado)
    print(f"⚠️  OpenAI não disponível, usando parser regex (fallback)")
    return parse_update_command_regex(user_message, current_requirements)


def parse_update_command_regex(user_message: str, current_requirements: List[Dict]) -> Dict[str, Any]:
    """
    Parser legado baseado em regex - mantido como fallback.
    
    Returns dict with:
    - intent: 'accept', 'edit', 'ask', 'repeat_need', 'other' (as per issue spec)
      or legacy: 'remove', 'keep_only', 'add', 'confirm', 'restart_necessity', 'unclear'
    - items: list of requirement IDs or content
    - message: explanation of what was done
    """
    if not user_message or not isinstance(user_message, str):
        return {'intent': 'unclear', 'items': [], 'message': 'Mensagem vazia ou inválida'}
    
    msg = (user_message or "").strip().lower()
    # Normalização simples
    msg = msg.replace("  ", " ")

    message_lower = user_message.lower().strip()

    # PRIORITY 0: Check for question/ask patterns FIRST
    # Questions should be detected before any edit or confirmation
    question_patterns = [
        '?', 'como', 'por que', 'porque', 'qual', 'quais', 'quando', 'onde',
        'quem', 'o que', 'pode explicar', 'não entendi', 'dúvida', 'duvida',
        'me explica', 'explique', 'o que significa', 'que significa'
    ]
    if any(pattern in msg for pattern in question_patterns):
        return {
            'intent': 'ask',
            'items': [],
            'message': 'Usuário fez uma pergunta ou pediu esclarecimento.'
        }

    # PRIORITY 1: Check for edit/change keywords FIRST
    # These override confirmation tokens (e.g., "ok, mas troque..." is edit, not confirm)
    edit_keywords = [
        "trocar", "troque", "trocar", "mudar", "mude", "alterar", "altere",
        "modificar", "modifique", "ajustar", "ajuste", "corrigir", "corrija",
        "atualizar", "atualize", "editar", "edite", "mas ", "porém", "porem",
        "entretanto", "contudo", "todavia"
    ]
    has_edit_intent = any(keyword in msg for keyword in edit_keywords)

    # PRIORITY 2: Check for "manter apenas" BEFORE checking general confirm tokens
    # This is a keep_only command, not a confirmation
    has_keep_only_intent = ("manter apenas" in msg or "manter só" in msg or "manter somente" in msg)

    # PRIORITY 3: Only check confirm/accept if no edit or keep_only intent
    if not has_edit_intent and not has_keep_only_intent:
        # Confirmações abrangentes (mapped to both 'confirm' and 'accept' for compatibility)
        confirm_tokens = [
            "aceito", "aprovado", "aprovada", "aprove", "confirmo", "confirmada",
            "pode seguir", "pode prosseguir", "pode continuar", "segue", "prosseguir",
            "sem alterações", "sem alteracoes", "sem ajustes", "manter assim",
            "está bom", "esta bom", "ok", "ok.", "ok!", "fechou", "tá bom", "ta bom",
            "pode manter", "manter", "concordo"
        ]
        for token in confirm_tokens:
            if token in msg:
                return {
                    'intent': 'confirm',  # Keep 'confirm' for backward compatibility
                    'items': [],
                    'message': 'Requisitos confirmados pelo usuário.'
                }
    
    # Reinício explícito
    restart_tokens = [
        "reiniciar", "recomeçar", "recomecar",
        "nova necessidade", "novo objeto", "redefinir necessidade"
    ]
    for token in restart_tokens:
        if token in msg:
            return {
                'intent': 'restart_necessity',
                'items': [],
                'message': 'Usuario pediu para reiniciar a coleta da necessidade.'
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
    
    # If nothing clear was detected, classify as 'other'
    # Note: 'repeat_need' is detected at controller level when user re-describes necessity
    # As per issue spec: never return "comando não reconhecido", just classify as 'other'
    return {
        'intent': 'other',
        'items': [],
        'message': ''  # Empty message - will be handled by state machine with ask_clarification
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
    
    # Negation patterns (these are confirmations, not edits)
    # Check FIRST before edit patterns that might contain these words
    negation_confirm_patterns = [
        'sem alterações', 'sem alteracoes', 'sem ajustes', 'sem mudanças', 'sem mudancas',
        'sem modificações', 'sem modificacoes', 'nenhuma alteração', 'nenhuma alteracao',
        'nenhum ajuste', 'nenhuma mudança', 'nenhuma mudanca'
    ]
    if any(pattern in message_lower for pattern in negation_confirm_patterns):
        return 'confirm'
    
    # Remove patterns
    remove_patterns = ['remover', 'tirar', 'excluir', 'deletar', 'retirar', 'apagar']
    if any(word in message_lower for word in remove_patterns):
        return 'remove'
    
    # Keep only patterns
    keep_only_patterns = ['manter apenas', 'só manter', 'manter só', 'manter somente', 'apenas']
    if any(pattern in message_lower for pattern in keep_only_patterns):
        return 'keep_only'
    
    # Edit patterns - include verb conjugations
    edit_patterns = [
        'alterar', 'altere', 'modificar', 'modifique', 'modifico',
        'trocar', 'troque', 'troco', 'mudar', 'mude', 'mudo',
        'editar', 'edite', 'edito', 'ajustar', 'ajuste', 'ajusto',
        'corrigir', 'corrija', 'corrijo', 'atualizar', 'atualize', 'atualizo'
    ]
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
