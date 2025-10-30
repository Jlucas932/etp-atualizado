"""

import re
from typing import Iterable, List, Sequence

from domain.services.etp_dynamic import regenerate_one
Métodos auxiliares para manipulação de requisitos na sessão
Renumeração estável R1..Rn e preservação de justificativas
"""

def renumber_requirements(requirements_list):
    """
    Renumera requisitos como R1, R2, R3... em ordem
    """
    for i, req in enumerate(requirements_list, 1):
        req['id'] = f'R{i}'
    return requirements_list


def generate_justification(requirement_text, necessity):
    """
    Gera justificativa coerente quando não fornecida
    """
    if not requirement_text or not necessity:
        return "Justificativa necessária para atender à demanda"
    
    # Justificativas padrão baseadas em palavras-chave
    text_lower = requirement_text.lower()
    necessity_lower = necessity.lower()
    
    if any(word in text_lower for word in ['material', 'equipamento', 'ferramenta']):
        return f"Material necessário para execução adequada de {necessity_lower}"
    elif any(word in text_lower for word in ['mão de obra', 'pessoal', 'profissional']):
        return f"Recursos humanos qualificados para {necessity_lower}"
    elif any(word in text_lower for word in ['prazo', 'cronograma', 'tempo']):
        return f"Cronograma adequado para atender {necessity_lower}"
    elif any(word in text_lower for word in ['qualidade', 'padrão', 'especificação']):
        return f"Garantia de qualidade para {necessity_lower}"
    else:
        return f"Requisito essencial para atendimento de {necessity_lower}"


def _parse_indices(items: Sequence[str]) -> List[int]:
    parsed: List[int] = []
    for raw in items or []:
        if isinstance(raw, str):
            match = re.search(r'(\d+)', raw)
            if match:
                idx = int(match.group(1))
                if idx not in parsed:
                    parsed.append(idx)
        elif isinstance(raw, int) and raw not in parsed:
            parsed.append(raw)
    parsed.sort()
    return parsed


def _regenerate_indices(session, indices: Iterable[int], necessity: str) -> None:
    current = session.get_requirements()
    if not current:
        return

    index_list = sorted({i for i in indices if isinstance(i, int) and i >= 1})
    if not index_list:
        return

    previous_by_pos = {i: req for i, req in enumerate(current, start=1)}
    updated = current
    for idx in index_list:
        updated = regenerate_one(necessity or "", updated, idx)

    target_set = set(index_list)
    for position, req in enumerate(updated, start=1):
        if position not in target_set:
            old = previous_by_pos.get(position)
            if old and old.get('justification') and 'justification' not in req:
                req['justification'] = old['justification']

    session.set_requirements(updated)


def apply_command_to_session(session, command_result, necessity):
    """
    Aplica comando parseado à sessão com renumeração estável
    """
    current_requirements = session.get_requirements()
    intent = command_result['intent']
    items = command_result.get('items', [])
    
    if intent == 'remove':
        # Remover requisitos especificados
        updated_requirements = []
        for req in current_requirements:
            if req['id'] not in items:
                updated_requirements.append(req)
        
        # Renumerar
        updated_requirements = renumber_requirements(updated_requirements)
        session.set_requirements(updated_requirements)
        
    elif intent == 'keep_only':
        # Manter apenas os especificados
        updated_requirements = []
        for req in current_requirements:
            if req['id'] in items:
                updated_requirements.append(req)
        
        # Renumerar
        updated_requirements = renumber_requirements(updated_requirements)
        session.set_requirements(updated_requirements)
        
    elif intent == 'edit':
        # Editar requisitos específicos
        new_text = command_result.get('new_text', '')
        should_regenerate = command_result.get('regenerate') or not new_text

        if should_regenerate:
            numeric_indices = _parse_indices(items)
            _regenerate_indices(session, numeric_indices, necessity)
        else:
            updated_requirements = []
            for req in current_requirements:
                if req['id'] in items and new_text:
                    req['text'] = new_text
                    if not req.get('justification'):
                        req['justification'] = generate_justification(new_text, necessity)
                updated_requirements.append(req)

            session.set_requirements(updated_requirements)
        
    elif intent == 'add':
        # Adicionar novos requisitos
        updated_requirements = current_requirements.copy()
        
        for content in items:
            new_req = {
                'id': f'R{len(updated_requirements) + 1}',
                'text': content,
                'justification': generate_justification(content, necessity)
            }
            updated_requirements.append(new_req)
        
        # Renumerar todos
        updated_requirements = renumber_requirements(updated_requirements)
        session.set_requirements(updated_requirements)
    
    elif intent == 'reorder':
        # Reordenar requisitos de acordo com nova ordem
        # items contém a nova ordem como lista de índices [2, 1, 3, ...]
        if not items or not isinstance(items, list):
            return  # Ordem inválida, não fazer nada
        
        # Criar mapa de índice atual para requisito
        req_by_index = {}
        for i, req in enumerate(current_requirements, 1):
            req_by_index[i] = req
        
        # Reordenar baseado na nova ordem
        updated_requirements = []
        for new_pos_idx in items:
            if new_pos_idx in req_by_index:
                updated_requirements.append(req_by_index[new_pos_idx])
        
        # Adicionar requisitos que não foram mencionados na nova ordem (manter no final)
        mentioned_indices = set(items)
        for i in range(1, len(current_requirements) + 1):
            if i not in mentioned_indices and i in req_by_index:
                updated_requirements.append(req_by_index[i])
        
        # Renumerar todos
        updated_requirements = renumber_requirements(updated_requirements)
        session.set_requirements(updated_requirements)


def escape_html(text):
    """
    Sanitização básica para prevenir XSS
    """
    if not isinstance(text, str):
        return str(text)
    
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&#x27;",
        ">": "&gt;",
        "<": "&lt;",
    }
    
    return "".join(html_escape_table.get(c, c) for c in text)
