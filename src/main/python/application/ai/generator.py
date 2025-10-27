import os
import json
import logging
import re
import traceback
import hashlib
from typing import List, Dict, Any, Protocol, Optional
from config.models import MODEL, TEMP
# from application.ai import prompt_templates

logger = logging.getLogger(__name__)

# Load strict per-stage templates from JSON file (required)
_TEMPLATES_JSON = None
_TPL_PATH = os.path.join(
    os.path.dirname(__file__), 'templates', 'prompt_templates.json'
)

# Map aliases from issue to internal stage names used elsewhere
_STAGE_ALIAS = {
    'quantity_value': 'qty_value',
    'parceling': 'installment',
}

BLOCKED_HEADS = re.compile(
    r"^\s*(\*\*)?\s*(justificativa(?: da contrata[cç][aã]o)?|objetivo)\s*(\*\*)?\s*$",
    re.IGNORECASE | re.MULTILINE
)

def _load_templates_json() -> Dict[str, str]:
    global _TEMPLATES_JSON
    if _TEMPLATES_JSON is not None:
        return _TEMPLATES_JSON
    try:
        with open(_TPL_PATH, 'r', encoding='utf-8') as f:
            _TEMPLATES_JSON = json.load(f)
            return _TEMPLATES_JSON
    except Exception as e:
        logger.error(f"[GEN:MISSING_TEMPLATE:bootstrap] Falha ao carregar JSON de templates: {e}")
        _TEMPLATES_JSON = {}
        return _TEMPLATES_JSON

def _stage_key(stage: str) -> str:
    # Normalize known aliases
    return _STAGE_ALIAS.get(stage, stage)

def strip_blocked_sections(stage: str, text: str) -> str:
    if stage in {"collect_need","suggest_requirements","solution_strategies","pca","legal_norms","quantity_value","parceling","qty_value","installment"}:
        lines = (text or '').splitlines()
        out = []
        skip = False
        for ln in lines:
            if BLOCKED_HEADS.match(ln.strip()):
                skip = True
                continue
            if skip and ln.strip() == "":
                skip = False
                continue
            if not skip:
                out.append(ln)
        text = "\n".join(out).strip()
    return text

# Stage to prompt mapping
STAGE_PROMPTS = {
    "suggest_requirements": "prompt_suggest_requirements",
    "solution_strategies": "prompt_solution_strategies",
    "pca": "prompt_pca",
    "legal_norms": "prompt_legal_norms",
    "qty_value": "prompt_qty_value",
    "installment": "prompt_installment",
    "summary": "prompt_summary",
}

# Banned phrases that indicate onboarding/reintroduction or document sections
BANNED_PHRASES = [
    "vamos começar", "vamos iniciar", "primeiro passo",
    "descrição da necessidade", "1. descrição da necessidade",
    "justificativa da contratação", "justificativa de contratação",
    "justificativas curtas",
    "posso seguir", "posso avançar", "posso continuar",
    "vamos começar pela", "começaremos com", "iniciaremos com",
    "recomendação:", "recomendação final"
]

# Remove bloco "Justificativa da Contratação" e variações (markdown ou texto puro)
JUSTIF_BLOCK_RE = re.compile(
    r"(^\s*(\*\*?\s*)?justificativa\s*(da|de)\s*contrata[cç][aã]o(\s*\*\*)?\s*:?[\r\n]+[\s\S]*?$)",
    re.IGNORECASE | re.MULTILINE
)

# Somente essas chaves podem aparecer por etapa:
STAGE_ALLOWED_KEYS = {
    "suggest_requirements": {"intro", "requirements"},
    "solution_strategies": {"strategies"},
    "pca": {"status", "text"},
    "legal_norms": {"norms"},
    "qty_value": {"items", "methodology"},
    "installment": {"decision", "text"},
    "summary": {"executive_summary"},
}

def _safe_nonempty(text: str, stage: str, client=None, messages: list = None) -> str:
    """
    Ensures the response is not empty. If empty:
    1. Attempts to regenerate once
    2. If still empty, returns a useful fallback
    
    Args:
        text: The response text to check
        stage: Current stage name
        client: OpenAI client for regeneration
        messages: Message history for regeneration
    
    Returns:
        Non-empty text (original, regenerated, or fallback)
    """
    if text and text.strip():
        return text
    
    # First attempt: regenerate
    logger.warning(f"[GEN] empty text at stage={stage}; regenerating once")
    if client and messages:
        try:
            regen = client.chat.completions.create(
                model=MODEL,
                temperature=TEMP,
                messages=[*messages, {"role": "system", "content": "Regenerate with non-empty content. Provide a complete and useful response."}],
                max_tokens=2500
            )
            txt = regen.choices[0].message.content if regen and regen.choices else ""
            if txt and txt.strip():
                logger.info(f"[GEN] Successfully regenerated non-empty response for stage={stage}")
                return txt.strip()
        except Exception as e:
            logger.error(f"[GEN] Error during regeneration: {e}")
    
    # Fallback: return useful default message
    logger.error(f"[GEN] still empty after regen at stage={stage}; returning fallback")
    return (
        "Para não te deixar sem base, segue uma síntese e próximos passos temporários. "
        "Se preferir, me diga e eu detalho mais ou ajusto a direção."
    )

def _normalize_line(s: str) -> str:
    """
    Normalizes a requirement line for deduplication by:
    - Converting to lowercase
    - Removing extra whitespace
    - Removing common punctuation
    
    Args:
        s: The requirement text to normalize
        
    Returns:
        Normalized text string
    """
    # Convert to lowercase and collapse whitespace
    s = re.sub(r'\s+', ' ', s.strip().lower())
    # Remove common punctuation that doesn't affect meaning
    s = re.sub(r'[.;:()\[\]\-]+', '', s)
    return s

