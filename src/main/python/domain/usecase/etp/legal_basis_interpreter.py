from typing import Dict, Any

def parse_legal_basis(user_message: str, answers: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Intents:
      - legal_basis_set: usuário informa a base legal (texto livre)
      - legal_basis_notes: observações adicionais
      - finalize: encerrar fase
      - unclear
    """
    msg = (user_message or "").strip()
    low = msg.lower()
    if any(t in low for t in ["lei", "art.", "artigo", "inciso", "decreto", "portaria", "estatuto"]):
        return {'intent': 'legal_basis_set', 'message': 'Base legal registrada.', 'payload': {'text': msg}}
    if any(t in low for t in ["observação", "observacao", "nota", "comentário", "comentario"]):
        return {'intent': 'legal_basis_notes', 'message': 'Observação registrada.', 'payload': {'text': msg}}
    if any(t in low for t in ["finalizar", "encerrar", "concluído", "concluido", "seguir"]):
        return {'intent': 'finalize', 'message': 'Fase de base legal concluída.', 'payload': None}
    return {'intent': 'unclear', 'message': 'Não entendi sua informação sobre base legal.', 'payload': None}
