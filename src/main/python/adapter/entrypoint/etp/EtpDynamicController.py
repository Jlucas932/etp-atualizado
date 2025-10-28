import os
import json
import uuid
import tempfile
import logging
import traceback
from datetime import datetime
from typing import Any
from flask import Blueprint, request, jsonify, send_file, g, session, Response, stream_with_context
from flask_cors import cross_origin
import re
import unicodedata

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpOrm import EtpSession, EtpDocument
from domain.dto.EtpDto import DocumentAnalysis, KnowledgeBase, ChatSession, EtpTemplate
from domain.dto.ConversationModels import Conversation, Message
from domain.repositories.ConversationRepository import ConversationRepo, MessageRepo
from domain.usecase.etp.verify_federal import resolve_lexml, summarize_for_user, parse_legal_norm_string
from application.config.LimiterConfig import limiter
from rag.retrieval import search_requirements
from domain.services.etp_dynamic import init_etp_dynamic
from domain.usecase.etp.legal_norms_interpreter import parse_legal_norms
from domain.usecase.etp.price_research_interpreter import parse_price_research
from domain.usecase.etp.legal_basis_interpreter import parse_legal_basis
from domain.usecase.etp.document_composer import compose_etp_document
from domain.usecase.etp.html_renderer import render_etp_html
from application.ai.generator import (
    get_etp_generator,
    FallbackGenerator,
    dedupe_requirements,
    generate_requirements_strict,
    generate_strategies_strict,
)
from application.ai.sanitize import keep_only_expected, is_blocked_text
from application.ai.hybrid_models import OpenAIChatConsultive, OpenAIFinalWriter, OpenAIIntentParser
from application.ai import intents
from application.services.preview_builder import build_preview, build_etp_markdown
from domain.usecase.etp.state_machine import (
    is_user_confirmed, validate_state_transition, can_generate_etp,
    handle_other_intent, handle_http_error, validate_generator_exists,
    get_next_state_after_suggestion
)
from domain.usecase.etp import conversational_state_machine as csm
from io import BytesIO
from docx import Document as DocxDocument
from application.etp import EtpParts, assemble_sections, ChatStage

etp_dynamic_bp = Blueprint('etp_dynamic', __name__)

# Module-level variables for lazy initialization
_etp_generator = None
_prompt_generator = None  
_rag_system = None
_initialized = False

# Simple generator for requirements (with fallback)
_simple_generator = None
_openai_client = None

# Hybrid model generators
chat_gen   = OpenAIChatConsultive()
final_gen  = OpenAIFinalWriter()
intent_par = OpenAIIntentParser()

# ===================== STAGE MACHINE CONFIGURATION =====================
# Deterministic FSM: 9-stage conversational flow without intermediate refinement
STAGE_ORDER = [
    "collect_need",
    "suggest_requirements",
    "solution_strategies",
    "pca",
    "legal_norms",
    "qty_value",
    "installment",
    "summary",
    "preview"
]

# Stage transition map
NEXT_STAGE = {stage: STAGE_ORDER[i+1] for i, stage in enumerate(STAGE_ORDER[:-1])}

ALLOWED_STEPS = [
    "collect_need",
    "suggest_requirements",
    "solution_strategies",
    "pca_check",
    "legal_norms",
    "estimation",
    "parcelamento",
    "finalize",
]


def _set_stage(session: EtpSession, next_state: str) -> None:
    assert next_state in ALLOWED_STEPS, f"Invalid conversation stage: {next_state}"
    session.conversation_stage = next_state
    session.updated_at = datetime.utcnow()


def _persist_structured_requirements(session: EtpSession, requisitos: list[dict]) -> list[dict]:
    sanitized: list[dict] = []
    for idx, raw in enumerate(requisitos or [], start=1):
        if not isinstance(raw, dict):
            continue
        titulo = (raw.get('titulo') or raw.get('descricao') or '').strip()
        descricao = (raw.get('descricao') or raw.get('titulo') or '').strip()
        criticidade = (raw.get('criticidade') or 'Desejável').strip().title()
        sla = (raw.get('sla') or '').strip()

        if not descricao or is_blocked_text(titulo) or is_blocked_text(descricao):
            continue

        criticidade = 'Obrigatório' if criticidade.lower().startswith('ob') else 'Desejável'
        entry = {
            'id': f'R{idx}',
            'titulo': titulo or f'Requisito {idx}',
            'descricao': descricao,
            'criticidade': criticidade,
        }
        if sla:
            entry['sla'] = sla
        sanitized.append(entry)

    session.set_requirements(sanitized)
    return sanitized

logger = logging.getLogger(__name__)

# Regex for detecting "Justificativa da Contratação" headings
JUSTIF_HDR_RE = re.compile(
    r"(?im)^\s*(\*\*\s*)?justificativa\s*(da|de)\s*contrata[cç][aã]o[:\s]*\**\s*$"
)

def _get_openai_client():
    """Get or create OpenAI client"""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            import openai
            _openai_client = openai.OpenAI(api_key=api_key)
    return _openai_client

def get_llm_client():
    """Helper to ensure llm_client is always available (never None)"""
    client = _get_openai_client()
    if client is None:
        logger.warning("[CLIENT] OpenAI client not initialized, creating fallback")
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            import openai
            client = openai.OpenAI(api_key=api_key)
    return client

def get_model_name():
    """Get standardized model name from environment"""
    return os.getenv("OPENAI_MODEL", "gpt-4.1")

def _get_simple_generator():
    """Get or create the simple requirements generator with automatic fallback"""
    global _simple_generator
    if _simple_generator is None:
        openai_client = _get_openai_client()
        _simple_generator = get_etp_generator(openai_client=openai_client)
    return _simple_generator

def get_current_user_id():
    """Get current user ID from flask.g, session, or request headers, fallback to 'anonymous'"""
    # Check if user_id is in flask.g (set by auth middleware)
    if hasattr(g, 'user_id') and g.user_id:
        return str(g.user_id)
    
    # Check X-User-Id header
    user_id = request.headers.get('X-User-Id')
    if user_id:
        return str(user_id)
    
    # Check Flask session (login.html uses /api/auth/login with cookie)
    if 'user_id' in session:
        return str(session['user_id'])
    
    # Fallback to anonymous for development
    return 'anonymous'

# ===================== Helpers consultivos =====================
CONFIRM_RE = re.compile(r'\b(ok|ok\.?|pode seguir|segue|prosseguir|manter|aceito|concordo|fechou|confirmo|confirmar|fechado|vamos em frente)\b', re.I)
YES_RE = re.compile(r'\b(sim|s|claro|ok|certo|pode|pode sim)\b', re.I)
NO_RE = re.compile(r'\b(n[aã]o|nao|n)\b', re.I)
UNCERTAIN_RE = re.compile(r'\b(n[aã]o sei|nao sei|talvez|tanto faz|indefinido|a definir|a confirmar)\b', re.I)

def _normalize(txt: str) -> str:
    if not txt:
        return ''
    s = txt.strip()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s

def _is_confirm(txt: str) -> bool:
    return bool(CONFIRM_RE.search(txt or ''))

def _is_uncertain(txt: str) -> bool:
    t = _normalize(txt).lower()
    return not t or bool(UNCERTAIN_RE.search(t)) or t in {'nao sei','n sei','?','nada','-'}

def _yes(txt: str) -> bool:
    return bool(YES_RE.search(txt or ''))

def _no(txt: str) -> bool:
    # tolera typos tipo "naoi", "naoii"
    t = _normalize(txt).lower()
    return bool(NO_RE.search(t)) or t.startswith('nao')

def _pick_numbers(txt: str, max_n: int) -> list:
    """Extrai seleções do tipo '1 e 3', '2,4', '1-2'."""
    t = _normalize(txt).lower()
    picks = set()
    for a,b in re.findall(r'(\d+)\s*-\s*(\d+)', t):
        a,b = int(a), int(b)
        for k in range(min(a,b), max(a,b)+1):
            if 1 <= k <= max_n: picks.add(k)
    for n in re.findall(r'\b(\d+)\b', t):
        k = int(n)
        if 1 <= k <= max_n: picks.add(k)
    return sorted(picks)

def _any_in(txt: str, options: list) -> str:
    """Detecta uma opção por palavra-chave dentro do texto."""
    if not txt: return None
    t = _normalize(txt).lower()
    for op in options:
        k = _normalize(op).lower()
        if k in t:
            return op
    return None

def _is_free_confirm(text: str) -> bool:
    """
    Check if user input is a free confirmation (ok, pode seguir, etc.)
    Returns True if it's a simple confirmation without actual content.
    """
    if not text:
        return False
    t = text.strip().lower()
    return bool(re.match(r'^(ok(ay)?|pode(\s)?(seguir|continuar)|perfeito|segue|entendido|manda ver|toca ficha|vamos lá)\.?$', t, re.I))

def _strategy_selection(text: str, strategies: list[str]) -> int | None:
    """
    Returns the index (0-based) of the selected strategy, or None.
    Rules:
      - numeric "1" to "9" → index (n-1) if exists
      - text match: fuzzy (simple) >= 0.60 on title
    """
    if not text:
        return None
    t = text.strip().lower()

    # numeric selection
    m = re.match(r'^\s*([1-9])\s*$', t)
    if m:
        idx = int(m.group(1)) - 1
        return idx if 0 <= idx < len(strategies) else None

    # text selection with fuzzy matching
    def _score(a: str, b: str) -> float:
        # simple jaccard over tokens
        sa, sb = set(re.findall(r'\w+', a.lower())), set(re.findall(r'\w+', b.lower()))
        inter = len(sa & sb)
        uni = len(sa | sb) or 1
        score = inter / uni
        # boost if user input is substring of title
        if a in b:
            score = max(score, 0.70)

def drop_justificativa_blocks(txt: str) -> str:
    """Remove entire blocks that start with 'Justificativa da Contratação' headings."""
    lines = txt.splitlines(keepends=True)
    out, skipping = [], False
    for ln in lines:
        if JUSTIF_HDR_RE.match(ln):
            skipping = True
            continue
        # Exit skip mode when finding blank line or new heading/item
        if skipping and (ln.strip() == "" or re.match(r"(?i)^\s*(\d+\.\s+|•\s+|-{1}\s+|\*\*)", ln)):
            skipping = False
        if not skipping:
            out.append(ln)
    return "".join(out)

def _sanitize_chat(text: str) -> str:
    """
    Remove banned headings from chat output (Justificativa, Descrição da Necessidade).
    This sanitization is ONLY for chat display - preview/docx remain complete.
    NOTE: No .strip() to preserve spaces in streaming.
    """
    if not text:
        return text
    # Remove titles/lines starting with "Justificativa"
    text = re.sub(r"(?im)^\s*\*?\*?\s*justificativa[^\n]*\n?", "", text)
    # Remove heading "Descrição da Necessidade" that sometimes leaks from KB
    text = re.sub(r"(?im)^\s*\*?\*?\s*descri[cç][aã]o da necessidade[^\n]*\n?", "", text)
    return text

# ===================== EtpParts Persistence Helpers =====================
def load_parts(conversation_id: str) -> EtpParts:
    """
    Load EtpParts from conversation metadata.
    Returns a new EtpParts if none exists.
    """
    conv = Conversation.query.filter_by(id=conversation_id).first()
    if not conv or not conv.metadata:
        return EtpParts()
    
    parts_data = conv.metadata.get('etp_parts', {})
    if not parts_data:
        return EtpParts()
    
    # Reconstruct EtpParts from dict
    return EtpParts(
        necessidade_texto=parts_data.get('necessidade_texto'),
        requisitos=parts_data.get('requisitos', []),
        estrategias=parts_data.get('estrategias', []),
        recomendacao=parts_data.get('recomendacao'),
        pca_status=parts_data.get('pca_status'),
        pca_texto=parts_data.get('pca_texto'),
        normas=parts_data.get('normas', []),
        itens_valor=parts_data.get('itens_valor', []),
        metodologia_valor=parts_data.get('metodologia_valor'),
        parcelamento_decisao=parts_data.get('parcelamento_decisao'),
        parcelamento_texto=parts_data.get('parcelamento_texto'),
        resumo_executivo=parts_data.get('resumo_executivo')
    )

def save_parts(conversation_id: str, parts: EtpParts):
    """Save EtpParts to conversation metadata"""
    conv = Conversation.query.filter_by(id=conversation_id).first()
    if not conv:
        logger.warning(f"[PERSIST] Conversation {conversation_id} not found")
        return
    
    if not conv.metadata:
        conv.metadata = {}
    
    # Convert EtpParts to dict
    conv.metadata['etp_parts'] = {
        'necessidade_texto': parts.necessidade_texto,
        'requisitos': parts.requisitos,
        'estrategias': parts.estrategias,
        'recomendacao': parts.recomendacao,
        'pca_status': parts.pca_status,
        'pca_texto': parts.pca_texto,
        'normas': parts.normas,
        'itens_valor': parts.itens_valor,
        'metodologia_valor': parts.metodologia_valor,
        'parcelamento_decisao': parts.parcelamento_decisao,
        'parcelamento_texto': parts.parcelamento_texto,
        'resumo_executivo': parts.resumo_executivo
    }
    db.session.commit()
    logger.info(f"[PERSIST] Saved EtpParts for conversation {conversation_id}")

def persist_stage_output(conversation_id: str, stage: str, reply: dict):
    """
    Persist stage output to EtpParts.
    Maps stage data to appropriate EtpParts fields.
    """
    parts = load_parts(conversation_id)
    data = reply.get("data", {})
    text = reply.get("text", "")
    
    if stage == "collect_need":
        parts.necessidade_texto = text
    elif stage == "suggest_requirements":
        parts.requisitos = data.get("requirements", [])
    elif stage == "solution_strategies":
        parts.estrategias = data.get("strategies", [])
        parts.recomendacao = data.get("recommendation")
    elif stage == "pca":
        parts.pca_status = data.get("status")
        parts.pca_texto = data.get("text")
    elif stage == "legal_norms":
        parts.normas = data.get("norms", [])
    elif stage == "qty_value":
        parts.itens_valor = data.get("items", [])
        parts.metodologia_valor = data.get("methodology")
    elif stage == "installment":
        parts.parcelamento_decisao = data.get("decision")
        parts.parcelamento_texto = data.get("text")
    elif stage == "summary":
        parts.resumo_executivo = data.get("executive_summary", text)
    
    save_parts(conversation_id, parts)
    logger.info(f"[PERSIST] Stage {stage} output persisted for conversation {conversation_id}")