def dedupe_requirements(items: list) -> list:
    """
    Removes duplicate requirements based on normalized content hash.
    Preserves original formatting while filtering duplicates.
    
    Args:
        items: List of requirement strings or dicts with 'text' field
        
    Returns:
        Deduplicated list maintaining original format
    """
    seen = set()
    out = []
    for item in items:
        # Extract text from dict or use string directly
        text = item.get('text') if isinstance(item, dict) else str(item)
        
        # Generate hash of normalized text
        h = hashlib.sha1(_normalize_line(text).encode()).hexdigest()
        
        if h not in seen:
            seen.add(h)
            out.append(item)
        else:
            logger.info(f"[DEDUPE] Filtered duplicate requirement: {text[:50]}...")
    
    if len(items) != len(out):
        logger.info(f"[DEDUPE] Removed {len(items) - len(out)} duplicate(s) from {len(items)} requirements")
    
    return out

def _looks_like_onboarding(text: str) -> bool:
    """
    Checks if text contains banned onboarding phrases.
    
    Args:
        text: Text to check for onboarding phrases
        
    Returns:
        True if onboarding phrases detected, False otherwise
    """
    t = (text or "").lower()
    return any(phrase in t for phrase in BANNED_PHRASES)

def _sanitize_banned_text(stage: str, text: str) -> str:
    """
    Removes banned content blocks like "Justificativa da Contratação" from text.
    
    Args:
        stage: Current stage name
        text: Text to sanitize
        
    Returns:
        Sanitized text with banned blocks removed
    """
    if stage not in ["suggest_requirements", "solution_strategies", "pca", "legal_norms"]:
        return text or ""
    
    # Remove explicit justification blocks
    cleaned = JUSTIF_BLOCK_RE.sub("", text or "")
    
    # Remove isolated justification headings
    cleaned = re.sub(r"^\s*\*\*?\s*justificativa[^\r\n]*\r?\n", "", cleaned, flags=re.IGNORECASE|re.MULTILINE)
    
    return cleaned.strip()

def _strip_banned(text: str) -> str:
    """
    Belt-and-suspenders sanitization: removes banned headings from text.
    Used defensively in generator output for collect_need/suggest_requirements stages.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Text with banned headings removed
    """
    if not text:
        return text
    # Remove titles/lines starting with "Justificativa"
    text = re.sub(r"(?im)^\s*\*?\*?\s*justificativa[^\n]*\n?", "", text)
    # Remove heading "Descrição da Necessidade" that sometimes leaks from KB
    text = re.sub(r"(?im)^\s*\*?\*?\s*descri[cç][aã]o da necessidade[^\n]*\n?", "", text)
    return text.strip()

def _prompt_for(stage: str):
    """
    Maps stage to appropriate prompt template.
    
    Args:
        stage: Current stage name
        
    Returns:
        Tuple of (prompt_text, effective_stage)
    """
    if stage == "collect_need":
        # collect_need transitions to suggest_requirements
        return prompt_templates.prompt_templates["prompt_suggest_requirements"], "suggest_requirements"
    
    key = STAGE_PROMPTS.get(stage)
    if not key:
        logger.warning(f"[FLOW] Unknown stage={stage}; defaulting to suggest_requirements")
        return prompt_templates.prompt_templates["prompt_suggest_requirements"], "suggest_requirements"
    
    return prompt_templates.prompt_templates[key], stage

class EtpGenerator(Protocol):
    """Protocol for ETP requirement generators"""
    def suggest_requirements(self, necessity: str) -> List[str]: ...

class FallbackGenerator:
    """
    Gera requisitos iniciais básicos sem depender de serviços externos.
    Usa heurística simples para determinar quantidade (7-12 itens).
    """
    def suggest_requirements(self, necessity: str) -> List[str]:
        base = (necessity or "").strip() or "Objeto não informado"
        # Dynamic list based on simple heuristic (default to medium complexity)
        return [
            f"1. (Obrigatório) Atender à necessidade principal: {base}",
            "2. (Obrigatório) Garantir conformidade com normas técnicas aplicáveis",
            "3. (Obrigatório) Compatibilidade com o ambiente existente",
            "4. (Obrigatório) Documentação técnica completa em português",
            "5. (Obrigatório) Garantia mínima de 12 meses",
            "6. (Obrigatório) Suporte técnico durante vigência contratual",
            "7. (Desejável) Treinamento de equipe técnica",
            "8. (Desejável) Manual de operação e manutenção",
            "9. (Desejável) Atualização tecnológica durante o contrato",
            "10. (Desejável) Relatórios periódicos de desempenho"
        ]

