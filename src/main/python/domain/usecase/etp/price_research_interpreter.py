from typing import Dict, Any
import re

def parse_price_research(user_message: str, answers: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Intents:
      - method_select: painel de preços, cotações com fornecedores, histórico de contratos, marketplaces etc.
      - supplier_count: número de fornecedores consultados (extrai inteiros)
      - link_evidence: captura URLs enviadas
      - mark_done: usuário sinaliza que concluiu a fase
      - unclear
    """
    msg = (user_message or "").strip().lower()
    urls = re.findall(r'(https?://\S+)', msg)

    # Check supplier_count first (with numbers) to avoid false positives with method keywords
    numbers = re.findall(r'\b(\d{1,3})\b', msg)
    if any(t in msg for t in ['fornecedor', 'fornecedores', 'empresas', 'cotações', 'cotacoes']) and numbers:
        return {'intent': 'supplier_count', 'message': 'Quantidade de fornecedores registrada.', 'payload': {'count': int(numbers[0])}}

    # Check for URLs before method selection (URLs have higher priority)
    if urls:
        return {'intent': 'link_evidence', 'message': 'Link de evidência registrado.', 'payload': {'urls': urls}}

    # Check method selection
    method_map = {
        'painel de preços': 'painel_de_precos',
        'painel': 'painel_de_precos',
        'cotação': 'cotacoes_fornecedores',
        'cotacoes': 'cotacoes_fornecedores',
        'fornecedor': 'cotacoes_fornecedores',
        'histórico': 'historico_contratos',
        'historico': 'historico_contratos',
        'marketplace': 'marketplace',
        'pregão anterior': 'historico_contratos',
        'pregao anterior': 'historico_contratos'
    }
    for k, v in method_map.items():
        if k in msg:
            return {'intent': 'method_select', 'message': f'Método definido: {v}.', 'payload': {'method': v}}

    if any(t in msg for t in ['concluído', 'concluido', 'finalizei', 'pronto', 'seguir', 'prosseguir']):
        return {'intent': 'mark_done', 'message': 'Pesquisa de preços concluída.', 'payload': None}

    return {'intent': 'unclear', 'message': 'Não entendi sua informação sobre pesquisa de preços.', 'payload': None}
