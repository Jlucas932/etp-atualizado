from typing import List, Tuple

from domain.dto.EtpDto import Requirement
from domain.usecase.etp.dynamic_prompt_generator import (
    generate_requirements_rag_first,
    regenerate_single,
)


def init_etp_dynamic():  # pragma: no cover - compat placeholder
    """Mantém compatibilidade com chamadas legadas que inicializam componentes dinâmicos."""
    return None, None, None


def build_initial_requirements(necessity: str) -> Tuple[List[Requirement], str]:
    """Retorna requisitos iniciais em formato normalizado e a origem (rag|llm)."""
    requirements, source = generate_requirements_rag_first(necessity or "")
    return requirements, source


def regenerate_one(necessity: str, reqs: List[Requirement], index1: int) -> List[Requirement]:
    """Regera apenas um requisito mantendo os demais intactos."""
    return regenerate_single(necessity or "", reqs, index1)
