from typing import List, Tuple

from domain.services.requirements_interpreter import only_lines_R_hash


def retrieve_from_kb(necessity: str, topk: int = 8) -> List[str]:
    """
    Implemente a chamada ao seu mecanismo de RAG existente.
    Deve retornar uma lista de frases de requisito (sem 'R#'), se houver.
    Retorne [] quando não houver base suficiente.
    """
    # TODO: ligar no seu retriever real
    return []


def llm_generate_requirements(necessity: str) -> List[str]:
    """
    Gera requisitos via LLM quando o RAG não cobrir.
    O prompt deve EXIGIR apenas 5 a 8 linhas, cada uma iniciando com um verbo no infinitivo,
    sem justificativas e sem resumos. Sem numeração; nós numeramos depois.
    """
    # TODO: ligar no seu provedor LLM
    return [
        "Especificar parâmetros técnicos essenciais para a solução",
        "Exigir mecanismos de segurança compatíveis com a criticidade do serviço",
        "Garantir suporte técnico com prazos definidos e rastreáveis",
        "Implementar indicadores de desempenho auditáveis",
        "Apresentar relatórios periódicos de conformidade",
    ]


def generate_requirements_rag_first(necessity: str) -> Tuple[List[dict], str]:
    base = retrieve_from_kb(necessity)
    source = "rag" if base else "llm"
    lines = base or llm_generate_requirements(necessity)
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
        generated = llm_generate_requirements(necessity)
        new_line = generated[0] if generated else others[index1 - 1]

    others[index1 - 1] = new_line
    return only_lines_R_hash(others)
