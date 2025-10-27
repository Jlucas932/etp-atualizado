from typing import Dict, Any
from .types import EtpParts, DocSection

def assemble_sections(parts: EtpParts) -> Dict[DocSection, str]:
    """
    Assembles ETP document sections from stage outputs.
    
    This function is the ONLY source for preview/DOCX generation.
    Chat stages never directly output document sections like "Justificativa da Contratação".
    
    Args:
        parts: EtpParts containing data collected from all stages
        
    Returns:
        Dictionary mapping DocSection enums to their text content
    """
    out: Dict[DocSection, str] = {}

    # 1. INTRODUÇÃO — vem do summary (resumo executivo) + cabeçalho fixo
    if parts.resumo_executivo:
        out[DocSection.INTRODUCAO] = parts.resumo_executivo

    # 2. OBJETO E ESPECIFICAÇÕES
    if parts.necessidade_texto:
        out[DocSection.OBJETO_DESC_NECESSIDADE] = parts.necessidade_texto
    if parts.pca_texto:
        out[DocSection.OBJETO_PCA] = parts.pca_texto

    # 3. REQUISITOS
    if parts.requisitos:
        out[DocSection.REQ_TECNICOS] = "\n".join(parts.requisitos)
    if parts.normas:
        out[DocSection.REQ_NORMATIVOS] = "\n".join(
            [f"- {n.get('ref','')}: {n.get('aplica','')}" for n in parts.normas]
        )

    # 4 & 6. ESTIMATIVAS (quantidades e valor)
    if parts.itens_valor:
        tabela = "\n".join([f"- {i['descricao']}: {i['quantidade']} x {i['valor_unit']}" for i in parts.itens_valor])
        out[DocSection.ESTIMATIVA_QTD] = tabela
        out[DocSection.ESTIMATIVA_VALOR] = tabela
    if parts.metodologia_valor:
        out[DocSection.ESTIMATIVA_VALOR] = (out.get(DocSection.ESTIMATIVA_VALOR,"") + f"\n\nMetodologia: {parts.metodologia_valor}").strip()

    # 7. SOLUÇÃO COMO UM TODO — síntese da recomendação/estratégias
    if parts.recomendacao:
        out[DocSection.SOLUCAO_COMO_UM_TODO] = parts.recomendacao

    # 8. JUSTIFICATIVA DO PARCELAMENTO — do stage installment (não do chat anterior)
    if parts.parcelamento_decisao or parts.parcelamento_texto:
        out[DocSection.JUSTIFICATIVA_PARCELAMENTO] = f"{parts.parcelamento_decisao or ''}\n{parts.parcelamento_texto or ''}".strip()

    # Demais seções podem permanecer em branco ou serem preenchidas por etapas futuras, se existirem.
    return out
