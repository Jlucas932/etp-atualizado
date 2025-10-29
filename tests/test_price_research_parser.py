from domain.usecase.etp.price_research_interpreter import parse_price_research

def test_price_research_basic():
    assert parse_price_research("Painel de preços", {})['intent'] == 'method_select'
    assert parse_price_research("Consultamos 3 fornecedores", {})['intent'] == 'supplier_count'
    out = parse_price_research("Segue link https://exemplo.com/painel", {})
    assert out['intent'] == 'link_evidence' and out['payload']['urls']
    assert parse_price_research("Concluído", {})['intent'] == 'mark_done'