def get_system_prompt(stage: str) -> str:
    """
    Retorna o prompt de sistema base para cada estágio.
    Sistema conversacional sem mensagens pré-definidas ou comandos artificiais.
    """
    # Base identity and objectives - conversational consultant approach
    base = """Identidade
Você é um consultor de ETP que conversa de forma natural. Gere conteúdo original, sem comandos ("adicionar:", "remover:", "editar:") e sem mensagens pré-definidas.

Objetivo
Entender a necessidade e responder como um consultor.
Produzir requisitos mensuráveis (métrica/SLA/evidência/norma) marcando (Obrigatório)/(Desejável), sem incluir blocos de justificativa nas respostas de chat.
Propor 2 a 3 estratégias de contratação aderentes à necessidade (ex.: compra, leasing, outsourcing, comodato, contrato por desempenho, ARP), cada uma com lista de Prós e Contras.
Tratar dados administrativos (PCA, normas, valor, parcelamento) sem travar: se o usuário não souber, registre "Pendente" e siga.

Estilo
Tom humano e claro, sem jargão desnecessário. Não peça que o usuário digite comandos. Aceite confirmações livres; avance quando houver "ok/segue/pode continuar/perfeito". Faça uma pergunta curta apenas se realmente destravar a etapa; do contrário, entregue conteúdo.

Qualidade
Evite generalidades. Sempre que possível use números, unidades e SLAs.
Para aeronaves: referenciar ANAC, disponibilidade mínima (%), SLA por criticidade (ex.: resposta em até 2h para crítico), seguro aeronáutico, rastreabilidade de peças por série, relatórios mensais consolidados.

Restrições
Não explique "como fazer um ETP". Foque na solução técnica/estratégica para a necessidade. Não repita blocos iguais. Nunca devolva resposta em branco."""

    if stage == "collect_need":
        return base + """

Tarefa: Gere requisitos (quantidade dinâmica 7–20 baseada na complexidade) marcando cada um como (Obrigatório) ou (Desejável).
- Baixa complexidade: 7-10 requisitos
- Média complexidade: 10-14 requisitos
- Alta complexidade: 14-20 requisitos
Cada requisito deve incluir métrica/SLA/evidência/norma quando aplicável.
Não inclua blocos de justificativa ou conclusões narrativas; entregue apenas introdução curta e lista numerada."""

    elif stage == "refine":
        return base + """

Tarefa: Refaça a lista completa de requisitos incorporando as preferências do usuário.
Mantenha numeração, marcação (Obrigatório)/(Desejável) e métricas.
Não gere justificativa; apenas traga a nova lista atualizada."""
    
    elif stage == "solution_strategies":
        return base + """

Tarefa: Liste 2 a 3 estratégias de contratação aplicáveis (não etapas de ETP).
Para cada estratégia, forneça JSON com:
{
  "name": "título curto",
  "pros": ["item", "item"],
  "cons": ["item", "item"]
}
Não inclua justificativa, exemplo prático ou campos extras."""
    
    elif stage == "legal_refs":
        return base + """

Tarefa: Traga apenas normas pertinentes ao objeto específico.
Formato: {norma: "...", aplicacao: "..."}"""
    
    elif stage == "summary":
        return base + """

Tarefa: Monte um texto corrido consolidado pronto para prévia do documento."""
    
    return base

def generate_answer(stage: str, history: List[Dict], user_input: str, rag_context: Dict) -> Dict:
    """
    Função unificada de geração por etapa.
    
    Args:
        stage: Estágio atual (collect_need, refine, solution_strategies, legal_refs, summary)
        history: Histórico de mensagens [{role, content}, ...]
        user_input: Entrada atual do usuário
        rag_context: Contexto RAG {chunks: [{text, id, score}...], necessity: str}
    
    Returns:
        Dict estruturado SEM texto pré-definido, com campos conforme a etapa.
        Exemplos:
        - suggest_requirements → {"intro": "...", "requirements": [{"text": "...", "type": "Obrigatório"}, ...]}
        - solution_strategies → {"strategies": [{"name": "...", "pros": [...], "cons": [...]}]}
        - legal_refs → {"intro": "...", "legal": [{"norma": "...", "aplicacao": "..."}, ...]}
        - summary → {"summary": "..."}
    """
    # Load JSON templates and select for stage
    templates = _load_templates_json()
    stage_norm = _stage_key(stage)
    tpl_text = templates.get(stage_norm)
    if tpl_text:
        logger.info(f"[GEN:TEMPLATE stage={stage_norm}] Using JSON template")
    else:
        logger.error(f"[GEN:MISSING_TEMPLATE:{stage_norm}] Template ausente para a etapa")
    
    # Get OpenAI client
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("[GENERATOR] No OpenAI API key available")
        return _fallback_response(stage, user_input, rag_context)
    
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # Use unified model configuration
        logger.info(f"[MODELS] using model={MODEL} temp={TEMP}")
        
        # Build system prompt
        system_prompt = tpl_text if tpl_text else get_system_prompt(stage)
        
        # Build context from RAG
        rag_chunks = rag_context.get('chunks', [])
        rag_text = "\n\n".join([f"[Referência {i+1}] {chunk.get('text', '')}" for i, chunk in enumerate(rag_chunks[:8])])
        logger.info(f"[RAG:USED n={len(rag_chunks[:8])}]")
        
        # Build user prompt: minimal user input + context (when present)
        user_prompt = (user_input or '').strip()
        if rag_text:
            user_prompt = f"{user_prompt}\n\nContexto:\n{rag_text}" if user_prompt else f"Contexto:\n{rag_text}"
        
        # Call OpenAI
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history (last 10 messages for context)
        for msg in history[-10:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        # Add current user input
        messages.append({"role": "user", "content": user_prompt})
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=TEMP,
            max_tokens=2500
        )
        
        content = response.choices[0].message.content if response.choices else ""
        # Ensure non-empty content with regeneration fallback
        content = _safe_nonempty(content, stage, client, messages)
        content = strip_blocked_sections(stage_norm, content.strip())
        
        # Parse response based on stage
        result = _parse_response(stage, content, user_input, rag_context)
        
        # [GUARD] Check for onboarding/banned phrases and retry in strict mode if detected
        result_text = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
        if _looks_like_onboarding(result_text):
            logger.warning(f"[GUARD] Banned content detected in {stage}. Retrying strict.")
            
            # Add strict guard to system prompt
            strict_guard = "\n\nMODO ESTRITO ATIVADO. NÃO insira textos de abertura, 'Descrição da Necessidade' ou 'Justificativa da Contratação'. Gere somente o bloco desta etapa seguindo o JSON indicado."
            strict_system_prompt = system_prompt + strict_guard
            
            # Rebuild messages with strict mode
            strict_messages = [{"role": "system", "content": strict_system_prompt}]
            for msg in history[-10:]:
                strict_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            strict_messages.append({"role": "user", "content": user_prompt})
            
            # Retry with strict mode
            retry_response = client.chat.completions.create(
                model=MODEL,
                messages=strict_messages,
                temperature=TEMP,
                max_tokens=2500
            )
            
            retry_content = retry_response.choices[0].message.content if retry_response.choices else ""
            retry_content = _safe_nonempty(retry_content, stage, client, strict_messages)
            retry_content = strip_blocked_sections(stage_norm, retry_content.strip())
            
            # Re-parse with retry content
            result = _parse_response(stage, retry_content, user_input, rag_context)
            logger.info(f"[GUARD] Retry completed for stage={stage}")
        
        # Validate and apply fallback if needed
        result = _validate_and_fix(stage, result, user_input, rag_context, client, MODEL, system_prompt, messages)
        
        # BLOQUEIO: Garantir payload mínimo antes de retornar
        necessity = rag_context.get('necessity', user_input)
        result = _ensure_min_payload(result, stage, necessity)
        
        # Post-process to remove command patterns and check for repetition
        result = _post_process_response(result, stage)
        
        return result
        
    except Exception as e:
        logger.error(f"[GENERATOR] Error in generate_answer: {e}")
        logger.error(traceback.format_exc())
        return _fallback_response(stage, user_input, rag_context)

