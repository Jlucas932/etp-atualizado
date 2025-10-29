from __future__ import annotations
import os
import httpx
import logging

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_URL = "https://api.openai.com/v1/chat/completions"

# Unified model and temperature for all stages
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
TEMP = float(os.getenv("ETP_TEMP", "0.7"))

logger.info(f"[MODELS] using model={MODEL} temp={TEMP}")

HEADERS = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

SYSTEM_CHAT = (
  "Você é um consultor de ETP. Explique, proponha alternativas, faça perguntas abertas, "
  "aceite incertezas do usuário e ajude a decidir. Evite menu rígido."
)

SYSTEM_FINAL = (
  "Você é um redator técnico. Gere síntese clara, análise de alternativas com prós/contras, "
  "e texto pronto para compor o ETP. Seja objetivo e fundamentado."
)

class OpenAIChatConsultive:
    def generate(self, user_prompt: str) -> str:
        logger.info(f"[GENERATOR] stage=consultoria using model={MODEL} temp={TEMP}")
        payload = {
            "model": MODEL,
            "temperature": TEMP,
            "messages": [
                {"role":"system","content":SYSTEM_CHAT},
                {"role":"user","content":user_prompt}
            ]
        }
        with httpx.Client(timeout=60) as cli:
            r = cli.post(BASE_URL, headers=HEADERS, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

class OpenAIFinalWriter:
    def generate(self, user_prompt: str) -> str:
        logger.info(f"[GENERATOR] stage=resumo_etp using model={MODEL} temp={TEMP}")
        payload = {
            "model": MODEL,
            "temperature": TEMP,
            "messages": [
                {"role":"system","content":SYSTEM_FINAL},
                {"role":"user","content":user_prompt}
            ]
        }
        with httpx.Client(timeout=120) as cli:
            r = cli.post(BASE_URL, headers=HEADERS, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

class OpenAIIntentParser:
    """
    Extrai {intent, slots} de forma barata/determinística.
    Suporta intents expandidos para PCA, escolha de opções e confirmações curtas.
    """
    INTENT_SCHEMA = """
    Você é um parser de intenções para um sistema de ETP (Estudo Técnico Preliminar).
    Analise a mensagem do usuário e retorne um JSON com:
    - intent: um de [confirm, add, remove, replace, ask_more, reset, choose_option, pca_request_build, ask_what_is, none]
    - index: número do requisito ou opção escolhida (opcional, para choose_option)
    - text: texto complementar (opcional)
    
    Intents especiais:
    - "confirm": usuário confirmou/aceitou (ok, pode, sim, confirmo, aceito, concordo, fechado, segue, pode seguir)
    - "choose_option": usuário escolheu uma opção por número (ex: "1", "2", "3", "opção 2")
    - "pca_request_build": usuário não tem PCA e pede para construir (ex: "não tenho o PCA", "monta um PCA", "faça o PCA")
    - "ask_what_is": usuário pergunta o que é algo (ex: "o que é PCA?", "como faz PCA?")
    
    Respeite a fala do usuário em PT-BR e seja tolerante com variações.
    """
    
    def parse(self, user_text: str) -> dict:
        """
        Parse user intent with fallback to regex patterns for common cases.
        """
        import re
        
        # Fast path: regex-based detection for common patterns
        user_lower = user_text.lower().strip()
        
        # Confirmations: ok, pode, sim, etc.
        if re.match(r'^(ok|pode|sim|s|confirmo|aceito|concordo|fechado|fechou|segue|pode seguir|prosseguir|vamos em frente|pode ser essa msm|parcelar)\.?$', user_lower):
            return {"intent": "confirm", "text": user_text}
        
        # Numbers: "1", "2", "3", etc. (choose option)
        if re.match(r'^\s*(\d+)\s*\.?$', user_lower):
            match = re.match(r'^\s*(\d+)\s*\.?$', user_lower)
            return {"intent": "choose_option", "index": int(match.group(1)), "text": user_text}
        
        # Option choice: "opção 1", "escolho a 2", etc.
        if re.search(r'(op[cç][aã]o|escolho|quero)\s+(\d+)', user_lower):
            match = re.search(r'(\d+)', user_lower)
            if match:
                return {"intent": "choose_option", "index": int(match.group(1)), "text": user_text}
        
        # PCA requests: "não tenho o PCA", "monta um PCA", "faça o PCA", "como faz PCA?"
        pca_patterns = [
            r'n[aã]o tenho.*pca',
            r'monta.*pca',
            r'fa[çz]a.*pca',
            r'construir.*pca',
            r'criar.*pca',
            r'gerar.*pca',
            r'preciso.*pca'
        ]
        if any(re.search(pattern, user_lower) for pattern in pca_patterns):
            return {"intent": "pca_request_build", "text": user_text}
        
        # Questions about PCA or other concepts
        if re.search(r'(o que [eé]|como faz|como [eé]|qual [eé]).*pca', user_lower):
            return {"intent": "ask_what_is", "subject": "PCA", "text": user_text}
        
        # Fallback to LLM for complex cases
        logger.info(f"[GENERATOR] stage=parsing using model={MODEL} temp={TEMP}")
        payload = {
            "model": MODEL,
            "temperature": TEMP,
            "messages": [
                {"role":"system","content":self.INTENT_SCHEMA},
                {"role":"user","content":user_text}
            ],
            "response_format": {"type":"json_object"}
        }
        
        try:
            with httpx.Client(timeout=30) as cli:
                r = cli.post(BASE_URL, headers=HEADERS, json=payload)
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                return __import__("json").loads(content)
        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            return {"intent":"none"}
