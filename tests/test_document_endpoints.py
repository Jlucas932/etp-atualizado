from domain.dto.EtpOrm import db, EtpSession

def test_generate_and_fetch_html(client):
    s = EtpSession(session_id='SIDX', conversation_stage='done',
                   answers={'requirements':['R1'],
                            'pca':{'present':True},
                            'price_research':{'method':'painel_de_precos','supplier_count':1,'evidence_links':[]},
                            'legal_basis':{'text':'Lei 14.133'}})
    s.necessity = 'Objeto teste'
    db.session.add(s); db.session.commit()

    resp = client.post('/api/etp-dynamic/generate-document', json={'session_id':'SIDX'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] and data.get('doc_id')

    resp2 = client.get(f"/api/etp-dynamic/document/{data['doc_id']}/html")
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2['success'] and '<html' in data2['html'].lower()
