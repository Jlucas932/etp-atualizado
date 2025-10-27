from typing import Dict, Any, List

def compose_etp_document(session) -> Dict[str, Any]:
    """
    Constrói o documento a partir da EtpSession:
      sections: [ {id, title, content, items?}, ... ]
    """
    ans = session.get_answers() or {}
    reqs: List[str] = (ans.get('requirements') or session.get_requirements() or [])
    pca = ans.get('pca') or {}
    pr = ans.get('price_research') or {}
    lb = ans.get('legal_basis') or {}

    doc = {
        'session_id': session.session_id,
        'title': 'Estudo Técnico Preliminar (ETP)',
        'sections': [
            {
                'id': 'intro',
                'title': 'Introdução',
                'content': 'Este ETP foi gerado a partir das informações coletadas na conversa estruturada.'
            },
            {
                'id': 'necessity',
                'title': 'Necessidade/Objeto',
                'content': session.necessity or 'Não informado.'
            },
            {
                'id': 'requirements',
                'title': 'Requisitos',
                'content': 'Lista de requisitos confirmados.',
                'items': reqs
            },
            {
                'id': 'pca',
                'title': 'Plano de Contratações Anual (PCA)',
                'content': (
                    f"Há previsão no PCA: {pca.get('present')}"
                ),
                'details': pca.get('details')
            },
            {
                'id': 'price_research',
                'title': 'Pesquisa de Preços',
                'content': 'Registro de método, quantidade e evidências.',
                'method': pr.get('method'),
                'supplier_count': pr.get('supplier_count'),
                'evidence_links': pr.get('evidence_links') or []
            },
            {
                'id': 'legal_basis',
                'title': 'Base Legal',
                'content': lb.get('text'),
                'notes': lb.get('notes') or []
            }
        ]
    }
    return doc