# ===================== Decision-awaiting helpers =====================
def ask_user_decision(session, prompt_text: str, proposal_text: str, stage: str) -> str:
    """
    Arms the session for decision-awaiting mode and returns a prompt with options.
    Does NOT advance stage until user makes a choice.
    
    Args:
        session: ETP session object
        prompt_text: Contextual prompt explaining the situation
        proposal_text: The proposed text/content for acceptance
        stage: Current stage name (for logging)
    
    Returns:
        String with prompt + options (1/2/3)
    """
    answers = session.get_answers()
    if 'state' not in answers:
        answers['state'] = {}
    
    answers['state']['awaiting_decision'] = True
    answers['state']['pending_proposal'] = proposal_text
    answers['state']['decision_stage'] = stage
    session.set_answers(answers)
    db.session.commit()
    
    logger.info(f"[{stage.upper()}] awaiting_decision (not advancing)")
    
    return (
        prompt_text + "\n\n"
        "**Opções:**\n"
        "1) **Aceitar** a sugestão inicial acima e seguir.\n"
        "2) **Registrar como Pendente** (anotamos os detalhes sugeridos) e seguir.\n"
        "3) **Quero debater mais** (ficamos neste ponto e ajustamos juntos)."
    )

def try_consume_decision(session, user_text: str) -> dict | str | None:
    """
    Attempts to consume a pending decision from the user.
    
    Args:
        session: ETP session object
        user_text: User's message
    
    Returns:
        - None: No decision is pending
        - str: Confirmation prompt asking user to clarify their choice
        - dict: Decision object with 'action' and 'text' keys
            action: 'accept' | 'pendente' | 'debate'
            text: The proposal text (for accept/pendente actions)
    """
    answers = session.get_answers()
    state = answers.get('state', {})
    
    if not state.get('awaiting_decision'):
        return None  # No decision pending
    
    t = (user_text or "").strip().lower()
    
    # Check if it's a vague acknowledgment that should not be treated as a decision
    if intents.is_vague_ack(user_text):
        logger.info(f"[DECISION] Vague acknowledgment detected, asking for clarification: {user_text[:30]}")
        return (
            "Só para confirmar: prefere **1) aceitar**, **2) marcar como pendente**, "
            "ou **3) debater mais**?"
        )
    
    # Detect choice (removed "ok" and "sim" from accepted list - they should be explicit)
    accepted = t in {"1", "aceitar", "aceito", "1)"} or "aceitar" in t
    pendente = t in {"2", "pendente", "registre como pendente", "2)"} or "pendente" in t
    debate = t in {"3", "debater", "quero debater", "ajustar", "3)"} or "debater" in t
    
    if not (accepted or pendente or debate):
        # Ask for confirmation
        return (
            "Só para confirmar: prefere **1) aceitar**, **2) marcar como pendente**, "
            "ou **3) debater mais**?"
        )
    
    # Clear decision state
    state['awaiting_decision'] = False
    proposal = state.get('pending_proposal', '')
    decision_stage = state.get('decision_stage', '')
    state['pending_proposal'] = None
    state['decision_stage'] = None
    answers['state'] = state
    session.set_answers(answers)
    
    if accepted:
        logger.info(f"[{decision_stage.upper()}] decision=accept, advancing")
        return {"action": "accept", "text": proposal}
    elif pendente:
        logger.info(f"[{decision_stage.upper()}] decision=pendente, advancing")
        return {"action": "pendente", "text": proposal}
    else:
        logger.info(f"[{decision_stage.upper()}] decision=debate, staying at stage")
        return {"action": "debate", "text": ""}

def _strategy_selection_score(t: str, title: str) -> float:
    """Helper for _strategy_selection: calculates fuzzy score"""
    # simple jaccard over tokens
    sa, sb = set(re.findall(r'\w+', t.lower())), set(re.findall(r'\w+', title.lower()))
    inter = len(sa & sb)
    uni = len(sa | sb) or 1
    score = inter / uni
    # boost if user input is substring of title
    if t in title:
        score = max(score, 0.70)
    return score

def _strategy_selection_complete(text: str, strategies: list[str]) -> int | None:
    """Complete version of strategy selection"""
    if not text:
        return None
    t = text.strip().lower()
    
    # numeric selection
    m = re.match(r'^\s*([1-9])\s*$', t)
    if m:
        idx = int(m.group(1)) - 1
        return idx if 0 <= idx < len(strategies) else None
    
    best, bi = 0.0, None
    for i, title in enumerate(strategies):
        s = _score(t, title.lower())
        if s > best:
            best, bi = s, i
    return bi if best >= 0.60 else None

def _parse_strategy_selection(user_input: str, strategies: list) -> list:
    """
    Parse user selection of strategies.
    Supports:
    - Numeric selection: r'^\\s*([1-9])\\s*$' (1-9)
    - Text-based fuzzy matching with strategy titles (threshold ≥ 0.60)
    
    Returns list of selected strategies or None if no valid selection found.
    """
    from difflib import SequenceMatcher
    
    if not user_input or not strategies:
        return None
    
    user_input_stripped = user_input.strip()
    
    # Try numeric selection first
    numeric_pattern = r'^\s*([1-9])\s*$'
    match = re.match(numeric_pattern, user_input_stripped)
    if match:
        index = int(match.group(1)) - 1  # Convert to 0-based index
        if 0 <= index < len(strategies):
            logger.info(f"[STRATEGY_SELECT] Numeric selection: {index + 1}")
            return [strategies[index]]
        else:
            logger.info(f"[STRATEGY_SELECT] Numeric selection out of range: {index + 1}")
            return None
    
    # Try text-based fuzzy matching
    user_lower = user_input.lower().strip()
    best_match = None
    best_score = 0.0
    
    for strategy in strategies:
        titulo = strategy.get('titulo', '')
        if not titulo:
            continue
        
        titulo_lower = titulo.lower()
        
        # Calculate similarity
        similarity = SequenceMatcher(None, user_lower, titulo_lower).ratio()
        
        # Also check if user input is contained in title (partial match)
        if user_lower in titulo_lower:
            similarity = max(similarity, 0.70)  # Boost for substring match
        
        if similarity >= 0.60 and similarity > best_score:
            best_score = similarity
            best_match = strategy
    
    if best_match:
        logger.info(f"[STRATEGY_SELECT] Text match: '{user_input}' -> '{best_match.get('titulo')}' (score={best_score:.2f})")
        return [best_match]
    
    logger.info(f"[STRATEGY_SELECT] No match found for: '{user_input}'")
    return None

def _consult_path_explainer(necessity: str) -> tuple:
    """
    Gera alternativas contextualizadas a partir da necessidade usando LLM gpt-4.1.
    Retorna (texto_consultivo, lista_opcoes).
    """
    from application.ai.hybrid_models import OpenAIChatConsultive
    import logging
    import json
    import re
    
    logger = logging.getLogger(__name__)
    nec = (necessity or '').strip()
    
    prompt = f"""Você é um consultor de contratações públicas. Analise esta necessidade e sugira APENAS as alternativas realmente adequadas (não mais que 3):

Necessidade: "{nec}"

Para cada alternativa pertinente, forneça:
- Nome da modalidade (ex.: "Compra", "Serviço continuado", "Locação" apenas se fizer sentido)
- Prós e contras específicos para ESTA necessidade

IMPORTANTE:
- NÃO sugira locação para bens de consumo (alimentos, materiais descartáveis, insumos)
- NÃO sugira locação se o bem se exaure com uso
- Para gêneros alimentícios: considere apenas compra ou serviço de fornecimento continuado
- Para serviços: foque em terceirização ou execução direta
- Para equipamentos duráveis: pode incluir compra, locação ou serviço gerenciado

Retorne em formato JSON:
{{
  "alternativas": [
    {{"nome": "...", "pros": "...", "contras": "..."}},
    ...
  ]
}}"""

    try:
        llm = OpenAIChatConsultive()
        model_name = get_model_name()
        logger.info(f"[LM] model={model_name} temp=0.7 stage=solution_path_generation")
        raw = llm.generate(prompt)
        
        # Parse JSON do retorno
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            alts = data.get('alternativas', [])
        else:
            alts = []
        
        if not alts:
            # Fallback simples contextual
            nec_l = _normalize(nec).lower()
            if any(k in nec_l for k in ['alimento', 'comida', 'gênero', 'merenda', 'refeição', 'alimentício']):
                alts = [
                    {"nome": "Compra direta", "pros": "Controle de qualidade e sazonalidade", "contras": "Gestão de estoque e validade"},
                    {"nome": "Serviço de fornecimento continuado", "pros": "Reposição regular e responsabilidade do fornecedor", "contras": "Menor controle sobre origem"}
                ]
            else:
                alts = [
                    {"nome": "Aquisição (compra)", "pros": "Controle do ativo", "contras": "CAPEX e manutenção própria"},
                    {"nome": "Serviço/terceirização", "pros": "Entrega por SLA", "contras": "Governança contratual intensa"}
                ]
        
        # Monta texto consultivo em prosa natural
        opcoes = []
        alt_texts = []
        for i, alt in enumerate(alts, start=1):
            nome = alt.get('nome', 'Opção')
            pros = alt.get('pros', '')
            contras = alt.get('contras', '')
            linha = f"{i}) {nome} — {pros}. Por outro lado, {contras.lower() if contras else 'requer atenção aos detalhes'}."
            alt_texts.append(linha)
            opcoes.append(nome)
        
        # Gerar parágrafo contextual usando LLM
        alternatives_text = "\n".join(alt_texts)
        context_prompt = f"""Para a necessidade "{nec}", apresente estas alternativas em 1-2 parágrafos de prosa natural, explicando por que cada uma é pertinente ao caso, sem usar headers ou comandos para o usuário:

{alternatives_text}

Escreva em tom consultivo e natural, finalizando de forma que o usuário se sinta confortável para escolher."""
        
        try:
            context_para = llm.generate(context_prompt)
            # Adicionar as opções numeradas após o contexto
            final_text = f"{context_para}\n\n{alternatives_text}"
        except Exception:
            # Fallback simples em prosa
            final_text = f'Para "{nec}", identifiquei estas alternativas que fazem sentido:\n\n{alternatives_text}\n\nCada uma tem suas vantagens específicas para seu contexto.'
        
        return final_text, opcoes
        
    except Exception as e:
        logger.error(f"Erro em _consult_path_explainer: {e}")
        # Fallback seguro
        return ("Precisamos escolher o caminho. Qual você prefere: compra ou serviço?", ["Compra", "Serviço"])

def _generate_prose_transition(stage: str, context: dict = None) -> str:
    """
    Gera transições em prosa natural usando LLM para cada etapa da conversa.
    Proibido usar: "Por que", "Como ajustar", "Você pode", cabeçalhos, menu rígido.
    """
    from application.ai.hybrid_models import OpenAIChatConsultive
    
    llm = OpenAIChatConsultive()
    context = context or {}
    
    prompts = {
        'confirm_to_solution_path': f"""O usuário acabou de confirmar os requisitos para a necessidade: "{context.get('necessity', '')}". 
        
Escreva 1-2 frases em prosa natural anunciando que agora vamos analisar as melhores alternativas para atender essa necessidade, sem usar comandos ou headers. Seja consultivo e direto.""",
        
        'solution_path_to_pca': f"""O usuário escolheu a alternativa "{context.get('chosen', '')}" para a contratação.
        
Escreva 1-2 frases em prosa natural perguntando sobre a previsão no PCA (Plano de Contratações Anual), aceitando incerteza. Não use formato de pergunta engessada.""",
        
        'pca_to_legal_norms': f"""O usuário respondeu sobre PCA: {context.get('pca_response', 'indefinido')}.
        
Escreva 1-2 frases em prosa natural fazendo a transição para normas legais, sugerindo opções comuns (Lei 14.133/21, regulamento local, etc.) mas aceitando que o usuário não saiba agora. Sem menu rígido.""",
        
        'legal_norms_to_qty': """O usuário informou as normas legais.
        
Escreva 1-2 frases em prosa natural perguntando sobre quantitativo e valor estimado, oferecendo ajuda caso não saiba (unidade, ordem de grandeza). Seja conversacional.""",
        
        'qty_to_installment': f"""O usuário informou: {context.get('qty_response', '')}.
        
Escreva 1-2 frases em prosa natural perguntando sobre parcelamento da contratação, explicando brevemente prós/contras sem formato didático. Seja natural."""
    }
    
    prompt = prompts.get(stage, "")
    if not prompt:
        return ""
    
    try:
        return llm.generate(prompt).strip()
    except Exception as e:
        logger.error(f"Erro ao gerar prosa para {stage}: {e}")
        # Fallback genérico
        return "Entendido. Vamos ao próximo ponto."

def _suggest_requirements(necessity: str) -> list:
    """Fallback de requisitos sugeridos quando o gerador não estiver disponível."""
    return [
        "Comprovação de experiência específica no escopo (projetos similares nos últimos 5 anos).",
        "Equipe dedicada com qualificações compatíveis e substituição sem prejuízo ao serviço.",
        "Conformidade com normas aplicáveis e regulatórias do setor.",
        "Plano de atendimento/manutenção com SLAs definidos.",
        "Integração com sistemas existentes e transferência de conhecimento/documentação.",
        "KPIs de desempenho e relatórios periódicos.",
        "Gestão de riscos e plano de contingência."
    ]

# ---------- HELPER: standardized response payload ----------
def _text_payload(session, text: str, extra: dict = None) -> dict:
    """
    Standardized response payload for all conversation endpoints.
    Always includes: success, kind, ai_response, message, conversation_stage, session_id
    """
    base = {
        'success': True,
        'kind': 'text',
        'ai_response': text,
        'message': text,
        'conversation_stage': getattr(session, 'conversation_stage', None),
        'session_id': getattr(session, 'session_id', None)
    }
    if extra:
        base.update(extra)
    return base

# ---------- HELPER: ensure session exists ----------
def ensure_session(sid: str = None, title: str = None) -> EtpSession:
    """
    Ensures that a session exists and its ID matches exactly what the client provided.
    Rules:
    - If sid is empty/None: generate a new sid and create the session.
    - If sid exists in DB: return that session.
    - If sid doesn't exist in DB: create session with exactly that sid.
    """
    if sid:
        s = EtpSession.query.filter_by(session_id=sid).first()
        if s:
            return s
        # Create new session with the exact sid provided by client
        s = EtpSession(
            user_id=1,
            session_id=sid,
            status='active',
            title=title or "Novo Estudo Técnico Preliminar",
            answers={},
            conversation_stage='collect_need',
            created_at=datetime.utcnow()
        )
        db.session.add(s)
        db.session.commit()
        return s
    # No sid provided → create new with generated UUID
    new_sid = str(uuid.uuid4())
    s = EtpSession(
        user_id=1,
        session_id=new_sid,
        status='active',
        title=title or "Novo Estudo Técnico Preliminar",
        answers={},
        conversation_stage='collect_need',
        created_at=datetime.utcnow()
    )
    db.session.add(s)
    db.session.commit()
    return s

