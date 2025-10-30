import re

ACCEPT = "ACCEPT"
EDIT = "EDIT"
UNCLEAR = "UNCLEAR"

ACCEPT_PATTERNS = [
    r"\b(sim|pode seguir|segue|fechou|perfeito|perfeita|ótimo|otimo|tá ótimo|ta otimo|está bom|esta bom|vamos em frente|acho que está bom|ok, pode|ok pode)\b",
]

EDIT_PATTERNS = [
    r"\b(troca(r)?|muda(r)?|altera(r)?|remove(r)?|exclui(r)?|apaga(r)?|adiciona(r)?|inclui(r)?|ajusta(r)?|corrige(r)?)\b",
    r"\b(não? gostei do|nao? curti|faltou|ficou faltando|prefiro|queria que|reduz|aumenta|eleva|diminui|muda o sla|troca o sla)\b",
]

UNCLEAR_PATTERNS = [
    r"^\s*(ok|beleza|entendi|uhum|certo)\s*$",
]

def detect_intent(user_text: str) -> str:
    if not user_text or not user_text.strip():
        return UNCLEAR
    txt = user_text.lower()

    if any(re.search(p, txt) for p in EDIT_PATTERNS):
        return EDIT
    if any(x in txt for x in [
        "não gostei",
        "nao gostei",
        "substitua",
        "troque",
        "gere outros",
        "gere novos",
        "mude o",
        "refaça",
        "refaca",
        "recrie",
        "refazer requisito",
        "substituir",
    ]):
        return EDIT
    if any(re.search(p, txt) for p in ACCEPT_PATTERNS):
        return ACCEPT
    if any(re.search(p, txt) for p in UNCLEAR_PATTERNS):
        return UNCLEAR

    if re.search(r"\b(bom|boa|legal|bacana|show|massa|top|mandou bem|curti)\b", txt):
        return ACCEPT

    if "requisit" in txt and "?" in txt:
        return UNCLEAR

    return UNCLEAR
