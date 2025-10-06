"""
Interpretador de comandos de revisão de requisitos em português.
Implementa a lógica determinística para interpretar comandos do usuário sobre requisitos.
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class Requirement:
    """Estrutura para representar um requisito"""
    id: str
    text: str
    justification: str


def parse_update_command(user_text: str, requirements: List[Dict]) -> Dict[str, Any]:
    """
    Interpreta comandos de atualização de requisitos em português.
    
    Args:
        user_text: Texto do usuário em português
        requirements: Lista atual de requisitos
        
    Returns:
        Dict com intent e parâmetros da ação a executar
    """
    text = user_text.strip().lower()
    total_reqs = len(requirements)
    
    # 1) Detecta troca de necessidade (gatilhos explícitos)
    if re.search(r"nova\s*necessidade|trocar\s*a\s*necessidade|na\s*verdade\s*a\s*necessidade\s*é", text):
        return {"intent": "change_need"}
    
    # 2) Identificar índices mencionados
    targets = []
    
    # Verificar se menciona "último"
    if re.search(r"últim[oa]", text):
        if total_reqs > 0:
            targets.append(total_reqs)  # 1-based indexing
    
    # Extrair números mencionados
    number_matches = re.findall(r"\b(\d+)\b", text)
    for match in number_matches:
        idx = int(match)
        if 1 <= idx <= total_reqs:
            targets.append(idx)
    
    # Remover duplicatas e ordenar
    targets = sorted(set(targets))
    
    # 3) Determinar ação baseada em palavras-chave
    
    # Comando de remoção
    if re.search(r"remov|apag|exclu", text) and targets:
        return {"intent": "remove", "indices": targets}
    
    # Comando de manter apenas alguns
    if re.search(r"manter\s*(só|somente)", text) and targets:
        return {"intent": "keep_only", "indices": targets}
    
    # Comando de ajuste/edição
    if re.search(r"ajust|troc|substitu", text) and targets:
        # Tentar extrair novo texto após ':'
        parts = re.split(r":", user_text, maxsplit=1)
        new_text = parts[1].strip() if len(parts) == 2 and len(parts[1].strip()) > 0 else None
        return {
            "intent": "edit", 
            "indices": targets, 
            "new_text": new_text
        }
    
    # Comando de adição (identificar palavras-chave de adição)
    if re.search(r"adicion|inclui|acrescent|mais\s*um", text):
        # Tentar extrair novo texto após ':'
        parts = re.split(r":", user_text, maxsplit=1)
        new_text = parts[1].strip() if len(parts) == 2 and len(parts[1].strip()) > 0 else None
        return {
            "intent": "add",
            "new_text": new_text or user_text  # Usar texto completo se não houver ':'
        }
    
    # Comando de confirmação/aprovação
    if re.search(r"confirmo|aprovo|perfeito|está\s*bom|ok|concordo|mantenha|assim\s*mesmo", text):
        return {"intent": "confirm"}
    
    # Se tem targets mas não identificou ação específica, assumir edição
    if targets:
        parts = re.split(r":", user_text, maxsplit=1)
        new_text = parts[1].strip() if len(parts) == 2 and len(parts[1].strip()) > 0 else None
        return {
            "intent": "edit", 
            "indices": targets, 
            "new_text": new_text
        }
    
    # Nenhuma ação clara identificada
    return {"intent": "unclear", "original_text": user_text}


def apply_update_command(command: Dict[str, Any], requirements: List[Dict], necessity: str = "") -> tuple[List[Dict], str]:
    """
    Aplica o comando de atualização à lista de requisitos.
    
    Args:
        command: Comando interpretado pelo parse_update_command
        requirements: Lista atual de requisitos
        necessity: Necessidade da contratação para contexto
        
    Returns:
        Tuple com (nova_lista_requisitos, mensagem_explicativa)
    """
    intent = command.get("intent")
    
    if intent == "change_need":
        return requirements, "Para alterar a necessidade, é necessário reiniciar o processo. Deseja continuar com os requisitos atuais?"
    
    if intent == "confirm":
        return requirements, f"Perfeito! Lista de {len(requirements)} requisitos confirmada. Vamos para a próxima etapa."
    
    if intent == "remove":
        indices = command.get("indices", [])
        # Converter para IDs baseados na posição atual
        ids_to_remove = [f"R{i}" for i in indices]
        # Filtrar requisitos
        new_reqs = [req for req in requirements if req["id"] not in ids_to_remove]
        # Renumerar IDs
        for i, req in enumerate(new_reqs, 1):
            req["id"] = f"R{i}"
        
        removed_count = len(requirements) - len(new_reqs)
        message = f"Removidos {removed_count} requisito(s). Lista atualizada com {len(new_reqs)} requisitos."
        return new_reqs, message
    
    if intent == "keep_only":
        indices = command.get("indices", [])
        # Manter apenas os requisitos especificados
        kept_reqs = []
        for i in indices:
            if i <= len(requirements):
                req = requirements[i-1].copy()  # 0-based para acesso
                kept_reqs.append(req)
        
        # Renumerar IDs
        for i, req in enumerate(kept_reqs, 1):
            req["id"] = f"R{i}"
            
        message = f"Mantidos apenas {len(kept_reqs)} requisito(s) conforme solicitado."
        return kept_reqs, message
    
    if intent == "edit":
        indices = command.get("indices", [])
        new_text = command.get("new_text")
        updated_reqs = requirements.copy()
        
        for idx in indices:
            if idx <= len(updated_reqs):
                req = updated_reqs[idx-1]  # 0-based para acesso
                if new_text:
                    req["text"] = new_text
                    req["justification"] = f"Requisito ajustado conforme solicitação do usuário."
                else:
                    # Se não tem texto novo, marcar para regeneração via LLM
                    req["_needs_regeneration"] = True
        
        if new_text:
            message = f"Requisito(s) {', '.join(map(str, indices))} atualizado(s) conforme solicitado."
        else:
            message = f"Requisito(s) {', '.join(map(str, indices))} será(ão) regenerado(s). Um momento..."
            
        return updated_reqs, message
    
    if intent == "add":
        new_text = command.get("new_text", "")
        if new_text:
            new_req = {
                "id": f"R{len(requirements) + 1}",
                "text": new_text,
                "justification": "Requisito adicionado conforme solicitação do usuário."
            }
            new_reqs = requirements + [new_req]
            message = f"Novo requisito adicionado. Lista atualizada com {len(new_reqs)} requisitos."
            return new_reqs, message
        else:
            return requirements, "Por favor, especifique o requisito que deseja adicionar. Exemplo: 'adicionar: certificação ISO 9001'"
    
    # Intent unclear
    return requirements, "Não compreendi o comando. Você pode ser mais específico? Exemplos: 'remover 3', 'ajustar o último', 'manter só 1 e 2'"


def detect_requirements_discussion(user_text: str) -> bool:
    """
    Detecta se o texto do usuário está discutindo sobre requisitos.
    
    Args:
        user_text: Texto do usuário
        
    Returns:
        True se está falando sobre requisitos
    """
    text = user_text.lower()
    
    # Palavras-chave que indicam discussão sobre requisitos
    requirement_keywords = [
        "requisito", "requisitos", "exigência", "exigências",
        "último", "primeira", "segundo", "terceiro", "quarto", "quinto",
        "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8",
        "remov", "ajust", "troc", "substitu", "mant", "confirm",
        "adicionar", "inclui", "acrescent"
    ]
    
    return any(keyword in text for keyword in requirement_keywords)


def format_requirements_list(requirements: List[Dict]) -> str:
    """
    Formata a lista de requisitos para exibição em Markdown.
    
    Args:
        requirements: Lista de requisitos
        
    Returns:
        String formatada em Markdown
    """
    if not requirements:
        return "Nenhum requisito definido ainda."
    
    markdown = "## Requisitos Atuais\n\n"
    for req in requirements:
        markdown += f"**{req['id']}** – {req['text']}\n"
        if req.get('justification'):
            markdown += f"*Justificativa:* {req['justification']}\n\n"
        else:
            markdown += "\n"
    
    return markdown