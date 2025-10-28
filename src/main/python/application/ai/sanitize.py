BLOCKED_TITLES = ("justificativa", "nota técnica")


def is_blocked_text(s: str) -> bool:
    return bool(s and any(word in s.lower() for word in BLOCKED_TITLES))


def keep_only_expected(obj: dict) -> dict:
    return {k: v for k, v in (obj or {}).items() if k in {"requisitos", "estrategias"}}
