from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from domain.services.requirements_interpreter import normalize_requirements


def retrieve_from_kb(necessity: str, topk: int = 5) -> List[Tuple[str, float]]:
    """Return candidate requirement bodies (text, score) from the knowledge base."""
    return []


def llm_generate_requirements(necessity: str, amount: int = 5, hint: str | None = None) -> List[str]:
    """Fallback deterministic LLM stub for tests."""
    base_text = hint.strip() if hint else f"Atender a necessidade: {necessity}".strip()
    suggestions: List[str] = []
    for i in range(amount):
        suffix = f" (var {i + 1})" if amount > 1 else ""
        if hint and i == 0:
            suggestions.append(_clean_candidate(base_text))
        else:
            suggestions.append(_clean_candidate(f"{base_text} requisito {i + 1}" + suffix))
    return suggestions


def _clean_candidate(text: str) -> str:
    return " ".join(str(text or "").split()).strip(" .;–—")


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for item in items:
        cleaned = _clean_candidate(item)
        lower = cleaned.lower()
        if not cleaned or lower in seen:
            continue
        seen.add(lower)
        ordered.append(cleaned)
    return ordered


def generate_requirements(necessity: str, k: int = 5) -> List[str]:
    """Generate deterministic requirements following the RAG-first policy."""
    rag_candidates = sorted(
        retrieve_from_kb(necessity, topk=k * 2),
        key=lambda pair: (-pair[1], pair[0].lower()),
    )
    rag_texts = [pair[0] for pair in rag_candidates][:k]

    requirements: List[str] = list(rag_texts)

    if len(requirements) < 3:
        llm_needed = max(k - len(requirements), 3 - len(requirements))
        requirements.extend(llm_generate_requirements(necessity, amount=llm_needed))

    if len(requirements) < k:
        requirements.extend(llm_generate_requirements(necessity, amount=k - len(requirements)))

    requirements = _dedupe_preserve_order(requirements)

    if len(requirements) < k:
        while len(requirements) < k:
            requirements.append(f"Requisito adicional {len(requirements) + 1}")

    normalized = normalize_requirements(requirements)
    return normalized


def choose_new_requirement(necessity: str, existing_plain: Sequence[str], hint: str | None = None) -> str:
    """Return a new single requirement body, respecting RAG-first policy."""
    existing_set = {item.lower().strip() for item in existing_plain}

    rag_candidates = sorted(
        retrieve_from_kb(necessity, topk=len(existing_plain) + 5),
        key=lambda pair: (-pair[1], pair[0].lower()),
    )
    for candidate, _score in rag_candidates:
        cleaned = _clean_candidate(candidate)
        if cleaned.lower() not in existing_set and cleaned:
            return cleaned

    llm_candidates = llm_generate_requirements(necessity, amount=max(3, len(existing_plain) // 2 or 1), hint=hint)
    for candidate in llm_candidates:
        cleaned = _clean_candidate(candidate)
        if cleaned.lower() not in existing_set and cleaned:
            return cleaned

    if hint:
        fallback = _clean_candidate(hint)
        if fallback:
            return fallback

    return f"Complementar requisito {len(existing_plain) + 1}"


def regenerate_list_with_hint(necessity: str, existing_plain: Sequence[str], hint: str | None = None) -> List[str]:
    new_items = list(existing_plain)
    candidate = choose_new_requirement(necessity, existing_plain, hint=hint)
    new_items.append(candidate)
    return normalize_requirements(new_items)


def generate_requirements_rag_first(necessity: str) -> Tuple[List[str], str]:
    normalized = generate_requirements(necessity)
    rag_candidates = retrieve_from_kb(necessity)
    source = "rag" if rag_candidates else "llm"
    return normalized, source


def regenerate_single(necessity: str, current: Sequence[str], index1: int, hint: str | None = None) -> List[str]:
    if not current or index1 < 1 or index1 > len(current):
        return list(current)
    plain = [item.split(" — ", 1)[1] if " — " in item else item for item in current]
    replacement = choose_new_requirement(necessity, plain, hint=hint)
    plain[index1 - 1] = replacement
    return normalize_requirements(plain)
