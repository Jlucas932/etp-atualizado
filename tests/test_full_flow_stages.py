from domain.dto.EtpOrm import EtpSession
from domain.interfaces.dataprovider.DatabaseConfig import db

def test_full_stages_pca_price_legal_basis(app_ctx):
    s = EtpSession(session_id='FLOW1', conversation_stage='legal_norms', answers={'requirements': ['R1','R2','R3']})
    db.session.add(s); db.session.commit()

    # Simula o preenchimento das três fases
    answers = s.answers.copy()
    answers['pca'] = {'present': True, 'details': 'PCA nº 123/2025'}
    s.answers = answers
    s.conversation_stage = 'price_research'
    db.session.commit()

    answers = s.answers.copy()
    answers['price_research'] = {'method': 'painel_de_precos', 'supplier_count': 3, 'evidence_links': ['https://x']}
    s.answers = answers
    s.conversation_stage = 'legal_basis'
    db.session.commit()

    answers = s.answers.copy()
    answers['legal_basis'] = {'text': 'Lei 14.133/2021', 'notes': ['Observação de teste']}
    s.answers = answers
    s.conversation_stage = 'done'
    db.session.commit()

    s2 = EtpSession.query.filter_by(session_id='FLOW1').first()
    assert s2.conversation_stage == 'done'
    assert s2.answers['pca']['present'] is True
    assert s2.answers['price_research']['supplier_count'] == 3
    assert s2.answers['legal_basis']['text']
