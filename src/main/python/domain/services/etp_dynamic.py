from __future__ import annotations

from typing import List, Tuple

from domain.usecase.etp.dynamic_prompt_generator import (
    generate_requirements_rag_first,
    regenerate_single,
)


def init_etp_dynamic():  # pragma: no cover - compat placeholder
    """Mantém compatibilidade com chamadas legadas que inicializam componentes dinâmicos."""
    return None, None, None


def build_initial_requirements(necessity: str) -> Tuple[List[str], str]:
    return generate_requirements_rag_first(necessity or "")


def regenerate_one(necessity: str, reqs: List[str], index1: int, hint: str | None = None) -> List[str]:
    return regenerate_single(necessity or "", reqs, index1, hint=hint)
