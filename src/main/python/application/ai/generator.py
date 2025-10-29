import os
import json
import logging
import re
import traceback
import hashlib
from typing import List, Dict, Any, Protocol, Optional
from config.models import MODEL, TEMP

logger = logging.getLogger(__name__)

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
Produzir requisitos mensuráveis (métrica/SLA/evidência/norma) marcando (Obrigatório)/(Desejável) e, ao final, justificar em 2–5 linhas por que os requisitos se encaixam no caso.
Propor 3–5 estratégias de contratação ("melhor caminho") aderentes à necessidade (ex.: compra, leasing, outsourcing, comodato, contrato por desempenho, ARP). Para cada estratégia, incluir: Quando indicado, Vantagens, Riscos/Cuidados com Mitigação, Exemplo prático e Por que encaixa no caso.
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
Ao final, forneça justificativa de 2–5 linhas explicando por que esses requisitos atendem à necessidade e por que escolheu essa quantidade."""
    
    elif stage == "refine":
        return base + """

Tarefa: Refaça a lista completa de requisitos incorporando as preferências do usuário.
Mantenha numeração, marcação (Obrigatório)/(Desejável) e métricas.
Na justificativa, explique o que mudou e por quê."""
    
    elif stage == "solution_strategies":
        return base + """

Tarefa: Liste 3–5 estratégias de contratação aplicáveis (não etapas de ETP).
Para cada estratégia, forneça:
- Título (ex.: "Compra Direta", "Leasing Operacional")
- Quando indicado
- Vantagens
- Riscos/Cuidados + Mitigação
- Exemplo prático
- Por que encaixa no caso

