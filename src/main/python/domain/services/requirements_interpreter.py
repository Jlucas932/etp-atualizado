"""Ferramentas determinísticas para revisão de requisitos do ETP."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Iterable, Optional, Tuple

ORDINAL_KEYWORDS = {
    "primeiro": 1,
    "primeira": 1,
    "segundo": 2,
    "segunda": 2,
    "terceiro": 3,
    "terceira": 3,
    "quarto": 4,
    "quarta": 4,
    "quinto": 5,
    "quinta": 5,
    "sexto": 6,
    "sexta": 6,
    "sétimo": 7,
    "sétima": 7,
    "setimo": 7,
    "setima": 7,
    "oitavo": 8,
    "oitava": 8,
    "nono": 9,
    "nona": 9,
    "décimo": 10,
    "décima": 10,
    "decimo": 10,
    "decima": 10,
}

ACCEPT_KEYWORDS = {
    "aceitar",
    "aceito",
    "aceite",
    "está bom",
    "esta bom",
    "pode seguir",
    "pode prosseguir",
    "pode avançar",
    "confirmo",
    "confirmar",
    "perfeito",
    "ok",
    "fechar requisitos",
    "pode manter",
    "pode ser",
}

REFAZER_KEYWORDS = {
    "refazer tudo",
    "refaça tudo",
    "refaz tudo",
    "refazê tudo",
    "refazer a lista",
    "nova lista completa",
    "gera outra lista",
    "gerar outra lista",
    "quero outra versão completa",
    "quero uma nova lista",
}

REMOVE_KEYWORDS = {"remover", "remove", "tirar", "excluir", "deletar", "apagar", "retirar"}
EDIT_KEYWORDS = {
    "ajustar",
    "ajuste",
    "alterar",
    "alterar",
    "editar",
    "modificar",
    "mudar",
    "trocar",
    "substituir",
    "refazer",
}
INSERT_KEYWORDS = {"inserir", "insira", "incluir", "inclua", "adicionar", "adiciona", "acrescentar", "acrescente"}
REINFORCE_KEYWORDS = {"reforçar", "reforce", "detalhar", "detalhe", "completar", "completa", "reforça"}
RANGE_SEPARATORS = {"-", "–", "—", "até", "a"}


@dataclass
class Requirement:
    """Representação simplificada de um requisito."""

    id: str
    text: str

    @staticmethod
    def from_dict(raw: Dict[str, Any], position: int | None = None) -> "Requirement":
        """Cria instância a partir de dicionário, descartando metadados."""
        idx = position if position is not None else _extract_index(raw.get("id"))
        return Requirement(id=f"R{idx}", text=str(raw.get("text", "")).strip())

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "text": self.text}


@dataclass
class RequirementCommand:
    """Descrição de uma operação determinística sobre requisitos."""

    intent: str
    targets: List[int] = field(default_factory=list)
    text: Optional[str] = None
    topic: Optional[str] = None


def parse_update_command(user_text: str, requirements: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Interpreta comandos de revisão escritos em português."""
    text = user_text.strip()
    if not text:
        return {"intent": "unclear", "reason": "empty"}

    lower = text.lower()
    total = len(list(requirements))

    if any(keyword in lower for keyword in REFAZER_KEYWORDS):
        return {"intent": "refazer_all"}

    if any(keyword in lower for keyword in ACCEPT_KEYWORDS):
        return {"intent": "accept"}

    if _mentions_need_change(lower):
        return {"intent": "change_need"}

    targets = _resolve_targets(lower, total)

    if any(keyword in lower for keyword in REMOVE_KEYWORDS) and targets:
        return {"intent": "remove", "targets": targets}

    if any(keyword in lower for keyword in INSERT_KEYWORDS):
        return {
            "intent": "insert",
            "text": _extract_requested_text(text, INSERT_KEYWORDS),
        }

    if any(keyword in lower for keyword in REINFORCE_KEYWORDS) and targets:
        return {
            "intent": "reinforce",
            "targets": targets,
            "text": _extract_requested_text(text, REINFORCE_KEYWORDS),
        }

    if any(keyword in lower for keyword in EDIT_KEYWORDS) and targets:
        return {
            "intent": "edit",
            "targets": targets,
            "text": _extract_requested_text(text, EDIT_KEYWORDS),
        }

    if targets:
        # Default interpretation: edit the referenced items
        return {
            "intent": "edit",
            "targets": targets,
            "text": _extract_requested_text(text, set()),
        }

    return {"intent": "unclear", "reason": "no_targets"}


