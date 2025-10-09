"""Utilities for interpreting and normalising ETP requirements discussions."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, List, Optional

RE_LINE = re.compile(r"^\s*(?:R\s*#?\s*|\(?R)?\s*(\d+)\s*[:\-\—]\s*(.+?)\s*$", re.IGNORECASE)
RE_ENUM = re.compile(r"^\s*(\d+)[\).]\s*(.+)$")
RE_BULLET = re.compile(r"^\s*[-•]\s*(.+)$")
RE_JUST = re.compile(r"\bjustificativa\s*:\s*", re.IGNORECASE)
RE_INDEX = re.compile(r"\br\s*#?\s*(\d{1,2})\b", re.IGNORECASE)
RE_GENERATE_MORE = re.compile(r"gera(?:r)?\s+mais\s+(\d+)")
RE_ADD_PLUS = re.compile(r"\+(\d+)")


@dataclass(frozen=True)
class RequirementIntent:
    intent: str
    target: Optional[int] = None
    amount: int = 0
    payload: Optional[str] = None


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text or "") if unicodedata.category(ch) != "Mn"
    )


def _normalise_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalise_text(text: str) -> str:
    """Return a lower-case, accent-stripped normalised string."""
    if not text:
        return ""
    text = _strip_accents(text)
    text = text.lower()
    return _normalise_spaces(text)


def _clean_requirement_body(body: str) -> str:
    cleaned = re.sub(r"\s+", " ", body or "").strip(" .;-–—")
    return cleaned


def normalize_requirements(raw: str | Iterable[str]) -> List[str]:
    """Normalise raw requirement text into ["R1 — ...", ...]."""
    if isinstance(raw, str):
        raw_lines = [line.strip() for line in raw.splitlines() if line.strip()]
    else:
        raw_lines = [str(line).strip() for line in raw if str(line).strip()]

    tmp: List[str] = []
    for line in raw_lines:
        match = RE_JUST.search(line)
        if match:
            line = line[: match.start()].strip()
        if not line:
            continue
        m = RE_LINE.match(line)
        if m:
            tmp.append(m.group(2))
            continue
        enum = RE_ENUM.match(line)
        if enum:
            tmp.append(enum.group(2))
            continue
        bullet = RE_BULLET.match(line)
        if bullet:
            tmp.append(bullet.group(1))
            continue
        tmp.append(line)

    seen: set[str] = set()
    deduped: List[str] = []
    for candidate in tmp:
        cleaned = _clean_requirement_body(candidate)
        if not cleaned:
            continue
        if cleaned.lower().startswith("justificativa"):
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)

    return [f"R{i + 1} — {text}" for i, text in enumerate(deduped)]


def _extract_payload(text: str, *, keywords: Iterable[str]) -> str:
    lowered = normalise_text(text)
    for keyword in keywords:
        idx = lowered.find(keyword)
        if idx >= 0:
            fragment = text[idx + len(keyword) :].strip()
            if fragment.startswith(":"):
                fragment = fragment[1:].strip()
            return fragment
    return ""


def parse_user_intent(user_text: str) -> RequirementIntent:
    """Parse user's PT-BR instruction about requirements."""
    normalised = normalise_text(user_text)
    if not normalised:
        return RequirementIntent("unknown")

    acceptance_markers = [
        "aceito",
        "aceitamos",
        "pode manter",
        "pode manter todos",
        "pode seguir",
        "ok seguir",
        "ok pode seguir",
        "fechou",
        "mantem",
        "manter assim",
    ]
    if any(marker in normalised for marker in acceptance_markers):
        return RequirementIntent("accept")

    keep_markers = ["mantem", "pode manter", "manter"]
    if any(marker in normalised for marker in keep_markers) and "nao" not in normalised:
        return RequirementIntent("accept")

    match = RE_GENERATE_MORE.search(normalised)
    if match:
        return RequirementIntent("generate_more", amount=int(match.group(1)))

    plus_match = RE_ADD_PLUS.search(normalised)
    if "+" in user_text and plus_match:
        return RequirementIntent("generate_more", amount=int(plus_match.group(1)))

    if "mais um" in normalised or "mais uma" in normalised:
        return RequirementIntent("generate_more", amount=1)

    if "exemplo" in normalised or "exemplifique" in normalised:
        return RequirementIntent("example")

    if any(marker in normalised for marker in ["padronize o tom", "padroniza o tom", "deixe mais objetivo", "reformula o tom", "reformule o tom", "reformular o tom", "reformular", "reformule"]):
        payload = _extract_payload(user_text, keywords=["deixe", "padronize", "reformule", "reformular"])
        return RequirementIntent("rephrase", payload=payload or None)

    index_match = RE_INDEX.search(normalised)
    target = int(index_match.group(1)) if index_match else None

    if any(marker in normalised for marker in ["remove", "remova", "exclui", "apaga"]) and target:
        return RequirementIntent("remove", target=target)

    if any(marker in normalised for marker in ["ajuste", "ajusta", "editar", "edite", "melhore", "melhora", "detalhe", "detalha", "aperfeiçoe", "aperfeicoe"]) and target:
        payload = _extract_payload(user_text, keywords=["para", "com", ":", "-", "=", "detalhe", "melhore"])
        return RequirementIntent("edit", target=target, payload=payload or None)

    if any(marker in normalised for marker in ["troca", "substitui", "substitua", "refaca", "refaça", "gera outro", "gere outro"]) and target:
        payload = _extract_payload(user_text, keywords=["por", "para", "com", "refaca", "refaça", "gera outro", "gere outro"])
        return RequirementIntent("replace", target=target, payload=payload or None)

    if "manter" in normalised and "nao" not in normalised:
        return RequirementIntent("accept")

    if "aceitar" in normalised and "nao" not in normalised:
        return RequirementIntent("accept")

    return RequirementIntent("unknown")


def strip_requirement_prefix(requirement: str) -> str:
    parts = requirement.split(" — ", 1)
    return parts[1] if len(parts) == 2 else requirement


def requirements_to_plain(requirements: Iterable[str]) -> List[str]:
    return [strip_requirement_prefix(req) for req in requirements]