def parse_update_command(user_message, current_requirements):
    """
    Parse user commands for requirement updates
    Returns dict with:
    - action: 'remove', 'edit', 'keep_only', 'add', 'unclear'
    - items: list of requirement IDs or content
    - message: explanation of what was done
    """
    import re
    
    message_lower = user_message.lower()
    
    # Check for explicit necessity restart keywords
    restart_keywords = [
        "nova necessidade", "trocar a necessidade", "na verdade a necessidade é",
        "mudou a necessidade", "preciso trocar a necessidade"
    ]
    
    for keyword in restart_keywords:
        if keyword in message_lower:
            return {
                'action': 'restart_necessity',
                'items': [],
                'message': 'Detectada solicitação para reiniciar necessidade'
            }
    
    # Extract requirement numbers (R1, R2, etc. or just numbers)
    req_numbers = []
    
    # Look for patterns like "R1", "R2", "requisito 1", "primeiro", "último", etc.
    r_patterns = re.findall(r'[rR](\d+)', user_message)
    req_numbers.extend([f"R{n}" for n in r_patterns])
    
    # Look for standalone numbers that might refer to requirements
    number_patterns = re.findall(r'\b(\d+)\b', user_message)
    for n in number_patterns:
        if int(n) <= len(current_requirements):
            req_id = f"R{n}"
            if req_id not in req_numbers:
                req_numbers.append(req_id)
    
    # Handle positional references
    if 'último' in message_lower or 'ultima' in message_lower:
        if current_requirements:
            req_numbers.append(current_requirements[-1].get('id', f"R{len(current_requirements)}"))
    
    if 'primeiro' in message_lower or 'primeira' in message_lower:
        if current_requirements:
            req_numbers.append(current_requirements[0].get('id', 'R1'))
    
    if 'penúltimo' in message_lower or 'penultima' in message_lower:
        if len(current_requirements) > 1:
            req_numbers.append(current_requirements[-2].get('id', f"R{len(current_requirements)-1}"))
    
    # Determine action type
    if any(word in message_lower for word in ['remover', 'tirar', 'excluir', 'deletar', 'retirar']):
        if req_numbers:
            return {
                'action': 'remove',
                'items': req_numbers,
                'message': f'Removidos requisitos: {", ".join(req_numbers)}'
            }
        else:
            return {'action': 'unclear', 'items': [], 'message': 'Não foi possível identificar quais requisitos remover'}
    
    if any(word in message_lower for word in ['manter apenas', 'só manter', 'manter só', 'manter somente']):
        if req_numbers:
            return {
                'action': 'keep_only',
                'items': req_numbers,
                'message': f'Mantidos apenas requisitos: {", ".join(req_numbers)}'
            }
        else:
            return {'action': 'unclear', 'items': [], 'message': 'Não foi possível identificar quais requisitos manter'}
    
    if any(word in message_lower for word in ['alterar', 'modificar', 'trocar', 'mudar', 'editar']):
        if req_numbers:
            return {
                'action': 'edit',
                'items': req_numbers,
                'message': f'Requisitos para edição: {", ".join(req_numbers)}'
            }
        else:
            return {'action': 'unclear', 'items': [], 'message': 'Não foi possível identificar quais requisitos alterar'}
    
    if any(word in message_lower for word in ['adicionar', 'incluir', 'acrescentar', 'novo requisito']):
        # Extract the content after the add command
        add_content = user_message
        for word in ['adicionar', 'incluir', 'acrescentar']:
            if word in message_lower:
                parts = user_message.lower().split(word, 1)
                if len(parts) > 1:
                    add_content = parts[1].strip()
                break
        
        return {
            'action': 'add',
            'items': [add_content],
            'message': f'Novo requisito adicionado: {add_content}'
        }
    
    # Check for confirmation words
    confirm_words = [
        'confirmar', 'confirmo', 'manter', 'ok', 'está bom', 'perfeito',
        'concordo', 'aceito', 'pode ser', 'sim'
    ]
    
    if any(word in message_lower for word in confirm_words):
        return {
            'action': 'confirm',
            'items': [],
            'message': 'Requisitos confirmados'
        }
    
    # If nothing clear was detected
    return {
        'action': 'unclear',
        'items': [],
        'message': 'Comando não reconhecido'
    }

def _get_etp_components():
    """Lazy initialization of ETP components to avoid circular imports"""
    global _etp_generator, _prompt_generator, _rag_system, _initialized
    
    if not _initialized:
        _etp_generator, _prompt_generator, _rag_system = init_etp_dynamic()
        _initialized = True
    
    return _etp_generator, _prompt_generator, _rag_system

# Initialize components for backward compatibility
def _ensure_initialized():
    """Ensure components are initialized"""
    global etp_generator, prompt_generator, rag_system
    etp_generator, prompt_generator, rag_system = _get_etp_components()

# Configure logging
logger = logging.getLogger(__name__)

# Perguntas do ETP conforme especificado
ETP_QUESTIONS = [
    {
        "id": 1,
        "question": "Qual a descrição da necessidade da contratação?",
        "type": "text",
        "required": True,
        "section": "OBJETO DO ESTUDO E ESPECIFICAÇÕES GERAIS"
    },
    {
        "id": 2,
        "question": "Você gostaria de manter esses requisitos, ajustar algum deles ou incluir outros?",
        "type": "text",
        "required": True,
        "section": "DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO"
    },
    {
        "id": 3,
        "question": "Possui demonstrativo de previsão no PCA?",
        "type": "boolean",
        "required": True,
        "section": "OBJETO DO ESTUDO E ESPECIFICAÇÕES GERAIS"
    },
    {
        "id": 4,
        "question": "Quais normas legais pretende utilizar?",
        "type": "text",
        "required": True,
        "section": "DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO"
    },
    {
        "id": 5,
        "question": "Qual o quantitativo e valor estimado?",
        "type": "text",
        "required": True,
        "section": "ESTIMATIVA DAS QUANTIDADES E VALORES"
    },
    {
        "id": 6,
        "question": "Haverá parcelamento da contratação?",
        "type": "boolean",
        "required": True,
        "section": "JUSTIFICATIVA PARA O PARCELAMENTO"
    }
]

def _text_payload(session, text, extra=None):
    """Helper para criar payload de resposta de texto padronizado"""
    payload = {
        'success': True,
        'kind': 'text',
        'ai_response': text,
        'message': text,
        'session_id': session.session_id,
        'conversation_stage': session.conversation_stage
    }
    if extra:
        payload.update(extra)
    return payload

def _parse_strategy_selection(user_text: str, strategies: list) -> list:
    """
    Interpreta a seleção de estratégia pelo usuário.
    Aceita: número puro ("2"), título parcial ("outsourcing"), ou múltiplos ("1 e 3", "2,3")
    
    Returns:
        Lista de estratégias selecionadas ou None se não houver correspondência
    """
    if not strategies or not user_text:
        return None
    
    text = (user_text or "").strip().lower()
    
    # 1) Número puro (ex: "2")
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(strategies):
            logger.info(f"[STRATEGY_SELECT] Selected by number: {idx+1}")
            return [strategies[idx]]
    
    # 2) Busca por título aproximado
    for s in strategies:
        title = (s.get("titulo") or s.get("title") or "").lower()
        if title:
            # Match por substring inicial ou palavras-chave
            if title[:20] in text or any(word in text for word in title.split()[:3] if len(word) > 3):
                logger.info(f"[STRATEGY_SELECT] Selected by title match: {s.get('titulo')}")
                return [s]
    
    # 3) Múltiplas seleções (ex.: "1 e 3", "2,3", "1 2")
    import re
    nums = [int(n)-1 for n in re.findall(r"\b\d+\b", text)]
    if nums:
        picked = [strategies[i] for i in nums if 0 <= i < len(strategies)]
        if picked:
            logger.info(f"[STRATEGY_SELECT] Selected multiple: {[s.get('titulo') for s in picked]}")
            return picked
    
    return None