def apply_update_command(
    command: Dict[str, Any],
    requirements: List[Dict[str, Any]],
    necessity: str | None = None,
) -> Tuple[List[Dict[str, str]], str]:
    """Aplica um comando determinístico na lista de requisitos."""

    normalized = [_coerce_requirement(req, i + 1) for i, req in enumerate(requirements)]
    intent = command.get("intent")

    if intent == "accept":
        return _export(normalized), "Perfeito! Requisitos confirmados."

    if intent == "refazer_all":
        return [], "Certo, vou refazer toda a lista de requisitos considerando as novas orientações."

    if intent == "change_need":
        return _export(normalized), (
            "Para mudar a necessidade, precisamos reiniciar o fluxo completo. Confirme se deseja prosseguir."
        )

    if intent == "remove":
        targets = set(command.get("targets", []))
        kept = [req for idx, req in enumerate(normalized, 1) if idx not in targets]
        message = (
            f"Removi {len(normalized) - len(kept)} requisito(s)."
            if kept or normalized
            else "Não havia requisitos para remover."
        )
        return _export(_renumber(kept)), message

    if intent == "edit":
        text = command.get("text")
        targets = set(command.get("targets", []))
        updated = []
        for idx, req in enumerate(normalized, 1):
            if idx in targets and text:
                updated.append(Requirement(id=f"R{len(updated)+1}", text=text))
            else:
                updated.append(req)
        message = (
            "Atualizei os requisitos solicitados." if text else "Indique o novo texto para concluir a alteração."
        )
        return _export(_renumber(updated)), message

    if intent == "reinforce":
        detail = command.get("text")
        targets = set(command.get("targets", []))
        if not detail:
            return _export(normalized), "Preciso do detalhe para reforçar o requisito."
        updated = []
        for idx, req in enumerate(normalized, 1):
            if idx in targets:
                merged = f"{req.text}. {detail}" if not detail.startswith(req.text) else detail
                updated.append(Requirement(id=req.id, text=merged.strip()))
            else:
                updated.append(req)
        return _export(updated), "Reforcei o requisito com as informações indicadas."

    if intent == "insert":
        text = (command.get("text") or "").strip()
        if not text:
            return _export(normalized), "Descreva o requisito que deseja incluir."
        normalized.append(Requirement(id=f"R{len(normalized)+1}", text=text))
        return _export(normalized), "Requisito adicionado ao final da lista."

    return _export(normalized), (
        "Não compreendi o ajuste. Você pode especificar se deseja inserir, remover ou editar algum requisito?"
    )


def detect_requirements_discussion(user_text: str) -> bool:
    """Indica se a mensagem do usuário trata de revisão de requisitos."""
    lower = user_text.lower()
    requirement_markers = [
        "requisito",
        "r1",
        "r2",
        "r3",
        "r4",
        "r5",
        "último",
        "ultimo",
        "penúltimo",
        "penultimo",
        "ajust",
        "remov",
        "inser",
        "adicion",
        "editar",
        "trocar",
        "manter",
        "aceitar",
        "confirmo",
    ]
    return any(marker in lower for marker in requirement_markers)


def format_requirements_list(requirements: List[Dict[str, Any]]) -> str:
    """Formata requisitos como linhas 'R# — texto'."""
    sanitized = [_coerce_requirement(req, idx + 1) for idx, req in enumerate(requirements)]
    if not sanitized:
        return "Nenhum requisito definido ainda."
    return "\n".join(f"{req.id} — {req.text}" for req in sanitized)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_index(identifier: Optional[str]) -> int:
    if not identifier:
        return 0
    match = re.search(r"(\d+)", str(identifier))
    return int(match.group(1)) if match else 0


def _mentions_need_change(lower: str) -> bool:
    return bool(
        re.search(
            r"nova\s+necessidade|trocar\s+a\s+necessidade|mudou\s+a\s+necessidade|necessidade\s+é\s+outra",
            lower,
        )
    )


def _resolve_targets(text: str, total: int) -> List[int]:
    indices: List[int] = []

    for match in re.findall(r"r\s*(\d+)", text):
        idx = int(match)
        if 1 <= idx <= total:
            indices.append(idx)

    for match in re.findall(r"\b(\d+)\b", text):
        idx = int(match)
        if 1 <= idx <= total and idx not in indices:
            indices.append(idx)

    for word, value in ORDINAL_KEYWORDS.items():
        if word in text and 1 <= value <= total and value not in indices:
            indices.append(value)

    if ("último" in text or "ultimo" in text) and total > 0 and total not in indices:
        indices.append(total)

    if ("penúltimo" in text or "penultimo" in text) and total > 1:
        idx = total - 1
        if idx not in indices:
            indices.append(idx)

    # Ranges (e.g. R2-R4 or 2 a 4)
    range_pattern = r"(r?\d+)\s*(?:-|–|—|até|a)\s*(r?\d+)"
    for raw_start, raw_end in re.findall(range_pattern, text):
        start = _extract_index(raw_start) or int(raw_start)
        end = _extract_index(raw_end) or int(raw_end)
        if start > end:
            start, end = end, start
        for idx in range(start, end + 1):
            if 1 <= idx <= total and idx not in indices:
                indices.append(idx)

    indices.sort()
    return indices


def _extract_requested_text(original: str, keywords: Iterable[str]) -> str:
    lower = original.lower()
    snippet: Optional[str] = None
    for keyword in keywords:
        idx = lower.find(keyword)
        if idx >= 0:
            snippet = original[idx + len(keyword) :].strip()
            snippet = snippet.lstrip(":-–— ")
            break

    if snippet is None and ":" in original:
        after_colon = original.split(":", 1)[1].strip()
        if after_colon:
            snippet = after_colon

    if snippet is None:
        quoted = re.findall(r"[\'\"]([^\'\"]+)[\'\"]", original)
        if quoted:
            snippet = quoted[0].strip()

    if snippet is None:
        snippet = original.strip()

    snippet = re.sub(r"^(?:r\d+\s*(?:[\-–—]\s*r?\d+)*)\s*", "", snippet, flags=re.IGNORECASE)
    snippet = snippet.strip()
    for token in ("para", "por", "com", "sobre"):
        if snippet.lower().startswith(token + " "):
            snippet = snippet[len(token):].strip()
            break
    return snippet


def _coerce_requirement(raw: Dict[str, Any], position: int) -> Requirement:
    if isinstance(raw, Requirement):
        req = raw
    else:
        req = Requirement.from_dict(raw, position)
    if not req.text:
        req = Requirement(id=req.id, text="")
    return req


def _renumber(requirements: List[Requirement]) -> List[Requirement]:
    return [Requirement(id=f"R{idx}", text=req.text) for idx, req in enumerate(requirements, 1)]


def _export(requirements: List[Requirement]) -> List[Dict[str, str]]:
    return [req.to_dict() for req in requirements]

