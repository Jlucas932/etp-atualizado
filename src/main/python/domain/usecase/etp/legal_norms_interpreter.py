from typing import Dict, Any

def parse_legal_norms(user_message: str, answers: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Interpreta respostas do usuário sobre PCA (Plano de Contratações Anual).
    Intents:
      - pca_yes: usuário afirma que há previsão no PCA
      - pca_no: usuário afirma que não há previsão no PCA
      - pca_unknown: usuário não sabe informar
      - pca_details: usuário traz detalhes (número, ano, item, observações)
      - proceed_next: comando explícito para seguir
      - unclear: não entendi
    Retorna dict com chaves: intent, message, payload
    """
    msg = (user_message or "").strip().lower()
    
    # Check for negative patterns first (unknown and no) to avoid false positives
    has_unknown = any(t in msg for t in ["não sei", "nao sei", "desconheço", "desconheco", "incerto", "não tenho", "nao tenho"])
    has_no = any(t in msg for t in ["não está no pca", "nao esta no pca", "não esta no pca", "nao está no pca", "sem pca"]) or \
             (("não" in msg or "nao" in msg) and ("pca" in msg) and not any(t in msg for t in ["não sei", "nao sei"]))
    
    # Check for positive patterns
    has_yes = any(t in msg for t in ["sim", "está no pca", "esta no pca", "previsto no pca", "conforme pca"])
    proceed = any(t in msg for t in ["seguir", "prosseguir", "pode continuar", "avançar", "avancar"])

    # Heurística simples para detectar detalhes
    has_details_markers = any(t in msg for t in ["nº", "no.", "numero", "número", "ano", "item", "itens", "capítulo", "capitulo", "seção", "secao"])

    # Check in priority order: unknown > no > yes > details > proceed
    if has_unknown:
        return {'intent': 'pca_unknown', 'message': 'PCA não informado pelo usuário.', 'payload': None}
    if has_no:
        return {'intent': 'pca_no', 'message': 'PCA indicado como inexistente.', 'payload': None}
    if has_yes and not has_details_markers:
        return {'intent': 'pca_yes', 'message': 'PCA indicado como existente.', 'payload': None}
    if has_details_markers:
        return {'intent': 'pca_details', 'message': 'Detalhes do PCA fornecidos.', 'payload': {'raw': msg}}
    if proceed:
        return {'intent': 'proceed_next', 'message': 'Solicitação para avançar.', 'payload': None}

    return {'intent': 'unclear', 'message': 'Não entendi a informação sobre o PCA.', 'payload': None}
