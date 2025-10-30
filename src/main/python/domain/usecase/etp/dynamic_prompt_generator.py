import random
import re
from typing import List, Optional, Sequence, Tuple

from domain.services.requirements_interpreter import only_lines_R_hash


def retrieve_from_kb(necessity: str, topk: int = 8) -> List[str]:
    """
    Implemente a chamada ao seu mecanismo de RAG existente.
    Deve retornar uma lista de frases de requisito (sem 'R#'), se houver.
    Retorne [] quando não houver base suficiente.
    """
    # TODO: ligar no seu retriever real
    return []


def _normalize(text: str) -> str:
    cleaned = re.sub(r"^\s*R?\d+\s*[-–—:)]\s*", "", text or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned.strip().lower())
    return cleaned


def decide_requirements_count(necessity: str) -> int:
    """Decide how many requirements to generate (between 5 and 20)."""

    text = (necessity or "").strip().lower()
    if not text:
        return random.randint(7, 10)

    high_complexity_keywords = [
        "sistema",
        "gestão",
        "gestao",
        "plataforma",
        "software",
        "hospital",
        "hospitalar",
        "monitoramento",
        "central",
        "rede",
        "integração",
        "integracao",
        "data center",
        "segurança da informação",
        "seguranca da informacao",
        "inteligência",
        "inteligencia",
    ]

    service_keywords = [
        "serviço",
        "servico",
        "manutenção",
        "manutencao",
        "consultoria",
        "suporte",
        "outsourcing",
        "locação",
        "locacao",
        "terceirização",
        "terceirizacao",
    ]

    vehicle_keywords = [
        "carro",
        "veículo",
        "veiculo",
        "viatura",
        "automóvel",
        "automovel",
        "ônibus",
        "onibus",
        "caminhão",
        "caminhao",
    ]

    low_complexity_keywords = [
        "cadeira",
        "mesa",
        "mobiliário",
        "mobiliario",
        "material de escritório",
        "material de escritorio",
        "suprimento",
        "suprimentos",
        "periférico",
        "periferico",
        "acessório",
        "acessorio",
    ]

    words = set(re.split(r"\W+", text))

    if any(keyword in text for keyword in high_complexity_keywords) or len(words) > 25:
        return random.randint(14, 18)

    if any(keyword in text for keyword in service_keywords) or 15 < len(words) <= 25:
        return random.randint(10, 14)

    if any(keyword in text for keyword in vehicle_keywords):
        return random.randint(8, 12)

    if any(keyword in text for keyword in low_complexity_keywords) or len(words) <= 12:
        return random.randint(5, 8)

    return random.randint(8, 14)


_FALLBACK_TEMPLATES: Sequence[Tuple[str, str]] = (
    ("Obrigatório", "Apresentar plano detalhado de execução do {obj} com marcos mensais e tolerância máxima de 5% de atraso"),
    ("Obrigatório", "Comprovar atendimento às normas técnicas e regulatórias aplicáveis ao {obj}, anexando certificações válidas"),
    ("Obrigatório", "Disponibilizar equipe técnica com experiência mínima de 3 anos relacionada a {obj}"),
    ("Obrigatório", "Garantir suporte técnico remoto em até 4 horas úteis após abertura de chamado referente ao {obj}"),
    ("Obrigatório", "Fornecer treinamento inicial sobre {obj} para a equipe do órgão, registrando presença e conteúdo aplicado"),
    ("Obrigatório", "Entregar documentação técnica completa do {obj} em português, incluindo revisões de configuração"),
    ("Obrigatório", "Apresentar garantia mínima de 12 meses cobrindo peças, mão de obra e deslocamentos ligados ao {obj}"),
    ("Obrigatório", "Implementar indicadores mensais de desempenho para o {obj}, com metas numéricas e evidências de medição"),
    ("Obrigatório", "Manter estoque de peças e insumos críticos para o {obj} com reposição em até 48 horas"),
    ("Obrigatório", "Executar testes de aceitação do {obj} com checklist aprovado pelo contratante antes da entrada em operação"),
    ("Desejável", "Disponibilizar canal de atendimento 24x7 para incidentes críticos relacionados ao {obj}"),
    ("Desejável", "Oferecer atualização tecnológica anual do {obj} sem custo adicional de licenciamento"),
    ("Desejável", "Realizar reuniões trimestrais de acompanhamento do {obj}, apresentando planos de ação para desvios"),
    ("Desejável", "Emitir relatórios bimestrais de conformidade do {obj} com evidências anexadas"),
    ("Desejável", "Garantir integração do {obj} com sistemas legados por meio de APIs documentadas"),
    ("Desejável", "Disponibilizar capacitação complementar sob demanda para usuários do {obj}"),
    ("Desejável", "Implementar mecanismos de gestão de riscos associados ao {obj}, revisando-os semestralmente"),
    ("Desejável", "Manter ambiente de testes homologado para validação do {obj} antes de atualizações em produção"),
    ("Desejável", "Oferecer suporte presencial em até 24 horas quando incidentes de alto impacto afetarem o {obj}"),
    ("Desejável", "Atualizar inventário e rastreabilidade de componentes vinculados ao {obj} a cada trimestre"),
)