def _build_user_prompt(stage: str, user_input: str, rag_text: str, rag_context: Dict) -> str:
    """Constrói o prompt do usuário baseado no estágio"""
    
    necessity = rag_context.get('necessity', user_input)
    
    if stage == "collect_need":
        strict_note = ""
        if rag_context.get("strict_mode") or rag_context.get("no_questions"):
            strict_note = """
Regras obrigatórias anti-perguntas:
- Não faça perguntas de nenhum tipo.
- Não use frases interrogativas.
- Cada item precisa começar com número e ponto (ex.: "1. ...").
- Cada item deve conter uma obrigação verificável e terminar com (Obrigatório) ou (Desejável).
"""
        return f"""Necessidade informada pelo usuário: {user_input}

Contexto RAG (exemplos de requisitos similares):
{rag_text if rag_text else "Nenhum contexto disponível."}

Gere uma lista numerada de requisitos técnicos e operacionais, sem perguntas e sem solicitar informações.
Cada requisito deve seguir: obrigação clara + métrica mínima + forma de verificação.

{strict_note}

Formato de saída obrigatório em JSON:
{{
  "intro": "parágrafo curto de contexto como consultor (2-4 linhas), sem perguntar nada",
  "requirements": [
    {{"text": "1. requisito...", "type": "Obrigatório"}},
    {{"text": "2. requisito...", "type": "Desejável"}}
  ]
}}
"""

    elif stage == "refine":
        previous_requirements = rag_context.get('requirements', [])
        reqs_text = "\n".join(previous_requirements) if previous_requirements else "Nenhum requisito anterior."
        
        return f"""Necessidade: {necessity}

Requisitos anteriores:
{reqs_text}

Nova informação do usuário: {user_input}

Contexto RAG:
{rag_text if rag_text else "Nenhum contexto disponível."}

Refine os requisitos integrando a nova informação do usuário. Re-emita a lista completa numerada.
Mantenha a marcação (Obrigatório)/(Desejável) quando aplicável.

Retorne em formato JSON:
{{
  "intro": "explicação breve das mudanças (2-4 linhas)",
  "requirements": [
    {{"text": "1. requisito atualizado um", "type": "Obrigatório"}},
    {{"text": "2. requisito atualizado dois", "type": "Desejável"}}
  ]
}}"""

    elif stage == "solution_strategies":
        requirements = rag_context.get('requirements', [])
        reqs_text = "\n".join(requirements[:10]) if requirements else "Requisitos não disponíveis."
        
        return f"""Necessidade: {necessity}

Requisitos definidos (primeiros 10):
{reqs_text}

Contexto RAG:
{rag_text if rag_text else "Nenhum contexto disponível."}

Proponha APENAS 2–3 estratégias de contratação coerentes com a necessidade e os requisitos aprovados.
Para cada estratégia, retorne exclusivamente: name, pros (bullets curtos), cons (bullets curtos).

PROIBIDO nesta etapa:
- "Justificativa da Contratação", "justificativas curtas", qualquer parágrafo narrativo
- "recomendação", "recomendação final"
- Textos de abertura ou onboarding

Exemplos de estratégias: compra direta, locação, comodato, outsourcing, leasing operacional, ata de registro de preços, contrato por desempenho.

Retorne SOMENTE este JSON (sem intro, sem recommendation):
{{
  "strategies": [
    {{
      "name": "Nome da estratégia",
      "pros": ["pró 1", "pró 2"],
      "cons": ["contra 1", "contra 2"]
    }}
  ]
}}"""

    elif stage == "legal_refs":
        return f"""Necessidade: {necessity}

Contexto RAG (normas e referências):
{rag_text if rag_text else "Nenhum contexto disponível."}

Liste apenas normas pertinentes ao objeto da contratação.
Sempre inclua Lei 14.133/2021 (nova lei de licitações).
Adicione normas setoriais quando aplicáveis (ex.: ANATEL para telecom, ANAC para aviação, etc.).
NÃO inclua NRs aleatórias fora de contexto.

Retorne em formato JSON:
{{
  "intro": "parágrafo curto sobre as normas aplicáveis",
  "legal": [
    {{"norma": "Lei 14.133/2021", "aplicacao": "Licitações e contratos administrativos"}},
    {{"norma": "Norma setorial", "aplicacao": "Aplicação específica"}}
  ]
}}"""

    elif stage == "summary":
        requirements = rag_context.get('requirements', [])
        strategies = rag_context.get('strategies', [])
        legal = rag_context.get('legal', [])
        
        reqs_text = "\n".join(requirements) if requirements else "Requisitos não disponíveis."
        strat_text = "\n".join([f"- {s.get('titulo', '')}" for s in strategies]) if strategies else "Estratégias não definidas."
        legal_text = "\n".join([f"- {l.get('norma', '')}" for l in legal]) if legal else "Normas não definidas."
        
        return f"""Necessidade: {necessity}

Requisitos finais:
{reqs_text}

Estratégias escolhidas:
{strat_text}

Normas aplicáveis:
{legal_text}

Contexto RAG:
{rag_text if rag_text else "Nenhum contexto disponível."}

Consolide todas as informações em um texto contínuo, profissional, pronto para uso como prévia do ETP.
Não peça confirmação, não use frases padrão. Apenas consolide os dados de forma clara e estruturada.

Retorne em formato JSON:
{{
  "summary": "texto consolidado pronto para prévia, em parágrafos corridos"
}}"""

    return user_input