Foco em modalidade/arranjo contratual e impacto na necessidade, não em instruções de ETP."""
    
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
        Dict estruturado SEM texto pré-definido, com campos conforme a etapa:
        {
            "intro": "texto consultivo curto (quando fizer sentido)",
            "requirements": ["1. ...", "2. ...", ...],
            "strategies": [{titulo, quando_indicado, vantagens, riscos, pontos_de_requisito_afetados}...],
            "legal": [{norma, aplicacao}...],
            "summary": "texto corrido pronto para prévia"
        }
    """
    logger.info(f"[GEN:NO_TEMPLATES] Generating for stage={stage}")
    
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
        system_prompt = get_system_prompt(stage)
        
        # Build context from RAG
        rag_chunks = rag_context.get('chunks', [])
        rag_text = "\n\n".join([f"[Referência {i+1}] {chunk.get('text', '')}" for i, chunk in enumerate(rag_chunks[:8])])
        logger.info(f"[RAG:USED n={len(rag_chunks[:8])}]")
        
        # Build user prompt based on stage
        user_prompt = _build_user_prompt(stage, user_input, rag_text, rag_context)
        
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
        content = content.strip()
        
        # Parse response based on stage
        result = _parse_response(stage, content, user_input, rag_context)
        
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
        return f"""Necessidade informada pelo usuário: {user_input}

Contexto RAG (exemplos de requisitos similares):
{rag_text if rag_text else "Nenhum contexto disponível."}

Gere requisitos numerados baseado na complexidade (baixa: 7-10, média: 10-14, alta: 14-20), claros, verificáveis e sem perguntas.
Cada requisito deve seguir o padrão: [Obrigação] + [Métrica mínima] + [Condição de verificação].

Exemplo: "1. O fornecedor deve disponibilizar sistema de gestão de frota com registro de manutenção, voos e tripulações, com exportação CSV/PDF mensal. (Obrigatório)"

Indique ao final de cada requisito se é (Obrigatório) ou (Desejável), quando fizer sentido.

Retorne em formato JSON:
{{
  "intro": "parágrafo curto de contexto como consultor (2-4 linhas)",
  "requirements": ["1. requisito um", "2. requisito dois", ...],
  "justification": "1-2 frases explicando por que esses requisitos se encaixam na necessidade; indicar quais itens são Obrigatórios e quais são Desejáveis"
}}"""

    elif stage == "refine":
        previous_requirements = rag_context.get('requirements', [])
        reqs_text = "\n".join(previous_requirements) if previous_requirements else "Nenhum requisito anterior."
        
        return f"""Necessidade: {necessity}

Requisitos anteriores:
{reqs_text}

Nova informação do usuário: {user_input}

Contexto RAG:
{rag_text if rag_text else "Nenhum contexto disponível."}

Refine os requisitos integrando a nova informação do usuário. Re-emita a lista completa numerada e explique brevemente o que mudou.
Mantenha a marcação (Obrigatório)/(Desejável) quando aplicável.

Retorne em formato JSON:
{{
  "intro": "explicação breve das mudanças (2-4 linhas)",
  "requirements": ["1. requisito atualizado um", "2. requisito dois", ...],
  "justification": "1-2 frases explicando o que mudou e por quê"
}}"""

    elif stage == "solution_strategies":
        requirements = rag_context.get('requirements', [])
        reqs_text = "\n".join(requirements[:10]) if requirements else "Requisitos não disponíveis."
        
        return f"""Necessidade: {necessity}

Requisitos definidos (primeiros 10):
{reqs_text}

Contexto RAG:
{rag_text if rag_text else "Nenhum contexto disponível."}

Gere de 2 a 5 opções de estratégias de contratação aplicáveis à necessidade informada.
Exemplos de estratégias: compra direta, locação, comodato, outsourcing, leasing operacional, ata de registro de preços, contrato por desempenho, etc.

NÃO descreva "passos para fazer um ETP". Foque em OPÇÕES DE CONTRATAÇÃO.

Retorne em formato JSON:
{{
  "intro": "parágrafo curto sobre as opções (1-2 frases)",
  "strategies": [
    {{
      "titulo": "Nome da estratégia",
      "quando_indicado": "Quando usar esta opção",
      "vantagens": ["vantagem 1", "vantagem 2"],
      "riscos": ["risco 1", "risco 2"],
      "pontos_de_requisito_afetados": [1, 3, 5]
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

def _parse_response(stage: str, content: str, user_input: str, rag_context: Dict) -> Dict:
    """Parse a resposta do modelo baseado no estágio"""
    
    try:
        # Try to extract JSON
        if '{' in content:
            json_start = content.index('{')
            json_end = content.rindex('}') + 1
            json_str = content[json_start:json_end]
            result = json.loads(json_str)
            return result
        else:
            # No JSON found, try to extract from text
            return _extract_from_text(stage, content)
    
    except Exception as e:
        logger.warning(f"[GENERATOR] Failed to parse JSON, extracting from text: {e}")
        return _extract_from_text(stage, content)

def _extract_from_text(stage: str, content: str) -> Dict:
    """Extrai informação estruturada de texto não-JSON"""
    
    if stage in ["collect_need", "refine"]:
        # Extract numbered requirements
        lines = content.split('\n')
        requirements = []
        intro_lines = []
        justification_lines = []
        in_requirements = False
        after_requirements = False
        
        for line in lines:
            stripped = line.strip()
            # Check if line starts with number
            if stripped and (stripped[0].isdigit() and '.' in stripped[:5]):
                in_requirements = True
                after_requirements = False
                requirements.append(stripped)
            elif in_requirements and stripped and not (stripped[0].isdigit() and '.' in stripped[:5]):
                # Text after requirements = justification
                after_requirements = True
                justification_lines.append(stripped)
            elif not in_requirements and stripped and not stripped.startswith('#'):
                intro_lines.append(stripped)
        
        return {
            "intro": " ".join(intro_lines[:4]) if intro_lines else "",
            "requirements": requirements if requirements else _get_default_requirements(stage, content),
            "justification": " ".join(justification_lines[:2]) if justification_lines else ""
        }
    
    elif stage == "solution_strategies":
        # Try to extract strategies from text - return minimal fallback
        return {
            "intro": "",
            "strategies": [
                {
                    "titulo": "Compra direta",
                    "quando_indicado": "Quando há necessidade de propriedade permanente do bem",
                    "vantagens": ["Propriedade definitiva", "Sem custos recorrentes"],
                    "riscos": ["Alto investimento inicial", "Obsolescência"],
                    "pontos_de_requisito_afetados": [1, 2, 3]
                }
            ]
        }
    
    elif stage == "legal_refs":
        return {
            "intro": "",
            "legal": [
                {"norma": "Lei 14.133/2021", "aplicacao": "Licitações e contratos administrativos"}
            ]
        }
    
    elif stage == "summary":
        return {
            "summary": content
        }
    
    return {}

def _get_default_requirements(stage: str, necessity: str) -> List[str]:
    """Gera requisitos padrão quando o modelo falha"""
    base = necessity[:50] if necessity else "contratação"
    return [
        f"1. Atender à necessidade de {base} conforme especificações técnicas",
        "2. Garantir conformidade com Lei 14.133/2021 e normas aplicáveis",
        "3. Fornecedor com experiência mínima de 2 anos no ramo",
        "4. Garantia mínima de 12 meses contra defeitos de fabricação",
        "5. Suporte técnico durante toda a vigência contratual",
        "6. Treinamento de equipe técnica com certificação",
        "7. Documentação técnica completa em português",
        "8. Compatibilidade com infraestrutura existente",
        "9. Prazo de entrega máximo de 60 dias corridos",
        "10. Assistência técnica em até 48 horas úteis"
    ]

def _validate_and_fix(stage: str, result: Dict, user_input: str, rag_context: Dict, 
                      client, model: str, system_prompt: str, messages: List[Dict]) -> Dict:
    """
    Valida requisitos e aplica correções se necessário.
    Política anti-lista-vazia e validação de qualidade.
    """
    
    if stage in ["collect_need", "refine"]:
        requirements = result.get('requirements', [])
        
        # Validate requirements
        valid = True
        reasons = []
        
        # Check if empty
        if not requirements or len(requirements) < 8:
            valid = False
            reasons.append("menos de 8 requisitos")
        
        # Check if all items are numbered
        if requirements:
            for req in requirements:
                if not (req.strip() and req.strip()[0].isdigit()):
                    valid = False
                    reasons.append("requisitos não numerados")
                    break
                
                # Check for questions
                if '?' in req:
                    valid = False
                    reasons.append("requisitos contêm perguntas")
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

Retorne APENAS JSON válido:
{{
  "intro": "frase contextual breve (2-4 linhas)",
  "requirements": ["1. requisito um com métrica", "2. requisito dois com métrica", ...],
  "justification": "1-2 frases explicando por que esses requisitos se encaixam na necessidade"
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
                if not result.get('requirements') or len(result.get('requirements', [])) < 8:
                    result['requirements'] = _get_default_requirements(stage, rag_context.get('necessity', user_input))
                    if 'intro' not in result or not result['intro']:
                        result['intro'] = ""
                    if 'justification' not in result or not result['justification']:
                        result['justification'] = ""
                    
            except Exception as e:
                logger.error(f"[GENERATOR] Regen failed: {e}")
                result['requirements'] = _get_default_requirements(stage, rag_context.get('necessity', user_input))
                if 'intro' not in result or not result['intro']:
                    result['intro'] = ""
                if 'justification' not in result or not result['justification']:
                    result['justification'] = ""
    
    return result

def _fallback_requirements_min(necessity: str) -> List[str]:
    """Gera pelo menos 8-12 requisitos objetivos quando tudo falhar"""
    base = necessity[:60] if necessity else "contratação"
    return [
        f"1. Atender plenamente à necessidade de {base} conforme especificações técnicas e requisitos funcionais mínimos",
        "2. Garantir conformidade com Lei 14.133/2021, legislação aplicável e normas técnicas do setor",
        "3. Fornecedor com experiência comprovada mínima de 2 anos em contratos similares",
        "4. Disponibilidade mínima de 99,5% mensal, com penalidades proporcionais por descumprimento",
        "5. Garantia contra defeitos de fabricação/execução pelo prazo mínimo de 12 meses",
        "6. Suporte técnico especializado em até 24 horas úteis, com SLA documentado",
        "7. Treinamento de equipe técnica com certificação reconhecida e material didático",
        "8. Documentação técnica completa em português brasileiro, incluindo manuais operacionais",
        "9. Compatibilidade técnica com infraestrutura e sistemas já existentes",
        "10. Relatórios mensais de desempenho, monitoramento e indicadores de qualidade",
        "11. Prazo de entrega ou início de execução em até 60 dias corridos após assinatura",
        "12. Conformidade com LGPD quando houver tratamento de dados pessoais"
    ]

def _fallback_strategies(necessity: str) -> List[Dict]:
    """Gera 2-4 estratégias quando o LLM falha"""
    base = necessity[:50] if necessity else "bem ou serviço"
    return [
        {
            "titulo": "Contrato por Desempenho (Performance-Based)",
            "quando_indicado": f"Quando o foco está em resultados mensuráveis para {base}",
            "vantagens": ["Pagamento vinculado a resultados", "Incentivo à qualidade", "Redução de riscos operacionais"],
            "riscos": ["Requer métricas bem definidas", "Dificuldade na mensuração inicial"],
            "pontos_de_requisito_afetados": [4, 6, 10]
        },
        {
            "titulo": "Outsourcing Integral",
            "quando_indicado": "Para necessidades que exigem gestão completa e especializada",
            "vantagens": ["Transferência total da operação", "Equipe dedicada", "Foco no core business"],
            "riscos": ["Dependência do fornecedor", "Custo recorrente mais alto"],
            "pontos_de_requisito_afetados": [3, 6, 7]
        },
        {
            "titulo": "Locação com Opção de Compra",
            "quando_indicado": "Quando há incerteza sobre a necessidade de longo prazo ou teste de viabilidade",
            "vantagens": ["Menor investimento inicial", "Flexibilidade contratual", "Possibilidade de aquisição futura"],
            "riscos": ["Custo total pode ser maior", "Limitações contratuais"],
            "pontos_de_requisito_afetados": [1, 9, 11]
        },
        {
            "titulo": "Ata de Registro de Preços (ARP)",
            "quando_indicado": "Para demandas recorrentes ou de múltiplos órgãos",
            "vantagens": ["Flexibilidade de aquisição", "Preços registrados por 12 meses", "Permite carona"],
            "riscos": ["Requer demanda estimada", "Não garante fornecimento imediato"],
            "pontos_de_requisito_afetados": [2, 11]
        }
    ]

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
    
    for key in ['intro', 'justification']:
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
            if re.search(command_pattern, req, re.I):
                req = re.sub(command_pattern, '', req, flags=re.I)
                req = ' '.join(req.split())
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
    if stage in {"collect_need", "refine"}:
        # Intro vazio
        if not resp.get("intro") or resp.get("intro").strip() == "":
            resp["intro"] = f"Entendi sua necessidade: {necessity[:80]}. Vou propor requisitos objetivos e verificáveis alinhados a segurança, disponibilidade e conformidade."
        
        # Requirements vazio ou insuficiente
        requirements = resp.get("requirements") or []
        if not requirements or len(requirements) < 8:
            logger.warning(f"[ENSURE_MIN] Requirements vazio/insuficiente ({len(requirements)}), aplicando fallback")
            resp["requirements"] = _fallback_requirements_min(necessity)
        
        # Justification vazio
        if not resp.get("justification") or resp.get("justification").strip() == "":
            resp["justification"] = "Os requisitos priorizam conformidade regulatória, segurança operacional, disponibilidade contratual e mensuração por indicadores objetivos."
    
    elif stage == "solution_strategies":
        # Strategies vazio
        strategies = resp.get("strategies") or []
        if not strategies or len(strategies) < 2:
            logger.warning(f"[ENSURE_MIN] Strategies vazio/insuficiente ({len(strategies)}), aplicando fallback")
            resp["strategies"] = _fallback_strategies(necessity)
        
        # Intro vazio
        if not resp.get("intro") or resp.get("intro").strip() == "":
            resp["intro"] = "Considerando o contexto, apresento as principais estratégias de contratação aplicáveis:"
    
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
    
    if stage in ["collect_need", "refine"]:
        resp = {
            "intro": "",
            "requirements": _get_default_requirements(stage, necessity),
            "justification": ""
        }
        return _ensure_min_payload(resp, stage, necessity)
    
    elif stage == "solution_strategies":
        resp = {
            "intro": "",
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
