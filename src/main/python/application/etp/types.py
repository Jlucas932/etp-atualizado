from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class ChatStage(str, Enum):
    collect_need = "collect_need"
    suggest_requirements = "suggest_requirements"
    solution_strategies = "solution_strategies"
    pca = "pca"
    legal_norms = "legal_norms"
    qty_value = "qty_value"
    installment = "installment"
    summary = "summary"
    preview = "preview"

class DocSection(str, Enum):
    INTRODUCAO = "1_introducao"
    OBJETO_ESPEC = "2_objeto_especificacoes"
    OBJETO_LOCAL = "2_1_local_execucao"
    OBJETO_NATUREZA_FINALIDADE = "2_2_natureza_finalidade"
    OBJETO_SIGILO = "2_3_classificacao_sigilo"
    OBJETO_DESC_NECESSIDADE = "2_4_descricao_necessidade"
    OBJETO_PCA = "2_5_previsao_pca"
    REQUISITOS = "3_requisitos"
    REQ_TECNICOS = "3_1_requisitos_tecnicos"
    REQ_SUSTENTABILIDADE = "3_2_requisitos_sustentabilidade"
    REQ_NORMATIVOS = "3_3_requisitos_normativos"
    ESTIMATIVA_QTD = "4_estimativa_quantidades"
    LEVANTAMENTO_MERCADO = "5_levantamento_mercado"
    ESTIMATIVA_VALOR = "6_estimativa_valor"
    SOLUCAO_COMO_UM_TODO = "7_solucao_como_um_todo"
    JUSTIFICATIVA_PARCELAMENTO = "8_justificativa_parcelamento"
    RESULTADOS_PRETENDIDOS = "9_resultados_pretendidos"
    PROVIDENCIAS_PREVIAS = "10_providencias_previas"
    CONTRATACOES_CORRELATAS = "11_contratacoes_correlatas"
    IMPACTOS_AMBIENTAIS = "12_impactos_ambientais"
    MAPA_RISCOS = "13_mapa_de_riscos"
    POSICIONAMENTO_CONCLUSIVO = "14_posicionamento_conclusivo"

@dataclass
class StagePayload:
    stage: ChatStage
    data: Dict[str, Any]
    text: str

@dataclass
class EtpParts:
    # Campos preenchidos progressivamente pelo fluxo
    necessidade_texto: Optional[str] = None
    requisitos: List[str] = field(default_factory=list)
    estrategias: List[Dict[str, Any]] = field(default_factory=list)
    recomendacao: Optional[str] = None
    pca_status: Optional[str] = None
    pca_texto: Optional[str] = None
    normas: List[Dict[str, str]] = field(default_factory=list)
    itens_valor: List[Dict[str, Any]] = field(default_factory=list)
    metodologia_valor: Optional[str] = None
    parcelamento_decisao: Optional[str] = None
    parcelamento_texto: Optional[str] = None
    resumo_executivo: Optional[str] = None