def _restrict_keys(stage: str, data: dict) -> dict:
    """
    Restricts the keys in a response dict to only those allowed for the stage.
    
    Args:
        stage: Current stage name
        data: Response dictionary to filter
        
    Returns:
        Filtered dictionary with only allowed keys for the stage
    """
    if not isinstance(data, dict):
        return data
    
    allowed = STAGE_ALLOWED_KEYS.get(stage, set())
    if not allowed:
        # If no restrictions defined for stage, return as-is
        return data
    
    filtered = {k: v for k, v in data.items() if k in allowed}
    
    # Log if keys were filtered out
    removed = set(data.keys()) - set(filtered.keys())
    if removed:
        logger.info(f"[RESTRICT] Filtered out keys for stage={stage}: {removed}")
    
    return filtered

def _parse_response(stage: str, content: str, user_input: str, rag_context: Dict) -> Dict:
    """Parse a resposta do modelo baseado no estágio"""
    
    try:
        # Try to extract JSON
        if '{' in content:
            json_start = content.index('{')
            json_end = content.rindex('}') + 1
            json_str = content[json_start:json_end]
            result = json.loads(json_str)
            # Apply key filtering to enforce stage schema
            result = _restrict_keys(stage, result)
            if isinstance(result, dict):
                result.pop('justification', None)
            return result
        else:
            # No JSON found, try to extract from text
            result = _extract_from_text(stage, content)
            result = _restrict_keys(stage, result)
            if isinstance(result, dict):
                result.pop('justification', None)
            return result
    
    except Exception as e:
        logger.warning(f"[GENERATOR] Failed to parse JSON, extracting from text: {e}")
        result = _extract_from_text(stage, content)
        result = _restrict_keys(stage, result)
        if isinstance(result, dict):
            result.pop('justification', None)
        return result

def _extract_from_text(stage: str, content: str) -> Dict:
    """Extrai informação estruturada de texto não-JSON"""
    
    if stage in ["collect_need", "refine", "suggest_requirements"]:
        # Extract numbered requirements ONLY - no intro or justification
        lines = content.split('\n')
        requirements = []
        
        for line in lines:
            stripped = line.strip()
            # Check if line starts with number
            if stripped and (stripped[0].isdigit() and '.' in stripped[:5]):
                requirements.append(stripped)
        
        # Helper function to detect questions
        def _looks_like_question(s: str) -> bool:
            s_low = s.lower()
            if "?" in s_low:
                return True
            starters = ("qual", "quais", "existe", "há ", "ha ", "como", "quando", "onde", "por que", "porque", "por quê", "por que")
            return any(s_low.strip().startswith(x) for x in starters)
        
        # Filter out questions
        requirements = [r for r in requirements if not _looks_like_question(r)]
        
        # Normalize numbering: ensure "N. " format at beginning
        norm = []
        n = 1
        for r in requirements:
            r_strip = r.strip()
            if not re.match(r"^\d+\.\s", r_strip):
                r_strip = f"{n}. {r_strip}"
            norm.append(r_strip)
            n += 1
        
        requirements = norm
        
        # Ensure O/D tags (Obrigatório/Desejável)
        def _ensure_od_tag(s: str) -> str:
            s_low = s.lower()
            if "(obrigatório)" in s_low or "(desejável)" in s_low:
                return s
            # Heurística simples: presença de verbos fortes indica obrigatório
            if any(x in s_low for x in ["deve", "garantir", "assegurar", "manter", "comprovar"]):
                return s + " (Obrigatório)"
            return s + " (Desejável)"
        
        requirements = [_ensure_od_tag(r) for r in requirements]

        def _to_requirement_dict(raw: str) -> Dict[str, str]:
            text = raw.strip()
            req_type = ''
            # Capture trailing type marker
            trailing_match = re.search(r'\((Obrigatório|Desejável)\)\s*$', text, re.IGNORECASE)
            if trailing_match:
                req_type = trailing_match.group(1).title()
                text = re.sub(r'\((Obrigatório|Desejável)\)\s*$', '', text, flags=re.IGNORECASE).strip()
            # Remove leading numbering
            text = re.sub(r'^\s*\d+[\.)]\s*', '', text)
            return {
                'text': text.strip(),
                'type': req_type
            }

        # If requirements list is too short after filtering, signal failure
        if len(requirements) < 5:
            return {
                "requirements": []
            }

        structured = [_to_requirement_dict(r) for r in requirements if r.strip()]
        return {
            "requirements": structured if structured else _get_default_requirements(stage, content)
        }
    
    elif stage == "solution_strategies":
        # Try to extract strategies from text - return minimal fallback
        # NO intro field - only stage-specific data
        return {
            "strategies": [
                {
                    "name": "Compra direta",
                    "pros": ["Propriedade definitiva", "Sem custos recorrentes"],
                    "cons": ["Alto investimento inicial", "Obsolescência"]
                }
            ]
        }
    
    elif stage == "legal_refs":
        # NO intro field - only stage-specific data
        return {
            "legal": [
                {"norma": "Lei 14.133/2021", "aplicacao": "Licitações e contratos administrativos"}
            ]
        }
    
    elif stage == "summary":
        return {
            "summary": content
        }
    
    return {}

