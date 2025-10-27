from domain.dto.EtpOrm import db, EtpSession
from domain.usecase.etp.document_composer import compose_etp_document

def test_compose_document_basic(app_ctx):
    s = EtpSession(session_id='DOC1', conversation_stage='done',
                   answers={'requirements':['R1','R2'],
                            'pca':{'present':True,'details':'PCA 123/2025'},
                            'price_research':{'method':'painel_de_precos','supplier_count':3,'evidence_links':['https://x']},
                            'legal_basis':{'text':'Lei 14.133/2021','notes':['Obs']}},
                   )
    s.necessity = 'Aquisição de XYZ'
    db.session.add(s); db.session.commit()
    doc = compose_etp_document(s)
    assert doc['title']
    assert any(sec['id']=='requirements' for sec in doc['sections'])