@etp_dynamic_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """Verificação de saúde da API dinâmica e do gerador de requisitos"""
    try:
        _ensure_initialized()
        # Verificar se os geradores estão funcionando
        kb_info = etp_generator.get_knowledge_base_info() if etp_generator else {}
        
        # Check simple generator status
        try:
            simple_gen = _get_simple_generator()
            generator_name = simple_gen.__class__.__name__
            generator_ready = True
        except Exception as gen_error:
            generator_name = f"Error: {str(gen_error)}"
            generator_ready = False

        return jsonify({
            'status': 'healthy',
            'version': '3.0.0-dynamic',
            'openai_configured': bool(os.getenv('OPENAI_API_KEY')),
            'etp_generator_ready': etp_generator is not None,
            'simple_generator': generator_name,
            'simple_generator_ready': generator_ready,
            'knowledge_base': {
                'documents_loaded': kb_info.get('total_documents', 0),
                'common_sections': len(kb_info.get('common_sections', []))
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@etp_dynamic_bp.route('/new', methods=['POST'])
@cross_origin()
def create_new_conversation():
    """Create a new conversation with persistent storage and fresh EtpSession"""
    try:
        user_id = get_current_user_id()
        
        # Generate sequential title with timestamp
        from datetime import datetime
        title = f"Novo Documento {datetime.now().strftime('%d/%m %H:%M')}"
        
        # Create conversation in database
        conv = ConversationRepo.create(user_id=user_id, title=title)
        
        # Create a new EtpSession with fresh state using the conversation_id as session_id
        # This ensures state is reset for the new document
        new_session_id = str(conv.id)  # Use conversation ID as session ID
        new_session = ensure_session(sid=new_session_id, title=title)
        
        # Ensure the session starts fresh
        new_session.necessity = None
        new_session.set_requirements([])
        new_session.set_answers({})
        new_session.conversation_stage = 'collect_need'
        new_session.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"[NEW_DOCUMENT] Created conversation {conv.id} and session {new_session_id} for user: {user_id}")
        
        return jsonify({
            'success': True,
            'conversation_id': conv.id,
            'session_id': new_session_id,
            'title': conv.title,
            'conversation_stage': 'collect_need',
            'created_at': conv.created_at.isoformat(),
            'updated_at': conv.updated_at.isoformat()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating new conversation: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro ao criar nova conversa: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/list', methods=['GET'])
@cross_origin()
def list_conversations():
    """List all conversations for the current user with message preview"""
    try:
        user_id = get_current_user_id()
        
        # Get conversations ordered by updated_at DESC
        conversations_list = ConversationRepo.list_by_user(user_id=user_id, limit=100)
        
        result = []
        for conv in conversations_list:
            # Get last message for preview
            last_msg = MessageRepo.get_last_message(conv.id)
            preview = ""
            if last_msg:
                preview = last_msg.content[:120] + "..." if len(last_msg.content) > 120 else last_msg.content
            
            result.append({
                'id': conv.id,
                'title': conv.title,
                'preview': preview,
                'updated_at': conv.updated_at.isoformat(),
                'created_at': conv.created_at.isoformat()
            })
        
        logger.info(f"[CONVERSATION] Listed {len(result)} conversations for user: {user_id}")
        
        return jsonify({
            'success': True,
            'conversations': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro ao listar conversas: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/chat-stage', methods=['POST'])
@cross_origin()
def chat_stage_based():
    """Deterministic stage-based chat returning structured payloads only."""
    try:
        data = request.get_json(force=True) or {}
        conversation_id = data.get('conversation_id')
        user_message = (data.get('message') or '').strip()

        if not conversation_id:
            return jsonify({'success': False, 'error': 'conversation_id é obrigatório'}), 400

        if not user_message:
            return jsonify({'success': False, 'error': 'Mensagem é obrigatória'}), 400

        conv = ConversationRepo.get(conversation_id)
        if not conv:
            return jsonify({'success': False, 'error': 'Conversa não encontrada'}), 404

        session = EtpSession.query.filter_by(session_id=str(conversation_id)).first()
        if not session:
            session = ensure_session(sid=str(conversation_id))

        current_stage = session.conversation_stage or 'collect_need'
        necessity = session.necessity or ''
        answers = session.get_answers() or {}
        requirements = session.get_requirements() or []

        logger.info(
            "[CHAT_STAGE] conversation=%s stage=%s message=%s",
            conversation_id,
            current_stage,
            user_message[:80],
        )

        MessageRepo.add(
            conversation_id=conversation_id,
            role='user',
            content=user_message,
            stage=current_stage,
        )

        payload: dict[str, Any] = {}
        next_stage = current_stage

        if current_stage == 'collect_need':
            session.necessity = user_message
            necessity = user_message
            context_chunks = []
            try:
                from rag.retrieval import retrieve_for_stage

                context_chunks = [
                    chunk.get('text', '')
                    for chunk in retrieve_for_stage(necessity, 'suggest_requirements', k=6)
                ]
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("[CHAT_STAGE] falha ao recuperar contexto: %s", exc)

            result = generate_requirements_strict(necessity, context=context_chunks)
            result = keep_only_expected(result)
            requisitos = result.get('requisitos', [])
            requisitos = _persist_structured_requirements(session, requisitos)
            requirements = requisitos
            payload = {'requisitos': requisitos}
            next_stage = 'suggest_requirements'

        elif current_stage == 'suggest_requirements':
            if _is_confirm(user_message):
                result = generate_strategies_strict(necessity, requirements)
                result = keep_only_expected(result)
                estrategias = result.get('estrategias', [])
                answers['estrategias'] = estrategias
                session.set_answers(answers)
                payload = {'estrategias': estrategias}
                next_stage = 'solution_strategies'
            else:
                complemento = user_message if user_message else ''
                consulta = f"{necessity}\n{complemento}" if necessity else complemento
                context_chunks = []
                try:
                    from rag.retrieval import retrieve_for_stage

                    context_chunks = [
                        chunk.get('text', '')
                        for chunk in retrieve_for_stage(consulta, 'suggest_requirements', k=6)
                    ]
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("[CHAT_STAGE] falha ao recuperar contexto: %s", exc)

                result = generate_requirements_strict(consulta, extra_details=complemento, context=context_chunks)
                result = keep_only_expected(result)
                requisitos = result.get('requisitos', [])
                requisitos = _persist_structured_requirements(session, requisitos)
                requirements = requisitos
                payload = {'requisitos': requisitos}
                next_stage = 'suggest_requirements'

        elif current_stage == 'solution_strategies':
            estrategias = answers.get('estrategias') or []
            if not estrategias:
                result = generate_strategies_strict(necessity, requirements)
                result = keep_only_expected(result)
                estrategias = result.get('estrategias', [])
                answers['estrategias'] = estrategias
                session.set_answers(answers)
            payload = {'estrategias': estrategias[:3]}
            next_stage = 'solution_strategies'

        else:
            payload = keep_only_expected({'requisitos': requirements})

        if next_stage != current_stage:
            _set_stage(session, next_stage)

        db.session.commit()

        response = {
            'success': True,
            'conversation_id': conversation_id,
            'conversation_stage': session.conversation_stage,
            'payload': payload,
        }
        return jsonify(response), 200

    except AssertionError as err:
        db.session.rollback()
        logger.error("[CHAT_STAGE] transição inválida: %s", err)
        return jsonify({'success': False, 'error': str(err)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in chat_stage_based: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Erro ao processar chat.'}), 500


@etp_dynamic_bp.route('/chat-persist', methods=['POST'])
@cross_origin()
def chat_persist():
    """Send a message in a conversation with full database persistence"""
    try:
        data = request.get_json(force=True)
        conversation_id = data.get('conversation_id')
        message = data.get('message', '').strip()
        
        if not conversation_id or not message:
            return jsonify({
                'success': False,
                'error': 'conversation_id e message são obrigatórios'
            }), 400
        
        # Verify conversation exists
        conv = ConversationRepo.get(conversation_id)
        if not conv:
            return jsonify({
                'success': False,
                'error': 'Conversa não encontrada'
            }), 404
        
        # Save user message
        user_msg = MessageRepo.add(
            conversation_id=conversation_id,
            role='user',
            content=message
        )
        
        # Get conversation history for context
        all_messages = MessageRepo.list_for_conversation(conversation_id)
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in all_messages[:-1]  # Exclude the just-added user message
        ]
        
        # Generate AI response using OpenAI
        try:
            client = get_llm_client()
            model = get_model_name()
            
            # Build messages for LLM
            system_prompt = (
                "Você é um assistente especializado em ajudar a criar Estudos Técnicos Preliminares (ETP). "
                "Faça perguntas claras e objetivas para coletar informações sobre a necessidade de contratação."
            )
            
            llm_messages = [{"role": "system", "content": system_prompt}]
            llm_messages.extend(history)
            llm_messages.append({"role": "user", "content": message})
            
            response = client.chat.completions.create(
                model=model,
                messages=llm_messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            ai_response = response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            ai_response = "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
        
        # Save assistant message
        assistant_msg = MessageRepo.add(
            conversation_id=conversation_id,
            role='assistant',
            content=ai_response
        )
        
        db.session.commit()
        
        logger.info(f"[CONVERSATION] Message exchange in {conversation_id}")
        
        return jsonify({
            'success': True,
            'user_message': {
                'id': user_msg.id,
                'content': user_msg.content,
                'created_at': user_msg.created_at.isoformat()
            },
            'assistant_message': {
                'id': assistant_msg.id,
                'content': assistant_msg.content,
                'created_at': assistant_msg.created_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in chat-persist: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro ao processar mensagem: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/chat-stream', methods=['POST'])
@cross_origin()
def chat_stream():
    """
    Streaming chat endpoint with SSE support for type-by-type responses.
    
    Request JSON:
    {
        "session_id": "<uuid>",
        "message": "<user message>",
        "message_id": "<unique id for this message>" (optional)
    }
    
    Returns: Server-Sent Events stream with chunks:
    - data: {"type": "token", "content": "<token>", "message_id": "<id>"}
    - data: {"type": "done", "message_id": "<id>"}
    - data: {"type": "error", "error": "<message>", "message_id": "<id>"}
    """
    def generate():
        try:
            data = request.get_json()
            session_id = data.get('session_id', '').strip()
            user_message = data.get('message', '').strip()
            message_id = data.get('message_id', str(uuid.uuid4()))
            
            if not user_message:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Mensagem é obrigatória', 'message_id': message_id})}\n\n"
                return
            
            # Load or create session
            session = ensure_session(session_id)
            current_state = session.conversation_stage or 'collect_need'
            
            # [FLOW FIX] Force transition from collect_need to suggest_requirements
            if current_state == 'collect_need':
                logger.info("[STREAM] State=collect_need, Intent=user_input")
                logger.info("[FLOW FIX] Necessidade coletada, avançando para geração de requisitos.")
                
                # Save user message
                conversation_id = session_id
                MessageRepo.add(
                    conversation_id=conversation_id,
                    role='user',
                    content=user_message,
                    stage=current_state
                )
                
                # Store necessity and generate requirements immediately
                session.necessity = user_message
                next_stage = 'suggest_requirements'
                
                # Generate requirements using generate_answer
                from rag.retrieval import retrieve_for_stage
                from application.ai.generator import generate_answer
                
                context_chunks = retrieve_for_stage(user_message, 'suggest_requirements', k=12)
                rag_context = {
                    'chunks': context_chunks,
                    'necessity': user_message
                }
                
                result = generate_answer('suggest_requirements', [], user_message, rag_context)
                
                # Extract and store requirements (no justification in chat)
                intro = (result.get('intro') or '').strip()
                requirements = result.get('requirements', []) or []
                
                # Helper function to detect questions
                def _has_question_like(items):
                    qtriggers = ("qual", "quais", "existe", "há ", "ha ", "como", "quando", "onde", "por que", "porque", "por quê", "?")
                    for it in items or []:
                        if isinstance(it, dict):
                            s = it.get('text') or ''
                        else:
                            s = it if isinstance(it, str) else str(it)
                        s_low = s.lower()
                        if "?" in s_low or any(s_low.strip().startswith(x) for x in qtriggers):
                            return True
                    return False
                
                # If parece onboarding (perguntas), forçar nova geração em modo estrito
                if not requirements or _has_question_like(requirements):
                    from rag.retrieval import retrieve_for_stage
                    context_chunks = retrieve_for_stage(user_message, 'suggest_requirements', k=12)
                    rag_context_retry = {'chunks': context_chunks, 'necessity': user_message, 'strict_mode': True, 'no_questions': True}
                    logger.warning("[FLOW GUARD] Detecção de perguntas na lista. Regerando requisitos em modo estrito.")
                    result = generate_answer('suggest_requirements', [], user_message, rag_context_retry)
                    intro = (result.get('intro') or '').strip()
                requirements = result.get('requirements', []) or []

                def _normalize_requirement(item):
                    if isinstance(item, dict):
                        text = (item.get('text') or item.get('descricao') or item.get('requirement') or '').strip()
                        req_type = (item.get('type') or item.get('tipo') or '').strip()
                    else:
                        text = str(item or '').strip()
                        req_type = ''
                    if not text:
                        return None
                    # Try to extract type markers embedded in text
                    type_match = re.match(r'^\s*\d+[\.)]\s*\((Obrigatório|Desejável)\)\s*(.+)$', text, re.IGNORECASE)
                    if type_match and not req_type:
                        req_type = type_match.group(1).title()
                        text = type_match.group(2).strip()
                    return {
                        'text': text,
                        'type': req_type.title() if req_type else ''
                    }

                requirements = [item for item in (_normalize_requirement(req) for req in requirements) if item]
                
                # Fallback intro if empty (ALWAYS provide technical note)
                if not intro:
                    nec = (user_message or session.necessity or 'contratação').strip()
                    intro = f"Nota técnica inicial: com base na necessidade informada ({nec}), a lista a seguir foca requisitos verificáveis, SLAs e conformidade regulatória."
                
                # Deduplicate and store requirements
                from application.ai.generator import dedupe_requirements
                requirements = dedupe_requirements(requirements)
                session.set_requirements(requirements)
                
                # Build response: intro + requirements list (NO justification in chat)
                lines = []
                for idx, req in enumerate(requirements, start=1):
                    text = req.get('text', '').strip()
                    req_type = req.get('type', '').strip()
                    prefix = f"{idx}. "
                    if req_type:
                        prefix += f"({req_type}) "
                    if text and text[0].isdigit() and '.' in text[:4]:
                        # Avoid double numbering when model already provided it
                        lines.append(text)
                    else:
                        lines.append(f"{prefix}{text}")
                req_text = "\n".join(lines)
                ai_response = f"{intro}\n\n{req_text}".strip()
                
                # Stream tokens preserving spaces, then apply final sanitization
                chunks = []
                for char in ai_response:
                    chunks.append(char)
                    yield f"data: {json.dumps({'type': 'token', 'content': char, 'message_id': message_id})}\n\n"
                
                # Apply final sanitization
                full_raw = "".join(chunks)
                full_sanitized = drop_justificativa_blocks(full_raw)
                
                # Save assistant message
                MessageRepo.add(
                    conversation_id=conversation_id,
                    role='assistant',
                    content=full_sanitized,
                    stage=next_stage
                )
                
                # Update stage and complete
                session.conversation_stage = next_stage
                db.session.commit()
                logger.info(f"[STREAM] State=suggest_requirements")
                
                # Send final sanitized content for re-rendering
                yield f"data: {json.dumps({'type': 'final', 'content': full_sanitized, 'stage': next_stage, 'message_id': message_id})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'state': next_stage, 'state_changed': True, 'full_response': full_sanitized})}\n\n"
                return
            
            # Get session data
            answers = session.get_answers() or {}
            requirements = session.get_requirements() or []
            
            session_data = {
                'necessity': session.necessity,
                'requirements': requirements,
                'answers': answers,
                'solution_path': answers.get('solution_path'),
                'pca': answers.get('pca'),
                'legal_norms': answers.get('legal_norms'),
                'quant_value': answers.get('quant_value'),
                'parcelamento': answers.get('parcelamento')
            }
            
            logger.info(f"[STREAM] State={current_state}, Message={user_message[:50]}")
            
            # Parse user intent
            intent = csm.parse_user_intent(user_message, current_state, session_data)
            logger.info(f"[STREAM] Intent={intent['intent']}, Confidence={intent['confidence']}")
            
            # Check confirmation intent
            confirmation_intent = csm.classify_confirmation_intent(user_message)
            logger.info(f"[STREAM] Confirmation={confirmation_intent}")
            
            # Handle negative intent - stay in state and ask for adjustments
            if confirmation_intent == 'negative':
                yield f"data: {json.dumps({'type': 'token', 'content': 'Entendi que você quer fazer ajustes. ', 'message_id': message_id})}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': 'O que gostaria de modificar?', 'message_id': message_id})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'state': current_state, 'state_changed': False})}\n\n"
                return
            
            # Handle uncertain intent - provide clarification
            if confirmation_intent == 'uncertain':
                yield f"data: {json.dumps({'type': 'token', 'content': 'Parece que você tem dúvidas. ', 'message_id': message_id})}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': 'Você pode responder \"sim\" para prosseguir, ', 'message_id': message_id})}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': '\"não\" para fazer ajustes, ', 'message_id': message_id})}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': 'ou descrever o que precisa.', 'message_id': message_id})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'state': current_state, 'state_changed': False})}\n\n"
                return
            
            # Use OpenAI streaming for AI responses
            try:
                client = get_llm_client()
                model = get_model_name()
                
                # Build context for AI
                system_prompt = (
                    "Você é um assistente especializado em criar ETPs (Estudos Técnicos Preliminares). "
                    "Conduza a conversa de forma natural e objetiva. "
                    "Gere apenas o conteúdo da etapa solicitada, sem reabrir seções anteriores. "
                    "Proibido usar frases de onboarding como 'Vamos começar' ou 'Descrição da Necessidade'."
                )
                
                # Build conversation history from session
                messages = [{"role": "system", "content": system_prompt}]
                if session.necessity:
                    messages.append({"role": "user", "content": f"Necessidade: {session.necessity}"})
                messages.append({"role": "user", "content": user_message})
                
                # Stream response from OpenAI
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000,
                    stream=True
                )
                
                full_response = ""
                for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            content = delta.content
                            full_response += content
                            yield f"data: {json.dumps({'type': 'token', 'content': content, 'message_id': message_id})}\n\n"
                
                # Apply final sanitization
                full_sanitized = drop_justificativa_blocks(full_response)
                
                # Update session if needed based on intent
                state_changed = False
                new_state = current_state
                
                if confirmation_intent == 'positive' and current_state in NEXT_STAGE:
                    new_state = NEXT_STAGE[current_state]
                    session.conversation_stage = new_state
                    state_changed = True
                    db.session.commit()
                    logger.info(f"[STREAM] State transition: {current_state} -> {new_state}")
                
                # Send final sanitized content for re-rendering
                yield f"data: {json.dumps({'type': 'final', 'content': full_sanitized, 'stage': new_state, 'message_id': message_id})}\n\n"
                # Send completion event
                yield f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'state': new_state, 'state_changed': state_changed, 'full_response': full_sanitized})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in streaming: {e}")
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'message_id': message_id})}\n\n"
        
        except Exception as e:
            logger.error(f"Error in chat_stream: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'message_id': message_id if 'message_id' in locals() else 'unknown'})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@etp_dynamic_bp.route('/conversation', methods=['POST'])
@cross_origin()
def etp_conversation():
    """Conduz conversa natural usando o modelo fine-tuned para coleta de informações do ETP"""
    try:
        _ensure_initialized()
        # NOTE: We no longer return 500 if etp_generator is missing
        # The simple generator with fallback will handle requirements generation

        data = request.get_json()
        print("🔹 Recebi do frontend:", data)

        # Reset suave de conversa
        if data.get('reset') is True:
            sid = (data.get('session_id') or '').strip() or None
            session = ensure_session(sid)
            # limpa a sessão do ETP, preservando o session_id
            session.necessity = None
            session.set_requirements([])
            session.set_answers({})
            session.conversation_stage = 'collect_need'
            session.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Vamos começar do zero. Qual é a necessidade da contratação?',
                'conversation_stage': session.conversation_stage,
                'session_id': session.session_id
            })

        # Aceitar ambos os nomes para compatibilidade com o front atual
        user_message = (data.get('user_message') or data.get('message') or '').strip()
        session_id = data.get('session_id')
        conversation_history = data.get('conversation_history', [])
        answered_questions = data.get('answered_questions', [])

        if not user_message:
            return jsonify({'success': False, 'error': 'Mensagem é obrigatória'}), 400

        # REQUIREMENT: session_id is mandatory
        request_sid = (session_id or "").strip() or None
        if not request_sid:
            return jsonify({
                'success': False, 
                'error': 'session_id é obrigatório. Use POST /api/etp-dynamic/new para criar uma nova sessão.'
            }), 400

        # Get or create session with the provided session_id
        session = ensure_session(request_sid)
        
        # REQUIREMENT 1: Ensure session_id and client are never None
        # If session_id is None, create new and reinitialize
        if not session.session_id:
            session.session_id = str(uuid.uuid4())
            session.conversation_stage = 'collect_need'
            session.updated_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"[SESSION] Created new session_id: {session.session_id}")
        
        # Ensure OpenAI client is initialized for etp_generator
        global _openai_client, _simple_generator
        try:
            if _openai_client is None:
                api_key = os.getenv('OPENAI_API_KEY')
                if api_key:
                    import openai
                    _openai_client = openai.OpenAI(api_key=api_key)
                    logger.info("[CLIENT] OpenAI client initialized")
            
            if _simple_generator is None:
                _simple_generator = get_etp_generator(openai_client=_openai_client)
                logger.info("[GENERATOR] ETP generator initialized")
        except Exception as e:
            logger.error(f"[CLIENT] Failed to initialize client: {e}")
            # Don't fail - use fallback generator
            if _simple_generator is None:
                _simple_generator = FallbackGenerator()

        # Base de resposta com session_id
        resp_base = {"success": True, "session_id": session.session_id}
        
        print(f"🔹 [ANTES] request_sid={request_sid} | session_id={session.session_id} | stage={session.conversation_stage} | necessity={bool(session.necessity)}")
        print(f"🔹 [INPUT] Mensagem: '{user_message[:50]}{'...' if len(user_message) > 50 else '}'}")

        # PASSO 3: Interpretador de comandos ANTES do LLM
        # GUARDRAIL: Handle confirm_requirements stage
        if session.conversation_stage == 'confirm_requirements':
            # Check if user confirmed
            user_confirmed = is_user_confirmed(user_message)
            
            if user_confirmed:
                # ORDEM CORRETA: CAMINHO → PCA → NORMAS → QTD/VALOR → PARCELAMENTO → RESUMO → GERAR
                # Gerar transição em prosa natural
                next_question = _generate_prose_transition('confirm_to_solution_path', {'necessity': session.necessity})
                if not next_question:
                    next_question = "Certo. Vamos identificar a melhor forma de atender essa necessidade."
                
                session.conversation_stage = 'solution_path'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'kind': 'text',
                    'ai_response': next_question,
                    'message': next_question,
                    'conversation_stage': session.conversation_stage,
                    'session_id': session.session_id
                })
            else:
                # User did not confirm, return to refine_requirements for more adjustments
                session.conversation_stage = 'refine_requirements'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                return jsonify({
                    **resp_base,
                    'kind': 'text',
                    'ai_response': 'Sem confirmação. Posso ajustar mais algo? (diga o que mudar ou "pode seguir" quando estiver pronto)',
                    'message': 'Sem confirmação. Posso ajustar mais algo? (diga o que mudar ou "pode seguir" quando estiver pronto)',
                    'conversation_stage': session.conversation_stage
                })
        
        # GUARDRAIL: Handle suggest_requirements and refine_requirements stages with state machine
        if session.conversation_stage in ['suggest_requirements', 'refine_requirements', 'review_requirements']:
            from domain.usecase.etp.requirements_interpreter import parse_update_command, aplicar_comando
            
            current_requirements = session.get_requirements()
            command_result = parse_update_command(user_message, current_requirements)
            
            print(f"🔹 Comando parseado: {command_result}")
            
            # Check if user confirmed using state machine validation
            user_confirmed = is_user_confirmed(user_message)
            print(f"🔹 [STATE_MACHINE] user_confirmed={user_confirmed}")
            
            # Ramo explícito de confirmação - GUARDRAIL: only transition with user_confirmed = true
            if command_result and command_result.get('intent') == 'confirm':
                if not user_confirmed:
                    # Should not happen as 'confirm' intent means confirmation detected, but be safe
                    return jsonify({
                        **resp_base,
                        'kind': 'text',
                        'ai_response': 'Para confirmar os requisitos, use palavras como: "ok", "confirmo", "pode seguir", "aceito", "concordo".',
                        'message': 'Para confirmar os requisitos, use palavras como: "ok", "confirmo", "pode seguir", "aceito", "concordo".',
                        'conversation_stage': session.conversation_stage
                    })
                
                # GUARDRAIL: Validate state transition to confirm_requirements
                next_state = 'confirm_requirements'
                is_valid, error_msg = validate_state_transition(session.conversation_stage, next_state, user_confirmed)
                
                if not is_valid:
                    print(f"🔸 [STATE_MACHINE] Transição inválida: {error_msg}")
                    return jsonify({
                        **resp_base,
                        'kind': 'text',
                        'ai_response': f"Não é possível confirmar agora: {error_msg}",
                        'message': f"Não é possível confirmar agora: {error_msg}",
                        'conversation_stage': session.conversation_stage
                    })
                
                # User confirmed - now transition to solution_path (not confirm_requirements)
                # The issue specifies: do not ask "Confirmo gerar o ETP" after requirements
                # Instead, move directly to solution_path
                session.conversation_stage = 'solution_path'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                # Gerar transição em prosa natural
                next_question = _generate_prose_transition('confirm_to_solution_path', {'necessity': session.necessity})
                if not next_question:
                    next_question = "Certo. Vamos identificar a melhor forma de atender essa necessidade."
                
                return jsonify({
                    'success': True,
                    'kind': 'text',
                    'ai_response': next_question,
                    'message': next_question,
                    'conversation_stage': session.conversation_stage,
                    'session_id': session.session_id
                })
            
            if command_result['intent'] == 'ask':
                # User asked a question - provide helpful context about requirements
                return jsonify({
                    **resp_base,
                    'kind': 'text',
                    'ai_response': 'Estamos revisando os requisitos. Se algo não faz sentido ou falta algo importante, me avise que ajusto. Quando estiver adequado, confirme para seguirmos.',
                    'message': 'Estamos revisando os requisitos. Se algo não faz sentido ou falta algo importante, me avise que ajusto. Quando estiver adequado, confirme para seguirmos.',
                    'conversation_stage': session.conversation_stage
                })
            
            if command_result['intent'] == 'restart_necessity':
                # Reset session to collect new necessity
                session.necessity = None
                session.conversation_stage = 'collect_need'
                session.set_requirements([])
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                return jsonify({
                    **resp_base,
                    'kind': 'text',
                    'ai_response': 'Entendido. Vamos recomeçar. Qual é a nova necessidade da contratação?',
                    'message': 'Entendido. Vamos recomeçar. Qual é a nova necessidade da contratação?',
                    'conversation_stage': 'collect_need'
                })
            
            elif command_result['intent'] in ['remove', 'edit', 'add', 'keep_only', 'reorder']:
                # PASSO 3: Apply the command to requirements with stable renumbering
                aplicar_comando(command_result, session, session.necessity)
                
                # Handle combo commands (e.g., remove + add)
                if command_result.get('_combo_add'):
                    for add_item in command_result['_combo_add']:
                        add_cmd = {
                            'intent': 'add',
                            'items': [add_item.get('text', '')],
                            'message': f'Adicionando: {add_item.get("text", "")}'
                        }
                        aplicar_comando(add_cmd, session, session.necessity)
                
                # GUARDRAIL: Stay in refine_requirements stage (loop allowed)
                session.conversation_stage = 'refine_requirements'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                # PASSO 6: Return with unified contract - natural messages per action type
                updated_requirements = session.get_requirements()
                intent = command_result['intent']
                if intent == 'remove':
                    msg = "Removi. Veja como ficou a lista atualizada e me diga se ajusto mais algo ou se posso seguir."
                elif intent == 'edit':
                    msg = "Perfeito. Atualizei e já deixei a lista abaixo com a mudança aplicada. Sigo ajustando?"
                elif intent == 'add':
                    msg = "Incluído. A lista abaixo já reflete o novo item. Ajusto mais algo?"
                else:
                    msg = command_result.get('message') or 'Atualização aplicada. Veja a lista atualizada abaixo.'
                    msg += " Ajusto mais algo ou posso seguir?"
                
                return jsonify({
                    **resp_base,
                    'kind': 'requirements_update',
                    'necessity': session.necessity,
                    'requirements': updated_requirements,
                    'message': msg,
                    'ai_response': msg,
                    'conversation_stage': session.conversation_stage
                })
            
            # Usuário pediu "adicionar mais" mas sem conteúdo → ofereça candidatos
            if re.search(r'\b(adicione|adicionar|incluir|mais requisito|mais requisitos)\b', user_message, flags=re.I) and _is_uncertain(user_message):
                candidates = _suggest_requirements(session.necessity)
                pool = [c for c in candidates if c not in [r.get('text', '') for r in current_requirements]][:6]
                if pool:
                    lines = [f"{i+1}) {it}" for i,it in enumerate(pool)]
                    msg = "Sugestões para incluir. Responda com os **números** (ex.: \"1 e 3\"):\n" + "\n".join(lines)
                    ans = session.get_answers() or {}
                    ans['req_candidates'] = pool
                    session.set_answers(ans)
                    db.session.commit()
                    return jsonify({**resp_base,'message': msg,'requirements': current_requirements,'conversation_stage': 'refine_requirements'})
            
            # Seleção numérica ("inclui 1 e 3")
            ans = session.get_answers() or {}
            pool = ans.get('req_candidates') or []
            picks = _pick_numbers(user_message, len(pool)) if pool else []
            if picks:
                for p in picks:
                    new_id = f'R{len(current_requirements) + 1}'
                    current_requirements.append({'id': new_id, 'text': pool[p-1]})
                ans['req_candidates'] = []
                session.set_answers(ans)
                session.set_requirements(current_requirements)
                db.session.commit()
                return jsonify({**resp_base,'message': "Incluí os itens selecionados. Posso seguir?",'requirements': current_requirements,'conversation_stage': 'refine_requirements'})
            
            # GUARDRAIL: If intent is 'other' or 'unclear', use handle_other_intent
            if command_result['intent'] in ['other', 'unclear']:
                clarification = handle_other_intent()
                return jsonify({
                    **resp_base,
                    'kind': 'text',
                    'ai_response': clarification['ai_response'],
                    'message': clarification['message'],
                    'conversation_stage': session.conversation_stage
                })
            
            # Fallback for any other case
            return jsonify({
                **resp_base,
                'kind': 'text',
                'ai_response': 'Entendi parcialmente. Quer remover, trocar ou incluir algo?',
                'message': 'Entendi parcialmente. Quer remover, trocar ou incluir algo?',
                'conversation_stage': session.conversation_stage
            })

        # ORDEM das ETAPAS (sem auto-avanço):
        # solution_path -> pca -> legal_norms -> qty_value -> installment -> summary -> gerar
        if session.conversation_stage == 'solution_path':
            ans = session.get_answers() or {}
            text = user_message.strip()
            
            # Check if user is asking for help
            if any(k in user_message.lower() for k in ['ajuda', 'me ajude', 'me ajuda', 'como', 'não sei', 'qual escolher']):
                help_msg = _consult_path_explainer(session.necessity)[0]
                return jsonify({**resp_base, 'message': help_msg, 'conversation_stage': 'solution_path'})
            
            # Check if already have a tentative choice waiting for approval
            if ans.get('solution_path_tentative'):
                # User is responding to confirmation request
                if _is_confirm(user_message) or _yes(user_message):
                    # Approved - advance to pca
                    chosen = ans['solution_path_tentative']
                    ans['solution_path'] = chosen
                    ans['solution_justification'] = f"Decisão tomada com base na análise e aderência da alternativa '{chosen}' à necessidade."
                    session.set_answers(ans)
                    session.conversation_stage = 'pca'
                    session.updated_at = datetime.utcnow()
                    db.session.commit()
                    
                    pca_msg = _generate_prose_transition('solution_path_to_pca', {'chosen': chosen})
                    if not pca_msg:
                        pca_msg = f"Certo, vamos com {chosen}. Sobre o planejamento anual: já existe previsão para isso no PCA?"
                    
                    return jsonify({**resp_base,'message': pca_msg, 'conversation_stage': 'pca'})
                else:
                    # User wants to reconsider - clear tentative and show options again
                    ans.pop('solution_path_tentative', None)
                    session.set_answers(ans)
                    db.session.commit()
                    msg_ctx, _ = _consult_path_explainer(session.necessity)
                    return jsonify({**resp_base,'message': msg_ctx,'conversation_stage': 'solution_path'})
            
            # No tentative choice yet - parse user's selection
            msg_ctx, options = _consult_path_explainer(session.necessity)
            choice_kw = _any_in(user_message, options)
            picks = _pick_numbers(user_message, len(options))
            
            if _is_uncertain(user_message) or (not choice_kw and not picks):
                # User didn't pick anything - show options
                return jsonify({**resp_base,'message': msg_ctx,'conversation_stage': 'solution_path'})
            
            # User picked something - save tentatively and ask for confirmation
            chosen = choice_kw or options[picks[0]-1]
            
            # Guardar TODAS as alternativas (para o estudo final)
            analysis_lines = [l for l in msg_ctx.splitlines() if re.match(r'^\d+\)', l)]
            parsed = []
            for line in analysis_lines:
                try:
                    _, rest = line.split(')', 1)
                    name, desc = rest.strip().split('—', 1)
                    parsed.append({'opcao': name.strip(), 'analise': desc.strip()})
                except Exception:
                    pass
            ans['solution_options'] = parsed
            ans['solution_path_tentative'] = chosen
            session.set_answers(ans)
            db.session.commit()
            
            # Ask for confirmation
            confirm_msg = f"Entendi que você escolheu: {chosen}. Posso seguir com essa opção para o PCA?"
            return jsonify({**resp_base,'message': confirm_msg,'conversation_stage': 'solution_path'})

        if session.conversation_stage == 'pca':
            ans = session.get_answers() or {}
            
            # ENHANCED: Check if user is requesting PCA construction
            user_lower = user_message.lower()
            pca_build_keywords = ['monta um pca', 'faça o pca', 'criar pca', 'gerar pca', 'construir pca', 'monte um pca']
            is_pca_request = any(kw in user_lower for kw in pca_build_keywords)
            
            # Check for "what is PCA" questions
            if any(phrase in user_lower for phrase in ['o que é pca', 'o que e pca', 'como faz pca', 'como fazer pca']):
                explanation = """O PCA (Plano de Contratações Anual) é o documento que registra todas as contratações previstas do órgão para o ano. Ele deve conter:
- Objetivos e metas institucionais
- Funções de despesa
- Vínculo com PPA/LDO
- Motivos das contratações planejadas

Se não tiver um PCA pronto, posso montar um rascunho básico para você. Quer que eu faça isso?"""
                return jsonify({**resp_base, 'message': explanation, 'conversation_stage': 'pca'})
            
            # If user doesn't have PCA and requests to build one
            if is_pca_request or (any(kw in user_lower for kw in ['não tenho', 'nao tenho', 'não possuo']) and 'pca' in user_lower):
                # Generate PCA draft
                necessity = session.necessity or "contratação descrita"
                solution_path = ans.get('solution_path', 'solução escolhida')
                
                pca_draft = f"""Rascunho de PCA para {necessity}:

**Objetivos e Metas:**
- Atender à necessidade de {necessity}
- Garantir qualidade e conformidade na prestação
- Assegurar continuidade operacional

**Função de Despesa:** 
- Classificar conforme natureza (investimento/custeio)

**Vínculo PPA/LDO:**
- Alinhar com programa/ação do Plano Plurianual
- Confirmar previsão orçamentária na LDO

**Motivos principais:**
- Contratação necessária para {solution_path}
- Requisitos técnicos validados
- Estimativa de recursos a definir

Posso usar este rascunho de PCA para seguirmos?"""
                
                ans['pca_draft_offered'] = pca_draft
                session.set_answers(ans)
                db.session.commit()
                
                return jsonify({**resp_base, 'message': pca_draft, 'conversation_stage': 'pca'})
            
            # If we offered a draft and user is confirming
            if ans.get('pca_draft_offered') and (_is_confirm(user_message) or _yes(user_message)):
                pca_value = ans['pca_draft_offered']
                ans['pca'] = pca_value
                ans.pop('pca_draft_offered', None)
                session.set_answers(ans)
                session.conversation_stage = 'legal_norms'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                legal_msg = _generate_prose_transition('pca_to_legal_norms', {'pca_response': 'PCA estruturado'})
                if not legal_msg:
                    legal_msg = "Ótimo! Sobre as normas legais: costumamos usar a Lei 14.133/21 como base, junto com o regulamento local aplicável. Se houver algo específico do setor ou proteção de dados envolvida, podemos incluir. O que faz sentido para você?"
                
                return jsonify({**resp_base, 'message': legal_msg, 'conversation_stage': 'legal_norms'})
            
            # Detectar se usuário precisa de ajuda ou está incerto
            if _is_uncertain(user_message) or any(k in user_lower for k in ['ajuda', 'como', 'não sei']):
                # Usuário não tem informação ou precisa de orientação
                help_msg = "O PCA (Plano de Contratações Anual) lista as compras previstas do órgão. Se ainda não constar, é bom registrar essa demanda junto ao setor de planejamento antes de seguir. Ou se preferir, posso montar um rascunho básico de PCA para você. O que prefere?"
                return jsonify({**resp_base, 'message': help_msg, 'conversation_stage': 'pca'})
            
            # Verificar confirmação explícita
            if not _is_confirm(user_message) and not _yes(user_message):
                # Usuário deu resposta mas não confirmou - salvar e pedir confirmação
                ans['pca_tentative'] = user_message
                session.set_answers(ans)
                db.session.commit()
                confirm_msg = f"Entendi que sobre o PCA: {user_message}. Posso registrar assim e seguir para as normas legais?"
                return jsonify({**resp_base, 'message': confirm_msg, 'conversation_stage': 'pca'})
            
            # Confirmação explícita - avançar
            pca_value = ans.get('pca_tentative', user_message)
            ans['pca'] = pca_value
            session.set_answers(ans)
            session.conversation_stage = 'legal_norms'
            session.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Gerar transição em prosa natural
            legal_msg = _generate_prose_transition('pca_to_legal_norms', {'pca_response': pca_value})
            if not legal_msg:
                legal_msg = "Entendido. Sobre as normas legais: costumamos usar a Lei 14.133/21 como base, junto com o regulamento local aplicável. Se houver algo específico do setor ou proteção de dados envolvida, podemos incluir. O que faz sentido para você?"
            
            return jsonify({**resp_base, 'message': legal_msg, 'conversation_stage': 'legal_norms'})

        if session.conversation_stage == 'legal_norms':
            ans = session.get_answers() or {}
            # Detectar ajuda
            if any(k in user_message.lower() for k in ['ajuda', 'como', 'não sei', 'quais', 'me ajuda']):
                help_msg = "As principais são: 1) Lei 14.133/2021 (nova lei de licitações), 2) Regulamento/Decreto local do seu ente, 3) LGPD se houver dados pessoais, 4) Normas técnicas do setor (ex: ABNT, vigilância sanitária). Você pode escolher por número ou me dizer quais aplicam ao seu caso. Te parece bom assim?"
                return jsonify({**resp_base, 'message': help_msg, 'conversation_stage': 'legal_norms'})
            
            # Parse resposta
            picks = _pick_numbers(user_message, 4)
            if picks:
                mapping = {1:"Lei 14.133/2021", 2:"Regulamento/Decreto local", 3:"LGPD", 4:"Normas técnicas/regulatórias do setor"}
                tentative_norms = ', '.join(mapping[i] for i in picks)
            elif _is_uncertain(user_message):
                tentative_norms = "Lei 14.133/2021; Regulamento local; (demais a confirmar)"
            else:
                tentative_norms = user_message
            
            # Verificar confirmação
            if not _is_confirm(user_message) and not _yes(user_message):
                ans['legal_norms_tentative'] = tentative_norms
                session.set_answers(ans)
                db.session.commit()
                confirm_msg = f"Entendi: {tentative_norms}. Posso seguir com essas normas?"
                return jsonify({**resp_base, 'message': confirm_msg, 'conversation_stage': 'legal_norms'})
            
            # Confirmado - avançar
            ans['legal_norms'] = ans.get('legal_norms_tentative', tentative_norms)
            session.set_answers(ans)
            session.conversation_stage = 'qty_value'
            session.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Gerar transição em prosa natural
            qty_msg = _generate_prose_transition('legal_norms_to_qty', {})
            if not qty_msg:
                qty_msg = "Certo. Sobre quantitativo e valor: dá para estimar por consumo recente, contratos similares ou pesquisa de mercado. Se preferir, pode me passar a unidade e ordem de grandeza que ajustamos depois."
            
            return jsonify({**resp_base, 'message': qty_msg, 'conversation_stage': 'qty_value'})

        if session.conversation_stage in ('qty_value', 'quantitativo_valor'):
            ans = session.get_answers() or {}
            # Detectar ajuda
            if any(k in user_message.lower() for k in ['ajuda', 'como', 'não sei', 'não tenho']):
                help_msg = "Você pode estimar baseado em: histórico de consumo, contratos anteriores, ou pesquisa de mercado. Se não tiver agora, pode indicar só a unidade (ex: 'por mês', 'por usuário') e ordem de grandeza. Quando tiver uma ideia, me passa e eu confirmo. Ok?"
                return jsonify({**resp_base, 'message': help_msg, 'conversation_stage': session.conversation_stage})
            
            # Parse resposta
            if _is_uncertain(user_message):
                tentative_qty = "A definir (estimativa pendente). Unidade/escopo a detalhar."
            else:
                tentative_qty = user_message
            
            # Verificar confirmação
            if not _is_confirm(user_message) and not _yes(user_message):
                ans['qty_value_tentative'] = tentative_qty
                session.set_answers(ans)
                db.session.commit()
                confirm_msg = f"Registrei: {tentative_qty}. Posso seguir para o parcelamento com essa informação?"
                return jsonify({**resp_base, 'message': confirm_msg, 'conversation_stage': session.conversation_stage})
            
            # Confirmado - avançar
            qty_value = ans.get('qty_value_tentative', tentative_qty)
            ans['qty_value'] = qty_value
            session.set_answers(ans)
            session.conversation_stage = 'installment'
            session.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Gerar transição em prosa natural
            installment_msg = _generate_prose_transition('qty_to_installment', {'qty_response': qty_value})
            if not installment_msg:
                installment_msg = "Entendido. Sobre parcelamento: dividir em lotes pode ampliar a competição e escalonar entregas; por outro lado, aumenta a logística. Pelo que descrevemos, faz sentido parcelar ou manter como item único?"
            
            return jsonify({**resp_base, 'message': installment_msg, 'conversation_stage': 'installment'})

        if session.conversation_stage == 'installment':
            ans = session.get_answers() or {}
            # Detectar ajuda
            if any(k in user_message.lower() for k in ['ajuda', 'como', 'não sei', 'me ajuda']):
                help_msg = "Parcelar pode aumentar a competição (mais empresas conseguem participar de lotes menores) e escalonar entregas. Mas também aumenta a gestão contratual. Se não souber agora, pode dizer 'a definir' e ajustamos depois. Te parece razoável?"
                return jsonify({**resp_base, 'message': help_msg, 'conversation_stage': 'installment'})
            
            # Parse resposta
            tentative_installment = "não" if _no(user_message) else ("sim" if _yes(user_message) else user_message)
            
            # Verificar confirmação
            if not _is_confirm(user_message) and tentative_installment not in ['sim', 'não']:
                ans['installment_tentative'] = tentative_installment
                session.set_answers(ans)
                db.session.commit()
                confirm_msg = f"Entendi: {tentative_installment}. Posso fechar assim e montar o resumo?"
                return jsonify({**resp_base, 'message': confirm_msg, 'conversation_stage': 'installment'})
            
            # Confirmado - avançar para resumo
            ans['installment'] = ans.get('installment_tentative', tentative_installment)
            session.set_answers(ans)
            
            # Monta RESUMO e só gera sob comando explícito
            resumo_lines = [
                f"Necessidade: {session.necessity}",
                "",
                "Análise de alternativas para atendimento:",
            ]
            # Traz todas as opções com análise
            opts = ans.get('solution_options') or []
            if opts:
                for i,o in enumerate(opts, start=1):
                    resumo_lines.append(f"  {i}) {o.get('opcao')}: {o.get('analise')}")
            else:
                resumo_lines.append("  (Alternativas registradas não disponíveis)")
            resumo_lines += [
                f"Opção escolhida: {ans.get('solution_path')} — {ans.get('solution_justification')}",
                "",
                f"PCA: {ans.get('pca')}",
                f"Normas legais: {ans.get('legal_norms')}",
                f"Quantitativo/Valor: {ans.get('qty_value')}",
                f"Parcelamento: {ans.get('installment')}",
                "",
                'Este é o resumo do que coletamos. Quando estiver pronto para gerar o documento, só me avisar.'
            ]
            resumo = "\n".join(resumo_lines)
            session.conversation_stage = 'summary'
            session.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({
                **resp_base,
                'message': resumo,
                'conversation_stage': 'summary'
            })

        # SUMMARY: Wait for explicit generation command
        # Geração do ETP (apenas quando o usuário pedir "pode gerar", "gerar etp", etc.)
        if session.conversation_stage == 'summary':
            lm = _normalize(user_message).lower()
            if any(k in lm for k in ["pode gerar","gerar etp","gera etp","ok gerar","gerar o etp"]):
                ans = session.get_answers() or {}
                prompt = (
                    f"Necessidade: {session.necessity}\n"
                    f"Análise de alternativas: {ans.get('solution_options')}\n"
                    f"Escolha: {ans.get('solution_path')} — {ans.get('solution_justification')}\n"
                    f"PCA: {ans.get('pca')}\n"
                    f"Normas legais: {ans.get('legal_norms')}\n"
                    f"Quantitativo/Valor: {ans.get('qty_value')}\n"
                    f"Parcelamento: {ans.get('installment')}\n"
                    "Redija uma seção de Estudo Técnico Preliminar clara e coerente, citando as alternativas "
                    "e justificando a decisão à luz da necessidade apresentada. Estruture em subtítulos."
                )
                try:
                    final_text = final_gen.generate(prompt)
                    return jsonify({**resp_base,
                                    'message': "Segue a versão para o ETP (prévia):\n\n" + final_text,
                                    'etp_preview': final_text,
                                    'conversation_stage': 'done'})
                except Exception:
                    return jsonify({**resp_base,
                                    'message': 'Não consegui gerar agora. Revise o resumo acima e tente "gerar etp" novamente. '
                                               'Seu progresso foi mantido.',
                                    'conversation_stage': 'summary'})

        # FASE: legal_norms (PCA)
        if session.conversation_stage == 'legal_norms':
            ans = session.get_answers() or {}
            pca = ans.get('pca') or {}
            out = parse_legal_norms(user_message, ans)

            if out['intent'] == 'pca_yes':
                pca.update({'present': True})
                ans['pca'] = pca
                session.set_answers(ans)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session,
                    'Ótimo. Há previsão no PCA. Informe número/ano/item se desejar. Quando terminar, diga "seguir".'))

            if out['intent'] == 'pca_details':
                pca.update({'details': out['payload']['raw']})
                ans['pca'] = pca
                session.set_answers(ans)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session,
                    'Detalhes do PCA registrados. Diga "seguir" para avançar para pesquisa de preços.'))

            if out['intent'] == 'pca_no':
                pca.update({'present': False})
                ans['pca'] = pca
                session.set_answers(ans)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session,
                    'Sem previsão no PCA. Registre o motivo, se houver, e diga "seguir" para avançar.'))

            if out['intent'] == 'pca_unknown':
                pca.update({'present': None})
                ans['pca'] = pca
                session.set_answers(ans)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session,
                    'Sem certeza sobre o PCA. Se descobrir depois, informe os detalhes. Diga "seguir" para avançar.'))

            if out['intent'] == 'proceed_next':
                session.conversation_stage = 'price_research'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session,
                    "Vamos à pesquisa de preços. Informe o método utilizado (ex.: painel de preços, cotações com fornecedores, histórico de contratos).",
                    {'conversation_stage': 'price_research'}))

            # unclear
            return jsonify(_text_payload(session,
                'Não captei a informação sobre o PCA. Diga "sim", "não", "não sei" ou forneça número/ano/item.'))

        # FASE: price_research
        if session.conversation_stage == 'price_research':
            ans = session.get_answers() or {}
            pr = ans.get('price_research') or {'method': None, 'supplier_count': None, 'evidence_links': []}
            out = parse_price_research(user_message, ans)

            if out['intent'] == 'method_select':
                pr['method'] = out['payload']['method']
                ans['price_research'] = pr
                session.set_answers(ans)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session, "Método registrado. Informe a quantidade de fornecedores consultados, se aplicável."))

            if out['intent'] == 'supplier_count':
                pr['supplier_count'] = out['payload']['count']
                ans['price_research'] = pr
                session.set_answers(ans)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session, 'Quantidade registrada. Caso tenha links de evidência, envie-os agora. Depois diga "concluído".'))

            if out['intent'] == 'link_evidence':
                pr['evidence_links'] = list(set((pr.get('evidence_links') or []) + out['payload']['urls']))
                ans['price_research'] = pr
                session.set_answers(ans)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session, 'Link registrado. Envie mais links se houver, ou diga "concluído".'))

            if out['intent'] == 'mark_done':
                ans['price_research'] = pr
                session.set_answers(ans)
                session.conversation_stage = 'legal_basis'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session, "Pesquisa de preços concluída. Agora, indique a base legal aplicável e eventuais observações.",
                                             {'conversation_stage': 'legal_basis'}))

            return jsonify(_text_payload(session, 'Você pode me passar o método usado, quantas fontes consultou, e os links. Quando tiver enviado tudo, é só avisar que concluiu.'))

        # FASE: legal_basis
        if session.conversation_stage == 'legal_basis':
            ans = session.get_answers() or {}
            lb = ans.get('legal_basis') or {'text': None, 'notes': []}
            out = parse_legal_basis(user_message, ans)

            if out['intent'] == 'legal_basis_set':
                lb['text'] = out['payload']['text']
                ans['legal_basis'] = lb
                session.set_answers(ans)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session, 'Base legal registrada. Se quiser, envie observações ou diga "finalizar".'))

            if out['intent'] == 'legal_basis_notes':
                lb['notes'] = list((lb.get('notes') or [])) + [out['payload']['text']]
                ans['legal_basis'] = lb
                session.set_answers(ans)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session, 'Observação registrada. Envie mais observações ou diga "finalizar".'))

            if out['intent'] == 'finalize':
                ans['legal_basis'] = lb
                session.set_answers(ans)
                session.conversation_stage = 'done'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify(_text_payload(session, "Coleta concluída. Podemos gerar o documento ou revisar se preferir.",
                                             {'conversation_stage': 'done'}))

            return jsonify(_text_payload(session, 'Envie a base legal, observações ou diga "finalizar".'))

        # PASSO 5: If no session necessity exists, we need to capture it
        if not session.necessity:
            # Try to analyze the need with etp_generator if available, otherwise just use the message
            need_description = None
            contains_need = False
            
            try:
                if etp_generator and hasattr(etp_generator, 'client'):
                    from domain.usecase.etp.utils_parser import analyze_need_safely
                    contains_need, need_description = analyze_need_safely(user_message, etp_generator.client)
                    print(f"🔹 [ANALYZER] contains_need={contains_need}, description='{need_description or 'None'}'")
                else:
                    # Fallback: assume the message is the necessity if it's long enough
                    if len(user_message.strip()) > 10:
                        contains_need = True
                        need_description = user_message.strip()
                        print(f"🔹 [ANALYZER FALLBACK] Usando mensagem como necessidade: {need_description}")
            except Exception as e:
                # If analysis fails, use the message as necessity
                print(f"🔸 [ANALYZER ERROR] {e} - usando fallback")
                if len(user_message.strip()) > 10:
                    contains_need = True
                    need_description = user_message.strip()

            if contains_need and need_description:
                print(f"🔹 [LOCK] Necessidade identificada e travada: {need_description}")
                
                # GUARDRAIL: LOCK NECESSITY and advance to suggest_requirements
                # After suggest_requirements, ALWAYS go to refine_requirements (mandatory state flow)
                session.necessity = need_description
                session.conversation_stage = 'suggest_requirements'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                print(f"🔹 [DEPOIS] Sessão: {session.session_id}, estágio: {session.conversation_stage}")

                # GUARDRAIL: Validate generator exists before generating requirements
                gen = _get_simple_generator()
                is_valid, error_msg = validate_generator_exists(gen)
                
                if not is_valid:
                    print(f"🔸 [GENERATOR ERROR] {error_msg}")
                    # Return controlled error without changing state
                    error_response = handle_http_error(500, error_msg, session.conversation_stage)
                    return jsonify({
                        **resp_base,
                        **error_response
                    })
                
                # Generate requirements using the simple generator with FALLBACK (NEVER 500)
                try:
                    suggested = gen.suggest_requirements(need_description)
                    origin = gen.__class__.__name__
                    print(f"🔹 [GENERATOR] Usando {origin} para gerar requisitos")
                except Exception as e:
                    # GUARDRAIL: Handle HTTP error without changing state
                    print(f"🔸 [GENERATOR ERROR] {e} - usando fallback explícito")
                    traceback.print_exc()
                    # Use FallbackGenerator
                    try:
                        origin = "FallbackGenerator"
                        suggested = FallbackGenerator().suggest_requirements(need_description)
                    except Exception as fallback_error:
                        # If even fallback fails, return controlled error
                        error_response = handle_http_error(500, str(fallback_error), session.conversation_stage)
                        return jsonify({
                            **resp_base,
                            **error_response
                        })
                
                # Convert simple list to structured format
                structured_requirements = []
                for i, req_text in enumerate(suggested, 1):
                    structured_requirements.append({
                        'id': f'R{i}',
                        'text': req_text,
                        'justification': 'Requisito sugerido pelo sistema'
                    })
                
                # Store requirements in session
                session.set_requirements(structured_requirements)
                
                # GUARDRAIL: After suggest_requirements, ALWAYS go to refine_requirements
                session.conversation_stage = get_next_state_after_suggestion(session.conversation_stage)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                print(f"🔹 [STATE_MACHINE] Transição: suggest_requirements → {session.conversation_stage}")
                
                # REQUIREMENT 4: Generate unified single-message response with contextual intro and rationale
                # Build contextual intro based on necessity
                necessity_lower = need_description.lower()
                if 'seguranç' in necessity_lower or 'vigilân' in necessity_lower:
                    intro_paragraph = "Faz sentido o que você descreveu. Essa necessidade tem impacto direto na segurança e conformidade, então vou organizar os requisitos de forma objetiva."
                elif 'manutençã' in necessity_lower or 'conservaçã' in necessity_lower:
                    intro_paragraph = "Entendi. A manutenção preventiva e o acompanhamento técnico são essenciais para garantir a continuidade operacional. Organizei os requisitos pensando nisso."
                elif 'tecnologi' in necessity_lower or 'sistema' in necessity_lower or 'software' in necessity_lower:
                    intro_paragraph = "Perfeito. Para uma contratação de tecnologia, precisamos requisitos que garantam entrega técnica, suporte adequado e segurança da informação. Veja o que pensei."
                elif 'consultor' in necessity_lower or 'assessor' in necessity_lower:
                    intro_paragraph = "Entendi sua demanda. Para consultoria especializada, os requisitos precisam focar em qualificação técnica, experiência comprovada e metodologia clara. Aqui estão."
                else:
                    intro_paragraph = "Faz sentido o que você descreveu. Essa necessidade precisa de requisitos que garantam qualidade, conformidade e continuidade da prestação. Vou detalhar."
                
                # Build numbered list
                req_list_text = "\n".join([f"{i}. {req['text']}" for i, req in enumerate(structured_requirements, 1)])
                
                # Build contextual rationale
                if 'seguranç' in necessity_lower or 'vigilân' in necessity_lower:
                    rationale_paragraph = "Escolhi esses pontos porque estruturam capacidade técnica, conformidade regulatória e operação contínua. Isso reduz risco de segurança e garante aderência legal."
                elif 'manutençã' in necessity_lower or 'conservaçã' in necessity_lower:
                    rationale_paragraph = "Esses requisitos cobrem experiência técnica, disponibilidade de equipe e insumos, e continuidade do serviço. Isso minimiza paradas não planejadas e mantém a infraestrutura funcionando."
                elif 'tecnologi' in necessity_lower or 'sistema' in necessity_lower or 'software' in necessity_lower:
                    rationale_paragraph = "Os requisitos focam em competência técnica comprovada, suporte ativo, segurança da informação e escalabilidade. Isso garante entrega funcional e reduz riscos de descontinuidade tecnológica."
                else:
                    rationale_paragraph = "Escolhi esses pontos porque estruturam competência comprovada, capacidade técnica e operação contínua com aderência regulatória. Isso amarra a prestação do serviço sem lacunas e reduz risco de entrega e de conformidade."
                
                # Combine all parts
                ai_response = (
                    f"{intro_paragraph}\n\n"
                    f"{req_list_text}\n\n"
                    f"{rationale_paragraph}\n\n"
                    f"Se quiser ajustar algo, diga no seu jeito mesmo e eu já refaço."
                )
                
                # PASSO 6: Return with unified contract (ALWAYS SUCCESS)
                # Return refine_requirements stage (not suggest_requirements)
                return jsonify({
                    **resp_base,
                    "kind": "requirements_suggestion", 
                    "necessity": session.necessity,
                    "requirements": structured_requirements,
                    "intro_paragraph": intro_paragraph,
                    "rationale_paragraph": rationale_paragraph,
                    "ai_response": ai_response,
                    "message": ai_response,
                    "conversation_stage": session.conversation_stage  # Will be refine_requirements
                })
            
            # PASSO 5: If necessity not detected, ask for it
            print(f"🔹 [NO_LOCK] contains_need=False ou parse falhou → pedindo necessidade")
            return jsonify({
                **resp_base,
                'kind': 'text',
                'ai_response': 'Olá! Para começar o ETP, preciso entender a necessidade. Qual é a descrição da necessidade da contratação?',
                'message': 'Olá! Para começar o ETP, preciso entender a necessidade. Qual é a descrição da necessidade da contratação?',
                'conversation_stage': 'collect_need'
            })

        # If we have a necessity but no clear command was processed, use LLM with updated prompts
        # This handles cases where the command parser returned 'unclear'
        if session.conversation_stage in ['suggest_requirements', 'review_requirements']:
            system_content = f"""Você é um especialista em licitações que está ajudando a revisar requisitos para um Estudo Técnico Preliminar (ETP).

IMPORTANTE: Você está na fase de revisão de requisitos. A necessidade já está definida: {session.necessity}

JAMAIS trate mensagens como "ajuste o último", "remover 2", "trocar 3" como nova necessidade. Apenas atualize a lista existente.

Foque apenas em:
- Confirmar requisitos apresentados
- Processar ajustes específicos solicitados
- Adicionar novos requisitos
- Remover requisitos específicos

A necessidade está TRAVADA e não deve ser alterada."""
        
        # Continue with normal LLM processing for other stages
        system_content = f"""Você é um especialista em licitações que está ajudando a coletar informações para um Estudo Técnico Preliminar (ETP).

Necessidade já capturada: {session.necessity}

Seu objetivo é conduzir uma conversa natural e fluida para coletar as seguintes informações obrigatórias:
1. Descrição da necessidade da contratação ✓ (já coletada)
2. Confirmação dos requisitos sugeridos ✓ (já processada) 
3. Se há previsão no PCA (Plano de Contratações Anual)
4. Quais normas legais pretende utilizar
5. Qual o quantitativo e valor estimado
6. Se haverá parcelamento da contratação

Mantenha o tom conversacional e profissional. Faça uma pergunta por vez.
Não repita informações já coletadas."""

        # Build conversation context
        messages = [{"role": "system", "content": system_content}]
        
        # Add conversation history
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            role = "user" if msg.get('sender') == 'user' else "assistant"
            messages.append({"role": role, "content": msg.get('text', '')})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})

        # Generate response - ensure client is initialized
        if not etp_generator or not hasattr(etp_generator, 'client') or not etp_generator.client:
            # Fallback: use get_llm_client() helper
            client = get_llm_client()
            if not client:
                return jsonify({
                    **resp_base,
                    'kind': 'text',
                    'ai_response': 'Erro: cliente OpenAI não inicializado. Verifique a configuração.',
                    'message': 'Erro: cliente OpenAI não inicializado. Verifique a configuração.',
                    'conversation_stage': session.conversation_stage
                })
        else:
            client = etp_generator.client
        
        model_name = get_model_name()
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=800,
            temperature=0.7
        )

        ai_response = response.choices[0].message.content.strip()

        # PASSO 6: Return with unified contract
        return jsonify({
            **resp_base,
            'kind': 'text',
            'ai_response': ai_response,
            'message': ai_response,
            'conversation_stage': session.conversation_stage
        })

    except Exception as e:
        print(f"🔸 Erro na conversa: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro na conversa: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/confirm-requirements', methods=['POST'])
@cross_origin()
def confirm_requirements():
    """Processa a confirmação, ajuste ou rejeição de requisitos pelo usuário"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        # PASSO 8: Reutilizar session_id corretamente
        data = request.get_json(force=True)
        sid = (data.get("session_id") or "").strip() or None
        session = EtpSession.query.filter_by(session_id=sid).first() if sid else None
        
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
            
        # PASSO 8: Base de resposta com session_id
        resp_base = {"success": True, "session_id": session.session_id}
        
        user_action = data.get('action', '')  # 'accept', 'modify', 'add', 'remove'
        requirements = data.get('requirements', [])
        user_message = data.get('message', '')

        # Standardize the next question for consistent flow
        next_question = "👉 **Agora, há previsão no PCA (Plano de Contratações Anual)?**"
        
        # Processar a ação do usuário
        if user_action == 'accept':
            # Usuário aceitou todos os requisitos
            confirmed_requirements = requirements
            ai_response = f"**Perfeito! Requisitos confirmados.**\n\n{next_question}"
            print(f"🔹 Usuário aceitou os requisitos: {len(confirmed_requirements)} requisitos confirmados")

        elif user_action == 'modify':
            # Usuário quer modificar alguns requisitos
            print(f"🔹 Usuário solicitou modificação nos requisitos: {user_message}")
            modify_prompt = f"""
            O usuário quer modificar os requisitos sugeridos. Processe a solicitação:

            Requisitos originais: {requirements}
            Solicitação do usuário: "{user_message}"

            Retorne APENAS um JSON com:
            - "updated_requirements": array com requisitos atualizados
            - "explanation": breve explicação das mudanças feitas
            """

            # Ensure client is initialized
            if not etp_generator or not hasattr(etp_generator, 'client') or not etp_generator.client:
                client = get_llm_client()
                if not client:
                    # Fallback: keep original requirements
                    confirmed_requirements = requirements
                    ai_response = f"**Mantive os requisitos originais.** Cliente não inicializado.\n\n{next_question}"
                    # Skip the LLM call
                    response = None
            else:
                client = etp_generator.client
            
            if client:
                model_name = get_model_name()
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "Você é um especialista em requisitos técnicos para licitações."},
                        {"role": "user", "content": modify_prompt}
                    ],
                    max_tokens=800,
                    temperature=0.7
                )

            # PASSO 5: Parse response safely
            if response:
                from domain.usecase.etp.utils_parser import parse_json_relaxed
                modification_result = parse_json_relaxed(response.choices[0].message.content.strip())
                
                if modification_result and 'updated_requirements' in modification_result:
                    confirmed_requirements = modification_result['updated_requirements']
                    explanation = modification_result.get('explanation', 'Requisitos atualizados conforme solicitado.')
                    ai_response = f"**Requisitos atualizados!**\n\n{explanation}\n\n{next_question}"
                else:
                    # Fallback if parsing fails
                    confirmed_requirements = requirements
                    ai_response = f"**Mantive os requisitos originais.** Não consegui processar a modificação solicitada.\n\n{next_question}"
            # else: confirmed_requirements and ai_response already set in the fallback above

        else:
            # Ação não reconhecida - manter requisitos originais
            confirmed_requirements = requirements
            ai_response = f"**Requisitos mantidos.**\n\n{next_question}"

        # Armazenar requisitos confirmados na sessão
        answers = session.get_answers()
        answers['confirmed_requirements'] = confirmed_requirements
        session.set_answers(answers)
        session.updated_at = datetime.utcnow()

        db.session.commit()

        # PASSO 8: Não retroceder estágio - manter em review_requirements ou avançar
        if user_action == 'accept':
            session.conversation_stage = 'legal_norms'  # Avançar para próxima fase
        else:
            session.conversation_stage = 'review_requirements'  # Manter em revisão
        
        session.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            **resp_base,
            'kind': 'requirements_confirmed',
            'confirmed_requirements': confirmed_requirements,
            'ai_response': ai_response,
            'message': ai_response,
            'conversation_stage': session.conversation_stage
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao confirmar requisitos: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/suggest-requirements', methods=['POST'])
@cross_origin()
def suggest_requirements():
    """Sugere requisitos baseados na necessidade identificada"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        data = request.get_json()
        necessity = data.get('necessity', '').strip()

        if not necessity:
            return jsonify({'error': 'Necessidade é obrigatória'}), 400

        # Usar RAG para encontrar requisitos similares
        rag_results = search_requirements("generic", necessity, k=5)
        
        # Gerar requisitos no formato R# — descrição (sem justificativas)
        requirements_prompt = f"""
        Baseado na necessidade: "{necessity}"
        
        E nos seguintes exemplos de requisitos similares:
        {json.dumps(rag_results, indent=2)}
        
        Gere uma lista de 3-5 requisitos específicos e objetivos para esta contratação.
        
        FORMATO OBRIGATÓRIO:
        Retorne APENAS uma lista de requisitos no formato:
        R1 — <descrição do requisito em uma única linha>
        R2 — <descrição do requisito em uma única linha>
        R3 — <descrição do requisito em uma única linha>
        
        REGRAS ESTRITAS:
        - NÃO inclua justificativas, explicações ou qualquer texto adicional
        - Cada linha deve começar com R seguido de número, espaço, travessão — e espaço
        - Cada requisito em uma única linha
        - Sem bullets, asteriscos, numeração dupla, tabelas ou JSON
        - Requisitos devem ser específicos e verificáveis
        
        Retorne SOMENTE as linhas no formato R# — descrição, nada mais.
        """
        
        model_name = get_model_name()
        response = etp_generator.client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Você é um especialista em licitações que gera requisitos técnicos precisos no formato R# — descrição, sem justificativas."},
                {"role": "user", "content": requirements_prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        # Parse response in R# — format
        result_raw = response.choices[0].message.content.strip()
        
        # Parse requirements from R# — format
        requirements = []
        for line in result_raw.split('\n'):
            line = line.strip()
            if line and (line.startswith('R') or (line and line[0].isdigit())):
                requirements.append(line)
        
        # Fallback if no requirements were parsed
        if not requirements:
            requirements = [
                f"R1 — Requisitos técnicos específicos para {necessity.lower()}",
                "R2 — Especificações técnicas adequadas ao objeto da contratação",
                "R3 — Comprovação de capacidade técnica adequada"
            ]

        return jsonify({
            'success': True,
            'requirements': requirements,
            'message': 'Requisitos sugeridos baseados na necessidade identificada e na base de conhecimento.',
            'necessity': necessity,
            'rag_sources': len(rag_results),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao sugerir requisitos: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/analyze-response', methods=['POST'])
@cross_origin()
def analyze_response_stub():
    return jsonify({'error': 'Rota removida. Use POST /api/etp-dynamic/conversation'}), 404

@etp_dynamic_bp.route('/generate-document', methods=['POST'])
@cross_origin()
def generate_document():
    data = request.get_json(silent=True) or {}
    sid = (data.get("session_id") or "").strip() or None
    if not sid:
        return jsonify({'success': False, 'error': 'session_id ausente'}), 400
    session = EtpSession.query.filter_by(session_id=sid).first()
    if not session:
        return jsonify({'success': False, 'error': 'Sessão não encontrada'}), 404
    
    # Check if user has confirmed requirements
    answers = session.get_answers() or {}
    user_confirmed = answers.get('user_confirmed_requirements', False)
    
    if not user_confirmed and session.conversation_stage in ['suggest_requirements', 'review_requirements']:
        return jsonify({
            'success': False,
            'error': 'Os requisitos precisam ser confirmados antes de gerar o documento.',
            'message': 'Por favor, confirme os requisitos antes de gerar o ETP.',
            'kind': 'confirmation_required',
            'conversation_stage': session.conversation_stage
        }), 400
    
    # Compor e renderizar
    doc_json = compose_etp_document(session)
    html = render_etp_html(doc_json)
    etp_doc = EtpDocument(session_id=sid, doc_json=doc_json, html=html)
    db.session.add(etp_doc); db.session.commit()
    return jsonify(_text_payload(session, f"Perfeito. Requisitos confirmados. Vou gerar o ETP com base neles.\n\nDocumento gerado com sucesso (ID: {etp_doc.id}).",
                                 {'doc_id': etp_doc.id, 'kind': 'doc_generated'}))

@etp_dynamic_bp.route('/document/<int:doc_id>/html', methods=['GET'])
@cross_origin()
def get_document_html(doc_id: int):
    etp_doc = EtpDocument.query.get(doc_id)
    if not etp_doc:
        return jsonify({'success': False, 'error': 'Documento não encontrado'}), 404
    return jsonify({'success': True, 'doc_id': etp_doc.id, 'html': etp_doc.html})

@etp_dynamic_bp.route('/document/<int:doc_id>/download-docx', methods=['GET'])
@cross_origin()
def download_docx(doc_id: int):
    etp_doc = EtpDocument.query.get(doc_id)
    if not etp_doc:
        return jsonify({'success': False, 'error': 'Documento não encontrado'}), 404
    d = DocxDocument()
    d.add_heading(etp_doc.doc_json.get('title', 'Documento'), level=1)
    for s in etp_doc.doc_json.get('sections', []):
        d.add_heading(s.get('title', ''), level=2)
        if s.get('content'):
            d.add_paragraph(str(s['content']))
        if s.get('items'):
            for it in s['items']:
                d.add_paragraph(f"- {it}")
        for key in ['details', 'method', 'supplier_count']:
            if s.get(key) is not None:
                d.add_paragraph(f"{key}: {s.get(key)}")
        if s.get('evidence_links'):
            d.add_paragraph("Evidências:")
            for link in s['evidence_links']:
                d.add_paragraph(f"* {link}")
        if s.get('notes'):
            d.add_paragraph("Observações:")
            for note in s['notes']:
                d.add_paragraph(f"* {note}")
    buf = BytesIO()
    d.save(buf); buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"ETP_{etp_doc.session_id}_{etp_doc.id}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

@etp_dynamic_bp.route('/regen-requirements', methods=['POST'])
@cross_origin()
def regen_requirements():
    """
    Regenerate requirements when frontend detects empty requirements list.
    Uses corrective prompt to ensure valid output.
    
    Request JSON:
    {
        "conversation_id": "<uuid>",
        "stage": "collect_need" | "refine"
    }
    
    Response JSON:
    {
        "success": true,
        "intro": "...",
        "requirements": ["1. ...", "2. ..."],
        "justification": "..."
    }
    """
    try:
        data = request.get_json()
        conversation_id = data.get('conversation_id')
        stage = data.get('stage', 'collect_need')
        
        if not conversation_id:
            return jsonify({'success': False, 'error': 'conversation_id é obrigatório'}), 400
        
        # Load conversation
        conv = ConversationRepo.get(conversation_id)
        if not conv:
            return jsonify({'success': False, 'error': 'Conversa não encontrada'}), 404
        
        # Get session
        session = EtpSession.query.filter_by(session_id=str(conversation_id)).first()
        if not session:
            return jsonify({'success': False, 'error': 'Sessão não encontrada'}), 404
        
        necessity = session.necessity or "contratação"
        
        # Build history
        history = []
        try:
            messages = MessageRepo.list_for_conversation(conversation_id) or []
        except Exception:
            messages = []
        for msg in messages[-10:]:
            history.append({'role': msg.role, 'content': msg.content})
        
        # Get RAG context
        from rag.retrieval import retrieve_for_stage
        from application.ai.generator import generate_answer
        
        context_chunks = retrieve_for_stage(necessity, stage, k=12)
        
        rag_context = {
            'chunks': context_chunks,
            'necessity': necessity,
            'requirements': session.get_requirements() or []
        }
        
        # Regenerate with corrective prompt embedded in generate_answer
        result = generate_answer(stage, history, necessity, rag_context)
        
        # Update session with regenerated requirements
        requirements = result.get('requirements', [])
        if requirements:
            session.set_requirements(requirements)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'intro': result.get('intro', ''),
            'requirements': requirements,
            'justification': result.get('justification', '')
        })
        
    except Exception as e:
        logger.error(f"[REGEN_REQ] Error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro ao regenerar requisitos: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/admin/repair-answers', methods=['POST'])
@cross_origin()
def repair_answers():
    """
    Endpoint de manutenção para normalizar sessões antigas com answers como string.
    Percorre todas as sessões e força a normalização via get_answers().
    """
    try:
        fixed_count = 0
        for session in EtpSession.query.all():
            before = session.answers
            # Normaliza em memória usando get_answers() que atualiza self.answers
            _ = session.get_answers()
            # Verifica se houve mudança
            if before != session.answers:
                fixed_count += 1
        
        # Salva todas as mudanças de uma vez
        db.session.commit()
        
        return jsonify({
            'success': True,
            'fixed': fixed_count,
            'message': f'{fixed_count} sessão(ões) normalizada(s) com sucesso.'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Erro ao reparar sessões: {str(e)}'
        }), 500


@etp_dynamic_bp.route('/export/docx', methods=['POST'])
@cross_origin()
def export_docx():
    """
    Export ETP document to .docx format using template.
    
    Request JSON:
    {
        "session_id": "<uuid>",
        "title": "Estudo Técnico Preliminar - <objeto>",
        "organ": "Nome do órgão",
        "object": "Descrição do objeto"
    }
    
    Returns: .docx file for download
    """
    try:
        from domain.services.docx_exporter import DocxExporter
        
        data = request.get_json()
        session_id = data.get('session_id', '').strip()
        
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id é obrigatório'}), 400
        
        # Load session
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'success': False, 'error': 'Sessão não encontrada'}), 404
        
        # Load EtpParts and assemble document sections
        from application.etp.types import DocSection
        parts = load_parts(session_id)
        assembled = assemble_sections(parts)
        
        # Build ETP data from assembled sections (via Assembler, not raw chat)
        etp_data = {
            'title': data.get('title', 'Estudo Técnico Preliminar'),
            'organ': data.get('organ', 'Órgão Contratante'),
            'object': data.get('object', parts.necessidade_texto or 'Objeto da contratação'),
            'introducao': assembled.get(DocSection.INTRODUCAO, ''),
            'necessity': assembled.get(DocSection.OBJETO_DESC_NECESSIDADE, ''),
            'requirements': parts.requisitos or [],
            'requisitos_tecnicos': assembled.get(DocSection.REQ_TECNICOS, ''),
            'requisitos_normativos': assembled.get(DocSection.REQ_NORMATIVOS, ''),
            'pca': assembled.get(DocSection.OBJETO_PCA, ''),
            'estimativa_quantidades': assembled.get(DocSection.ESTIMATIVA_QTD, ''),
            'estimativa_valor': assembled.get(DocSection.ESTIMATIVA_VALOR, ''),
            'solution_strategy': assembled.get(DocSection.SOLUCAO_COMO_UM_TODO, ''),
            'parcelamento': assembled.get(DocSection.JUSTIFICATIVA_PARCELAMENTO, ''),
            'justifications': '',  # Deprecated - no longer in chat
            'signatures': data.get('signatures', '')
        }
        
        logger.info(f"[EXPORT_DOCX] Exporting session {session_id}")
        
        # Check for template
        template_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', '..', '..', 
            'templates', 
            'modelo-etp.docx'
        )
        
        # Create exporter
        exporter = DocxExporter(template_path if os.path.exists(template_path) else None)
        
        # Generate document
        docx_buffer = exporter.export_etp(etp_data)
        
        # Generate filename
        filename = f"ETP-{session_id[:8]}.docx"
        if data.get('object'):
            # Sanitize object name for filename
            obj_name = data['object'][:30]
            obj_name = re.sub(r'[^\w\s-]', '', obj_name)
            obj_name = re.sub(r'[\s]+', '-', obj_name)
            filename = f"ETP-{obj_name}.docx"
        
        logger.info(f"[EXPORT_DOCX] Generated {filename}")
        
        return send_file(
            docx_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except Exception as e:
        logger.error(f"[EXPORT_DOCX] Error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro ao gerar documento: {str(e)}'
        }), 500