def _get_default_requirements(stage: str, necessity: str) -> List[Dict[str, str]]:
    """Gera requisitos padrão quando o modelo falha"""
    base = necessity[:50] if necessity else "contratação"
    defaults = [
        (f"Atender à necessidade de {base} conforme especificações técnicas", "Obrigatório"),
        ("Garantir conformidade com Lei 14.133/2021 e normas aplicáveis", "Obrigatório"),
        ("Fornecedor com experiência mínima de 2 anos no ramo", "Obrigatório"),
        ("Garantia mínima de 12 meses contra defeitos de fabricação", "Obrigatório"),
        ("Suporte técnico durante toda a vigência contratual", "Obrigatório"),
        ("Treinamento de equipe técnica com certificação", "Desejável"),
        ("Documentação técnica completa em português", "Obrigatório"),
        ("Compatibilidade com infraestrutura existente", "Obrigatório"),
        ("Prazo de entrega máximo de 60 dias corridos", "Obrigatório"),
        ("Assistência técnica em até 48 horas úteis", "Obrigatório")
    ]
    structured = []
    for text, req_type in defaults:
        structured.append({
            'text': text,
            'type': req_type
        })
    return structured

def _validate_and_fix(stage: str, result: Dict, user_input: str, rag_context: Dict, 
                      client, model: str, system_prompt: str, messages: List[Dict]) -> Dict:
    """
    Valida requisitos e aplica correções se necessário.
    Política anti-lista-vazia e validação de qualidade.
    """
    
    if stage in ["collect_need", "refine", "suggest_requirements"]:
        raw_requirements = result.get('requirements', []) or []

        normalized = []
        for item in raw_requirements:
            if isinstance(item, dict):
                text = (item.get('text') or '').strip()
                req_type = (item.get('type') or '').strip()
            else:
                text = str(item or '').strip()
                req_type = ''
            if not text:
                continue
            if '?' in text:
                text = text.replace('?', '').strip()
            normalized.append({
                'text': text,
                'type': req_type.title() if req_type else ''
            })

        valid = True
        reasons = []

        if len(normalized) < 8:
            valid = False
            reasons.append("menos de 8 requisitos")

        if normalized:
            for req in normalized:
                text = req.get('text', '')
                if not text:
                    valid = False
                    reasons.append("requisito vazio")
                    break

        # If validation failed, try to regenerate
        if not valid:
            logger.warning(f"[VALIDATION:REGEN triggered] Reasons: {', '.join(reasons)}")

            # Add corrective prompt
            corrective_prompt = f"""CORREÇÃO NECESSÁRIA: A resposta anterior falhou na validação ({', '.join(reasons)}).

Retorne de 8 a 15 requisitos numerados, específicos e verificáveis, sem perguntas.
Cada requisito deve ter formato: "N. [Obrigação clara] + [Métrica/valor mínimo] + [Forma de verificação]"
Inclua pelo menos um item de SLA, um de conformidade regulatória, um de garantia/suporte e um de relatório/monitoramento.
Marque (Obrigatório) ou (Desejável) quando aplicável.

Retorne APENAS JSON válido com requisitos, SEM intro extra:
{{
  "intro": "parágrafo curto",
  "requirements": [{{"text": "1. requisito um com métrica", "type": "Obrigatório"}}, {{"text": "2. requisito dois", "type": "Desejável"}}]
}}"""

            try:
                messages_copy = messages.copy()
                messages_copy.append({"role": "user", "content": corrective_prompt})
                
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages_copy,
                    temperature=TEMP,
                    max_tokens=2500
                )
                
                content = response.choices[0].message.content.strip()
                result = _parse_response(stage, content, user_input, rag_context)
                
                # If still invalid, use fallback
                regenerated = result.get('requirements') or []
                if not regenerated or len(regenerated) < 8:
                    result['requirements'] = _get_default_requirements(stage, rag_context.get('necessity', user_input))
                    if 'intro' not in result or not result['intro']:
                        result['intro'] = ""

            except Exception as e:
                logger.error(f"[GENERATOR] Regen failed: {e}")
                result['requirements'] = _get_default_requirements(stage, rag_context.get('necessity', user_input))
                if 'intro' not in result or not result['intro']:
                    result['intro'] = ""

        else:
            result['requirements'] = normalized

    return result

