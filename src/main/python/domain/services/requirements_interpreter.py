import re
import unicodedata
from typing import List, Dict

Requirement = Dict[str, str]  # {"id": "R1", "text": "R1 — ..."}
UpdateCmd = Dict[str, object]  # {"type": "...", "targets": [1], "payload": "..."}


def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def normalize_pt(text: str) -> str:
    t = _strip_accents(text or "").lower().strip()
    t = re.sub(r'\s+', ' ', t)
    return t


def only_lines_R_hash(requirements: List[str]) -> List[Requirement]:
    """
    Recebe lista de textos (com ou sem prefixo), normaliza e devolve:
    [{"id": "R1", "text": "R1 — ..."}, ...]
    - Usa ' — ' (travessão) entre id e texto
    - Garante numeração sequencial
    - NUNCA inclui 'Justificativa'
    """
    out: List[Requirement] = []
    for i, raw in enumerate(requirements, start=1):
        clean = re.sub(r'^\s*[-*•]\s*', '', (raw or '').strip())
        clean = re.sub(r'^\s*R?\d+\s*[-–—:)]\s*', '', clean)
        clean = clean.rstrip('.').strip()
        out.append({"id": f"R{i}", "text": f"R{i} — {clean}"})
    return out


def format_for_ui(requirements: List[Requirement]) -> List[Dict]:
    """
    Mapeia para o que a UI consome. Garanta campo 'showJustificativa': False.
    """
    return [
        {
            "id": r["id"],
            "text": r["text"],
            "justification": None,
            "showJustificativa": False,
        }
        for r in requirements
    ]


def detect_requirements_discussion(user_text: str) -> bool:
    t = normalize_pt(user_text)
    keys = [
        "requisito", "r1", "r2", "r3", "r4", "r5", "troca", "substitu", "mudar",
        "melhora", "refaz", "gera outro", "nao gostei", "pode manter", "aceito", "ok pode ser", "mantem"
    ]
    return any(k in t for k in keys)


def parse_update_command(user_text: str) -> UpdateCmd:
    """
    Interpreta comandos de revisão do usuário em PT-BR:
    - aceitar tudo: 'pode manter', 'aceito', 'ok pode ser'
    - trocar um:    'troca o r3 para ...', 'gera outro para o r1', 'melhora o r2 com ...'
    - remover um:   'remove o r4', 'exclui r5'
    - inserir:      'adiciona mais um sobre ...'
    - refazer:      'refaz todos', 'gera tudo de novo'
    Retorna dicionário com type e alvos. Nunca None.
    """
    t = normalize_pt(user_text)

    if any(p in t for p in ["pode manter", "aceito", "ok pode ser", "pode ser", "mantem", "manter assim"]):
        return {"type": "accept_all", "targets": [], "payload": None}

    m = re.search(r'\b(r)(\d{1,2})\b', t)
    idx = int(m.group(2)) if m else None

    if any(p in t for p in ["troca", "substitui", "substitua", "gera outro", "refaz o r", "refazer o r", "melhora o r"]) and idx:
        pm = re.search(r'(?:para|por|com)\s+(.+)$', t)
        payload = pm.group(1).strip() if pm else ""
        return {"type": "replace_one", "targets": [idx], "payload": payload}

    if any(p in t for p in ["remove", "exclui", "apaga"]) and idx:
        return {"type": "remove_one", "targets": [idx], "payload": None}

    if any(p in t for p in ["adiciona", "insere", "inclui", "cria mais um"]):
        pm = re.search(r'(?:sobre|de)\s+(.+)$', t)
        payload = pm.group(1).strip() if pm else ""
        return {"type": "append_one", "targets": [], "payload": payload}

    if any(p in t for p in ["refaz todos", "refaz tudo", "gera tudo de novo", "refazer tudo", "gerar tudo de novo"]):
        return {"type": "regenerate_all", "targets": [], "payload": None}

    return {"type": "none", "targets": [], "payload": None}


def apply_update_command(cmd: UpdateCmd, current: List[Requirement]) -> List[Requirement]:
    """
    Aplica o comando NO LADO DO BACKEND (sem chamar LLM aqui).
    As gerações/alterações de texto ficam a cargo do serviço dinâmica (RAG/LLM).
    Aqui apenas estrutura, renumera e remove quando preciso.
    """
    ctype = cmd["type"]
    if ctype == "remove_one":
        targets = set(cmd["targets"])
        kept = [r for r in current if int(r["id"][1:]) not in targets]
        return only_lines_R_hash([r["text"].split(" — ", 1)[1] for r in kept])

    if ctype == "append_one":
        new_texts = [r["text"].split(" — ", 1)[1] for r in current]
        new_texts.append(cmd.get("payload") or "Requisito adicional (placeholder)")
        return only_lines_R_hash(new_texts)

    if ctype == "replace_one":
        idx = cmd["targets"][0]
        new_texts = [r["text"].split(" — ", 1)[1] for r in current]
        if 1 <= idx <= len(new_texts):
            new_texts[idx - 1] = cmd.get("payload") or new_texts[idx - 1]
        return only_lines_R_hash(new_texts)

    if ctype in ["none", "accept_all", "regenerate_all"]:
        return current

    return current