def llm_generate_requirements(
    necessity: str,
    target_count: Optional[int] = None,
    existing: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    Gera requisitos via LLM quando o RAG não cobrir.
    O prompt deve EXIGIR apenas 5 a 8 linhas, cada uma iniciando com um verbo no infinitivo,
    sem justificativas e sem resumos. Sem numeração; nós numeramos depois.
    """
    target = target_count or decide_requirements_count(necessity)
    object_label = (necessity or "objeto contratado").strip() or "objeto contratado"

    pool = list(_FALLBACK_TEMPLATES)
    random.shuffle(pool)

    existing_norm = {_normalize(text) for text in (existing or []) if text}
    results: List[str] = []

    for label, template in pool:
        if len(results) >= target:
            break
        candidate = f"({label}) {template.format(obj=object_label)}"
        norm_candidate = _normalize(candidate)
        if norm_candidate in existing_norm:
            continue
        results.append(candidate)
        existing_norm.add(norm_candidate)

    # If templates not enough (target up to 20), create generic placeholders to meet count
    while len(results) < target:
        idx = len(results) + 1
        generic = (
            f"(Obrigatório) Detalhar entregáveis numerados ({idx}) para {object_label} com métrica e forma de verificação"
        )
        norm_generic = _normalize(generic)
        if norm_generic not in existing_norm:
            results.append(generic)
            existing_norm.add(norm_generic)

    return results


def generate_requirements_rag_first(necessity: str) -> Tuple[List[dict], str]:
    target = decide_requirements_count(necessity)
    base = retrieve_from_kb(necessity)
    source = "rag" if base else "llm"
    lines = list(base[:target]) if base else []
    known_norms = {_normalize(l) for l in lines}

    if len(lines) < target:
        llm_lines = llm_generate_requirements(necessity, target_count=target, existing=lines)
        for line in llm_lines:
            norm_line = _normalize(line)
            if norm_line not in known_norms:
                lines.append(line)
                known_norms.add(norm_line)
            if len(lines) >= target:
                break

    if not lines:
        lines = llm_generate_requirements(necessity, target_count=target)

    reqs = only_lines_R_hash(lines)
    return reqs, source


def regenerate_single(necessity: str, current: List[dict], index1: int) -> List[dict]:
    """
    Regenera APENAS um requisito (R{index1}) usando RAG-first limitado ao tópico do R alvo,
    caindo no LLM se preciso. Mantém os demais intactos e renumera.
    """
    if not current or index1 < 1 or index1 > len(current):
        return current

    others = [r["text"].split(" — ", 1)[1] for r in current]
    candidate = retrieve_from_kb(necessity)
    new_line = None
    if candidate:
        new_line = candidate[0]
    else:
        generated = llm_generate_requirements(
            necessity,
            target_count=1,
            existing=others,
        )
        new_line = generated[0] if generated else others[index1 - 1]

    others[index1 - 1] = new_line
    return only_lines_R_hash(others)