def _fallback_requirements_min(necessity: str) -> List[Dict[str, str]]:
    """Gera pelo menos 8-12 requisitos objetivos quando tudo falhar"""
    base = necessity[:60] if necessity else "contratação"
    defaults = [
        (f"Atender plenamente à necessidade de {base} conforme especificações técnicas e requisitos funcionais mínimos", "Obrigatório"),
        ("Garantir conformidade com Lei 14.133/2021, legislação aplicável e normas técnicas do setor", "Obrigatório"),
        ("Fornecedor com experiência comprovada mínima de 2 anos em contratos similares", "Obrigatório"),
        ("Disponibilidade mínima de 99,5% mensal, com penalidades proporcionais por descumprimento", "Obrigatório"),
        ("Garantia contra defeitos de fabricação/execução pelo prazo mínimo de 12 meses", "Obrigatório"),
        ("Suporte técnico especializado em até 24 horas úteis, com SLA documentado", "Obrigatório"),
        ("Treinamento de equipe técnica com certificação reconhecida e material didático", "Desejável"),
        ("Documentação técnica completa em português brasileiro, incluindo manuais operacionais", "Obrigatório"),
        ("Compatibilidade técnica com infraestrutura e sistemas já existentes", "Obrigatório"),
        ("Relatórios mensais de desempenho, monitoramento e indicadores de qualidade", "Obrigatório"),
        ("Prazo de entrega ou início de execução em até 60 dias corridos após assinatura", "Obrigatório"),
        ("Conformidade com LGPD quando houver tratamento de dados pessoais", "Obrigatório")
    ]
    return [{'text': text, 'type': req_type} for text, req_type in defaults]

def _fallback_strategies(necessity: str) -> List[Dict]:
    """Gera 2-3 estratégias quando o LLM falha - somente name/when/pros/cons"""
    base = necessity[:50] if necessity else "bem ou serviço"
    strategies = [
        {
            "name": "Contrato por Desempenho (Performance-Based)",
            "pros": ["Pagamento vinculado a resultados", "Incentivo à qualidade", "Redução de riscos operacionais"],
            "cons": ["Requer métricas bem definidas", "Dificuldade na mensuração inicial"]
        },
        {
            "name": "Outsourcing Integral",
            "pros": ["Transferência total da operação", "Equipe dedicada", "Foco no core business"],
            "cons": ["Dependência do fornecedor", "Custo recorrente mais alto"]
        },
        {
            "name": "Locação com Opção de Compra",
            "pros": ["Menor investimento inicial", "Flexibilidade contratual", "Possibilidade de aquisição futura"],
            "cons": ["Custo total pode ser maior", "Limitações contratuais"]
        }
    ]
    for strat in strategies:
        strat['titulo'] = strat['name']
        strat['vantagens'] = strat['pros']
        strat['riscos'] = strat['cons']
    return strategies

def _post_process_response(resp: Dict, stage: str, prev_content: str = "") -> Dict:
    """
    Post-processing to remove command patterns and detect repetition.
    As per issue requirements:
    - Remove any "adicionar:|remover:|editar:" patterns
    - Check for repeated content (similarity > 85%)
    - Ensure non-empty responses
    """
    from difflib import SequenceMatcher
    
    # Check all text fields for command patterns
    command_pattern = r'\b(adicionar:|remover:|editar:)\b'
    
    for key in ['intro']:
        if key in resp and resp[key]:
            text = resp[key]
            if re.search(command_pattern, text, re.I):
                # Remove command patterns
                text = re.sub(command_pattern, '', text, flags=re.I)
                text = ' '.join(text.split())  # Clean up whitespace
                resp[key] = text
                logger.warning(f"[POST_PROCESS] Removed command pattern from {key}")

    # Check requirements for command patterns
    if 'requirements' in resp and resp['requirements']:
        cleaned_reqs = []
        for req in resp['requirements']:
            if isinstance(req, dict):
                text = req.get('text') or ''
                if re.search(command_pattern, text, re.I):
                    text = re.sub(command_pattern, '', text, flags=re.I)
                    text = ' '.join(text.split())
                    req['text'] = text
                cleaned_reqs.append(req)
            else:
                if re.search(command_pattern, str(req), re.I):
                    cleaned = re.sub(command_pattern, '', str(req), flags=re.I)
                    cleaned = ' '.join(cleaned.split())
                    cleaned_reqs.append(cleaned)
                else:
                    cleaned_reqs.append(req)
        resp['requirements'] = cleaned_reqs
    
    # Check for repetition if prev_content provided
    if prev_content and 'intro' in resp and resp['intro']:
        similarity = SequenceMatcher(None, prev_content.lower(), resp['intro'].lower()).ratio()
        if similarity > 0.85:
            logger.warning(f"[POST_PROCESS] High similarity detected ({similarity:.2f}), regenerating with variation")
            # Add variation marker to force different response
            resp['_needs_variation'] = True
    
    return resp

def _ensure_min_payload(resp: Dict, stage: str, necessity: str) -> Dict:
    """
    Garantia mínima: nunca devolver payload vazio.
    Aplica sanity check para cada estágio crítico.
    """
    if stage in {"collect_need", "refine", "suggest_requirements"}:
        # Intro vazio
        if not resp.get("intro") or resp.get("intro").strip() == "":
            resp["intro"] = f"Entendi sua necessidade: {necessity[:80]}. Vou propor requisitos objetivos e verificáveis alinhados a segurança, disponibilidade e conformidade."

        # Requirements vazio ou insuficiente
        raw_requirements = resp.get("requirements") or []

        normalized = []
        for item in raw_requirements:
            if isinstance(item, dict):
                text = (item.get('text') or '').strip()
                req_type = (item.get('type') or '').strip()
            else:
                text = str(item or '').strip()
                req_type = ''
            if not text:
                continue
            # Detect embedded type markers
            trailing = re.search(r'\((Obrigatório|Desejável)\)\s*$', text, re.IGNORECASE)
            if trailing and not req_type:
                req_type = trailing.group(1).title()
                text = re.sub(r'\((Obrigatório|Desejável)\)\s*$', '', text, flags=re.IGNORECASE).strip()
            normalized.append({
                'text': text,
                'type': req_type.title() if req_type else ''
            })

        if len(normalized) < 8:
            logger.warning(f"[ENSURE_MIN] Requirements vazio/insuficiente ({len(normalized)}), aplicando fallback")
            normalized = _fallback_requirements_min(necessity)

        resp["requirements"] = normalized

    elif stage == "solution_strategies":
        # Strategies vazio
        strategies = resp.get("strategies") or []
        if not strategies or len(strategies) < 2:
            logger.warning(f"[ENSURE_MIN] Strategies vazio/insuficiente ({len(strategies)}), aplicando fallback")
            resp["strategies"] = _fallback_strategies(necessity)
        
        # NO intro field for solution_strategies - strict schema enforcement
    
    elif stage == "legal_refs":
        legal = resp.get("legal") or []
        if not legal:
            logger.warning(f"[ENSURE_MIN] Legal refs vazio, aplicando fallback mínimo")
            resp["legal"] = [
                {"norma": "Lei 14.133/2021", "aplicacao": "Nova Lei de Licitações e Contratos Administrativos"}
            ]
        if not resp.get("intro"):
            resp["intro"] = "Base legal aplicável à contratação:"
    
    elif stage == "summary":
        if not resp.get("summary") or resp.get("summary").strip() == "":
            resp["summary"] = f"Necessidade: {necessity}\n\nRequisitos e estratégias consolidados estão em elaboração."
    
    return resp

def _fallback_response(stage: str, user_input: str, rag_context: Dict) -> Dict:
    """Resposta de fallback quando há erro"""
    necessity = rag_context.get('necessity', user_input)
    
    if stage in ["collect_need", "refine", "suggest_requirements"]:
        resp = {
            "intro": "",
            "requirements": _get_default_requirements(stage, necessity)
        }
        return _ensure_min_payload(resp, stage, necessity)
    
    elif stage == "solution_strategies":
        resp = {
            "strategies": _fallback_strategies(necessity)
        }
        return _ensure_min_payload(resp, stage, necessity)
    
    elif stage == "legal_refs":
        resp = {
            "intro": "",
            "legal": [
                {"norma": "Lei 14.133/2021", "aplicacao": "Nova Lei de Licitações e Contratos Administrativos"}
            ]
        }
        return _ensure_min_payload(resp, stage, necessity)
    
    elif stage == "summary":
        resp = {
            "summary": f"Necessidade: {necessity}\n\nRequisitos e estratégias estão sendo consolidados."
        }
        return _ensure_min_payload(resp, stage, necessity)
    
    return {"error": "Estágio não suportado"}

# ============================================================================
# Legacy API compatibility
# ============================================================================

class OpenAIGenerator:
    """
    Gerador de conteúdo ETP usando OpenAI API.
    ATENÇÃO: Esta classe está DEPRECATED e mantida apenas para compatibilidade.
    Use a função generate_answer() diretamente.
    """
    def __init__(self, openai_client, model: str = "gpt-4o-mini"):
        if not openai_client:
            raise RuntimeError("OpenAI client não fornecido")
        self.client = openai_client
        self.model = model
        logger.info(f"[GENERATOR] Initialized with model {model}")

    def generate(self, stage: str, necessity: str, context: List[Dict] = None, 
                 data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Legacy generate method - redirects to new generate_answer()
        """
        context = context or []
        data = data or {}
        
        # Convert to new format
        history = []
        rag_context = {
            'chunks': context,
            'necessity': necessity,
            'requirements': data.get('requirements', []),
            'strategies': data.get('strategies', []),
            'legal': data.get('legal', [])
        }
        
        # Map old stage names to new
        stage_map = {
            'collect_need': 'collect_need',
            'suggest_requirements': 'collect_need',
            'refine_requirements': 'refine',
            'refine_requirements_assist': 'refine',
            'solution_path': 'solution_strategies',
            'legal_norms': 'legal_refs',
            'summary': 'summary',
            'preview': 'summary'
        }
        
        new_stage = stage_map.get(stage, stage)
        
        result = generate_answer(new_stage, history, necessity, rag_context)
        
        # Convert back to legacy format
        legacy_result = {
            'message': result.get('intro', ''),
            'requirements': result.get('requirements', []),
            'next_stage': self._get_next_stage(stage),
            'ask': None
        }
        
        if 'strategies' in result:
            legacy_result['steps'] = [s.get('titulo', '') for s in result.get('strategies', [])]
            legacy_result['strategies'] = result.get('strategies', [])
        
        if 'legal' in result:
            legacy_result['legal'] = result.get('legal', [])
        
        if 'summary' in result:
            legacy_result['summary'] = result.get('summary', '')
        
        return legacy_result
    
    def _get_next_stage(self, current_stage: str) -> str:
        """Get next stage in flow"""
        stage_order = [
            'collect_need',
            'suggest_requirements',
            'refine_requirements_assist',
            'solution_strategies',
            'pca',
            'legal_norms',
            'qty_value',
            'installment',
            'summary',
            'preview'
        ]
        
        try:
            idx = stage_order.index(current_stage)
            if idx < len(stage_order) - 1:
                return stage_order[idx + 1]
        except ValueError:
            pass
        
        return None

def get_etp_generator(openai_client=None, fallback: bool = True):
    """
    Factory function para obter gerador de ETP.
    Retorna OpenAIGenerator se cliente disponível, senão FallbackGenerator.
    """
    if openai_client:
        try:
            return OpenAIGenerator(openai_client)
        except Exception as e:
            logger.error(f"[GENERATOR] Failed to create OpenAIGenerator: {e}")
            if fallback:
                logger.warning("[GENERATOR] Using FallbackGenerator")
                return FallbackGenerator()
            raise
    else:
        if fallback:
            logger.warning("[GENERATOR] No OpenAI client, using FallbackGenerator")
            return FallbackGenerator()
        raise RuntimeError("OpenAI client não fornecido e fallback desabilitado")
