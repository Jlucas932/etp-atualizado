"""
Preview Builder Service
Generates ETP previews with multipass generation (14-section structure).
Uses 3-4 OpenAI calls to avoid token limits.
"""
import os
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

def get_openai_client() -> Optional[OpenAI]:
    """Get OpenAI client instance"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("[PREVIEW_BUILDER] OPENAI_API_KEY not found")
        return None
    return OpenAI(api_key=api_key)

def get_model_name() -> str:
    """Get model name from environment"""
    return os.getenv("OPENAI_MODEL", "gpt-4o")


def generate_etp_multipass(context: dict) -> str:
    """
    Gera ETP completo usando multipass (3-4 chamadas) para evitar limite de tokens.
    Estrutura obrigatória de 14 seções, conteúdo rico e variável.
    
    Args:
        context: Dict com necessity, requirements, answers
        
    Returns:
        str: Documento ETP completo em markdown
    """
    client = get_openai_client()
    if not client:
        return "# Erro\n\nNão foi possível gerar a prévia (API key não configurada)."
    
    model = get_model_name()
    necessity = context.get('necessity', 'Não informada')
    requirements = context.get('requirements', [])
    answers = context.get('answers', {})
    
    # Extract answers
    selected_strategies = answers.get('selected_strategies', [])
    pca = answers.get('pca', 'Não informado')
    legal_norms = answers.get('legal_norms', 'Não informado')
    qty_value = answers.get('qty_value', 'Não informado')
    installment = answers.get('installment', 'Não informado')
    
    # Format requirements for prompt
    req_list = []
    for i, req in enumerate(requirements, 1):
        text = req.get('text', '') if isinstance(req, dict) else str(req)
        req_list.append(f"{i}. {text}")
    req_text = "\n".join(req_list) if req_list else "Requisitos não definidos"
    
    # Format strategies
    strategy_text = ""
    if selected_strategies:
        for strat in selected_strategies:
            titulo = strat.get('titulo', 'Estratégia não especificada')
            strategy_text += f"- {titulo}\n"
    else:
        strategy_text = "Estratégia não definida"
    
    # Base context for all passes
    base_context = f"""
Contexto da contratação:
- Necessidade: {necessity}
- Estratégia de contratação: {strategy_text}
- PCA: {pca}
- Normas: {legal_norms}
- Estimativa: {qty_value}
- Parcelamento: {installment}

Requisitos técnicos:
{req_text}
"""
    
    # PASS 1: Sections 1-4
    logger.info("[PREVIEW_BUILDER] Multipass - Pass 1/4 (Sections 1-4)")
    pass1_prompt = f"""Você é um especialista em elaboração de ETPs (Estudos Técnicos Preliminares) conforme Lei 14.133/2021.

{base_context}

Gere APENAS as seções 1 a 4 do ETP com conteúdo substancial e técnico (NÃO replique falas do usuário):

1. INTRODUÇÃO
   - Finalidade do ETP
   - Base legal (Lei 14.133/2021)
   - Princípios da administração pública

2. OBJETO DO ESTUDO E ESPECIFICAÇÕES GERAIS
   2.1 Local de execução
   2.2 Natureza e finalidade
   2.3 Classificação quanto ao sigilo
   2.4 Descrição da necessidade
   2.5 Previsão no PCA

3. DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO
   3.1 Requisitos Técnicos (com verificabilidade)
   3.2 Requisitos de Sustentabilidade
   3.3 Requisitos Normativos

4. ESTIMATIVA DAS QUANTIDADES E VALORES
   Incluir tabela:
   | Item | Descrição | Quantidade | Unidade | Valor Unit. (R$) | Valor Total (R$) |
   |------|-----------|------------|---------|------------------|------------------|
   | 1    | [Item]    | [Qtd]      | [Un]    | [Valor]          | [Total]          |

Use o contexto fornecido mas redija de forma técnica, coesa e profissional. Cada seção deve ter NO MÍNIMO 2-3 parágrafos substanciais."""
    
    pass1_content = _call_openai_with_retry(client, model, pass1_prompt)
    
    # PASS 2: Sections 5-8
    logger.info("[PREVIEW_BUILDER] Multipass - Pass 2/4 (Sections 5-8)")
    pass2_prompt = f"""Continue o ETP. Você já gerou as seções 1-4. Agora gere as seções 5 a 8:

{base_context}

5. LEVANTAMENTO DE MERCADO
   - Pesquisa de preços no PNCP
   - Comparativos de fornecedores
   - Análise de mercado

6. ESTIMATIVA DO VALOR DA CONTRATAÇÃO
   Incluir tabela consolidada:
   | Descrição | Valor Mínimo (R$) | Valor Médio (R$) | Valor Máximo (R$) |
   |-----------|-------------------|------------------|-------------------|
   | Estimativa| [Min]             | [Med]            | [Max]             |

7. DESCRIÇÃO DA SOLUÇÃO COMO UM TODO
   - Abordagem técnica
   - Integração dos componentes
   - Cronograma estimado

8. JUSTIFICATIVA DO PARCELAMENTO
   - Análise de parcelamento vs. lote único
   - Fundamentação da decisão

Mantenha coerência com as seções anteriores. Mínimo 2-3 parágrafos por seção."""
    
    pass2_content = _call_openai_with_retry(client, model, pass2_prompt)
    
    # PASS 3: Sections 9-12
    logger.info("[PREVIEW_BUILDER] Multipass - Pass 3/4 (Sections 9-12)")
    pass3_prompt = f"""Continue o ETP. Você já gerou as seções 1-8. Agora gere as seções 9 a 12:

{base_context}

9. RESULTADOS PRETENDIDOS
   - Objetivos mensuráveis
   - Indicadores de sucesso
   - Benefícios esperados

10. PROVIDÊNCIAS PRÉVIAS À CONTRATAÇÃO
    - Ações necessárias
    - Documentação requerida
    - Aprovações necessárias

11. CONTRATAÇÕES CORRELATAS
    - Contratos relacionados existentes
    - Interdependências
    - Sinergia com outras contratações

12. IMPACTOS AMBIENTAIS
    - Avaliação de impacto ambiental
    - Medidas de mitigação
    - Sustentabilidade

Mínimo 2-3 parágrafos por seção. Seja específico e técnico."""
    
    pass3_content = _call_openai_with_retry(client, model, pass3_prompt)
    
    # PASS 4: Sections 13-14 + Header
    logger.info("[PREVIEW_BUILDER] Multipass - Pass 4/4 (Sections 13-14 + Mapa de Riscos)")
    pass4_prompt = f"""Finalize o ETP. Você já gerou as seções 1-12. Agora gere as seções finais 13-14:

{base_context}

13. MAPA DE RISCOS
    Incluir tabela:
    | Risco | Probabilidade | Impacto | Mitigação |
    |-------|---------------|---------|-----------|
    | [Risco 1] | [Alta/Média/Baixa] | [Alto/Médio/Baixo] | [Medida] |
    | [Risco 2] | [Alta/Média/Baixa] | [Alto/Médio/Baixo] | [Medida] |
    | [Risco 3] | [Alta/Média/Baixa] | [Alto/Médio/Baixo] | [Medida] |
    
    Identifique pelo menos 5 riscos relevantes.

14. POSICIONAMENTO CONCLUSIVO
    - Recomendação final
    - Alinhamento com planejamento estratégico
    - Próximos passos
    - Assinatura da equipe técnica

Seja técnico e conclusivo. Cada seção com NO MÍNIMO 2-3 parágrafos."""
    
    pass4_content = _call_openai_with_retry(client, model, pass4_prompt)
    
    # Consolidate all passes
    header = f"""# ESTUDO TÉCNICO PRELIMINAR (ETP)

**Data:** {_get_current_date()}  
**Órgão:** [Nome do Órgão]  
**Setor Demandante:** [Setor]

---

"""
    
    full_document = header + pass1_content + "\n\n" + pass2_content + "\n\n" + pass3_content + "\n\n" + pass4_content
    
    logger.info(f"[PREVIEW_BUILDER] Multipass complete - Generated {len(full_document)} characters")
    return full_document


def _call_openai_with_retry(client: OpenAI, model: str, prompt: str, max_retries: int = 2) -> str:
    """
    Chama OpenAI com retry se retornar vazio.
    
    Args:
        client: OpenAI client
        model: Model name
        prompt: Prompt text
        max_retries: Maximum retry attempts
        
    Returns:
        str: Generated content
    """
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Você é um especialista em elaboração de Estudos Técnicos Preliminares (ETP) para licitações públicas brasileiras."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            if content:
                logger.info(f"[PREVIEW_BUILDER] OpenAI call successful (attempt {attempt + 1})")
                return content
            else:
                logger.warning(f"[PREVIEW_BUILDER] Empty response from OpenAI (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    continue
                    
        except Exception as e:
            logger.error(f"[PREVIEW_BUILDER] OpenAI call failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                continue
    
    # If all retries failed
    return "[Erro ao gerar esta seção. Por favor, tente novamente.]"


def _get_current_date() -> str:
    """Get current date formatted"""
    from datetime import datetime
    return datetime.now().strftime("%d/%m/%Y")


def build_preview(conversation_id: str, summary: dict) -> dict:
    """
    Gera HTML e PDF a partir do resumo/estado da conversa.
    Salva em /app/static/previews/{conversation_id}.html e .pdf.
    
    Args:
        conversation_id: ID da conversa
        summary: Dicionário com necessity, requirements, answers
        
    Returns:
        Dict: {
          "html_path": "/static/previews/{conversation_id}.html",
          "pdf_path": None,  # PDF not implemented yet
          "filename": "ETP_{conversation_id}.html"
        }
    """
    try:
        # Extract data from summary
        necessity = summary.get('necessity', 'Não informada')
        requirements = summary.get('requirements', [])
        answers = summary.get('answers', {})
        
        # Find project root and create previews directory
        # From: src/main/python/application/services/
        # To: static/previews/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..', '..'))
        static_dir = os.path.join(project_root, 'static')
        previews_dir = os.path.join(static_dir, 'previews')
        
        # Create previews directory if it doesn't exist
        os.makedirs(previews_dir, exist_ok=True)
        logger.info(f"[PREVIEW_BUILDER] Previews directory: {previews_dir}")
        
        # Generate filenames
        html_filename = f"{conversation_id}.html"
        html_filepath = os.path.join(previews_dir, html_filename)
        
        # Generate HTML content
        html_content = _generate_html(necessity, requirements, answers)
        
        # Save HTML file
        with open(html_filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"[PREVIEW_BUILDER] HTML saved: {html_filepath}")
        
        # Generate response paths (relative URLs for frontend)
        html_path = f"/static/previews/{html_filename}"
        
        return {
            "html_path": html_path,
            "pdf_path": None,  # PDF generation not implemented yet
            "filename": f"ETP_{conversation_id}.html"
        }
        
    except Exception as e:
        logger.error(f"[PREVIEW_BUILDER] Error building preview: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


def build_etp_markdown(context: dict) -> str:
    """
    Gera documento ETP completo em markdown para exibição no chat usando multipass.
    Estrutura de 14 seções com conteúdo rico e técnico.
    
    Args:
        context: Dicionário com necessity, requirements, answers
        
    Returns:
        str: Documento markdown completo em formato etp-preview
    """
    logger.info("[PREVIEW_BUILDER] Building ETP markdown with multipass generation")
    
    # Use multipass generation for full 14-section structure
    full_etp = generate_etp_multipass(context)
    
    # Wrap in etp-preview code block for front-end rendering
    return f"```etp-preview\n{full_etp}\n```"


def build_etp_markdown_legacy(context: dict) -> str:
    """
    LEGACY: Simple ETP markdown generation (kept for reference).
    Use build_etp_markdown() for multipass generation instead.
    """
    necessity = context.get('necessity', 'Não informada')
    requirements = context.get('requirements', [])
    answers = context.get('answers', {})
    
    # Extract answers
    selected_strategies = answers.get('selected_strategies', [])
    pca = answers.get('pca', 'Não informado')
    legal_norms = answers.get('legal_norms', 'Não informado')
    qty_value = answers.get('qty_value', 'Não informado')
    installment = answers.get('installment', 'Não informado')
    
    # Build markdown document
    md = []
    
    # Title and summary
    md.append("# Estudo Técnico Preliminar (ETP)")
    md.append("")
    md.append("## Sumário Executivo")
    md.append("")
    md.append(f"Este documento apresenta o Estudo Técnico Preliminar para {necessity}.")
    md.append("")
    
    # Section 1: Necessidade
    md.append("## 1. Necessidade")
    md.append("")
    md.append(necessity)
    md.append("")
    
    # Section 2: Requisitos Técnicos
    md.append("## 2. Requisitos Técnicos")
    md.append("")
    if requirements:
        for i, req in enumerate(requirements, 1):
            text = req.get('text', '') if isinstance(req, dict) else str(req)
            # Extract (Obrigatório)/(Desejável) markers
            if '(Obrigatório)' in text or '(Desejável)' in text:
                md.append(f"{i}. {text}")
            else:
                md.append(f"{i}. {text}")
        md.append("")
        md.append(f"**Justificativa**: Os {len(requirements)} requisitos acima foram definidos considerando a necessidade específica, ")
        md.append("garantindo conformidade técnica e operacional.")
    else:
        md.append("*Requisitos não definidos.*")
    md.append("")
    
    # Section 3: Caminho da Solução (Estratégia de Contratação)
    md.append("## 3. Caminho da Solução")
    md.append("")
    if selected_strategies:
        for strat in selected_strategies:
            titulo = strat.get('titulo', 'Estratégia não especificada')
            quando = strat.get('quando_indicado', '')
            vantagens = strat.get('vantagens', [])
            riscos = strat.get('riscos', [])
            
            md.append(f"**Estratégia Recomendada**: {titulo}")
            md.append("")
            if quando:
                md.append(f"**Quando indicado**: {quando}")
                md.append("")
            if vantagens:
                md.append("**Vantagens**:")
                for v in vantagens:
                    md.append(f"- {v}")
                md.append("")
            if riscos:
                md.append("**Riscos e Mitigações**:")
                for r in riscos:
                    md.append(f"- {r}")
                md.append("")
            
            md.append(f"**Por que essa estratégia**: A modalidade '{titulo}' é a mais adequada para atender à necessidade identificada, ")
            md.append("considerando os requisitos técnicos, prazos e características da contratação.")
    else:
        md.append("*Estratégia de contratação não definida.*")
    md.append("")
    
    # Section 4: PCA (Plano de Contratações Anual)
    md.append("## 4. PCA (Plano de Contratações Anual)")
    md.append("")
    md.append(f"**Situação**: {pca}")
    md.append("")
    if 'Pendente' not in pca and 'não informado' not in pca.lower():
        md.append("A contratação está alinhada com o planejamento anual do órgão.")
    md.append("")
    
    # Section 5: Normas Legais e Regulatórias
    md.append("## 5. Normas Legais e Regulatórias")
    md.append("")
    md.append("**Obrigatórias**:")
    md.append("- Lei 14.133/2021 (Nova Lei de Licitações)")
    md.append("- Decreto 11.462/2023 (Regulamenta a Lei 14.133/2021)")
    md.append("")
    md.append("**De Referência/Setoriais**:")
    md.append(f"{legal_norms}")
    md.append("")
    md.append("**Justificativa**: As normas acima asseguram conformidade licitatória e regulatória, ")
    md.append("além de atender requisitos técnicos específicos do setor.")
    md.append("")
    
    # Section 6: Quantitativo e Valor Estimado
    md.append("## 6. Quantitativo e Valor Estimado")
    md.append("")
    md.append(f"**Estimativa**: {qty_value}")
    md.append("")
    if 'Pendente' in qty_value or 'não informado' in qty_value.lower():
        md.append("**Método de Estimativa Sugerido**: Benchmark no PNCP + pesquisa de preços com 3+ fornecedores.")
        md.append("")
        md.append("**Próximos Passos**: Realizar pesquisa de mercado para validação dos valores.")
    else:
        md.append("**Método de Estimativa**: Baseado em pesquisa de mercado e/ou histórico de contratações similares.")
    md.append("")
    
    # Section 7: Parcelamento
    md.append("## 7. Parcelamento")
    md.append("")
    md.append(f"**Decisão**: {installment}")
    md.append("")
    if 'sim' in installment.lower():
        md.append("**Justificativa**: O parcelamento permite melhor gestão orçamentária e adequação ao fluxo de pagamentos do órgão.")
    elif 'não' in installment.lower() or 'nao' in installment.lower():
        md.append("**Justificativa**: Pagamento único simplifica a execução contratual e pode permitir melhor negociação de preços.")
    md.append("")
    
    # Section 8: Riscos e Mitigações
    md.append("## 8. Riscos e Mitigações")
    md.append("")
    md.append("**Principais riscos identificados**:")
    md.append("")
    md.append("1. **Risco de não atendimento dos requisitos técnicos**")
    md.append("   - *Mitigação*: Especificação detalhada e análise criteriosa das propostas técnicas")
    md.append("")
    md.append("2. **Risco de variação de preços de mercado**")
    md.append("   - *Mitigação*: Pesquisa ampla de preços e previsão de reajuste contratual")
    md.append("")
    md.append("3. **Risco de atraso na entrega/execução**")
    md.append("   - *Mitigação*: Estabelecimento de prazos claros com multas por descumprimento")
    md.append("")
    
    # Section 9: Próximos Passos
    md.append("## 9. Próximos Passos")
    md.append("")
    md.append("- [ ] Validar requisitos técnicos com área demandante")
    md.append("- [ ] Realizar pesquisa de preços detalhada")
    md.append("- [ ] Confirmar disponibilidade orçamentária")
    md.append("- [ ] Elaborar Termo de Referência ou Projeto Básico")
    md.append("- [ ] Submeter à aprovação da autoridade competente")
    md.append("- [ ] Iniciar processo licitatório")
    md.append("")
    
    md.append("---")
    md.append("")
    md.append("*Documento gerado automaticamente pelo sistema AutoDoc-IA*")
    
    return "\n".join(md)


def _generate_html(necessity: str, requirements: List[Dict], answers: Dict) -> str:
    """
    Generate HTML content for ETP preview.
    
    Args:
        necessity: User's necessity description
        requirements: List of requirement dicts with 'text' field
        answers: Dict with pca, legal_norms, qty_value, installment, solution_path
        
    Returns:
        str: Complete HTML document
    """
    # Build requirements list HTML
    if requirements:
        reqs_html = "<ol>\n"
        for req in requirements:
            text = req.get('text', '') if isinstance(req, dict) else str(req)
            reqs_html += f"        <li>{_escape_html(text)}</li>\n"
        reqs_html += "      </ol>"
    else:
        reqs_html = "<p><em>Nenhum requisito definido.</em></p>"
    
    # Build solution path HTML
    solution_path = answers.get('solution_path', [])
    if solution_path and isinstance(solution_path, list):
        solution_html = "<ol>\n"
        for step in solution_path:
            solution_html += f"        <li>{_escape_html(step)}</li>\n"
        solution_html += "      </ol>"
    else:
        solution_html = "<p><em>Caminho da solução não definido.</em></p>"
    
    # Extract other answers
    pca = answers.get('pca', 'Não informado')
    legal_norms = answers.get('legal_norms', 'Não informado')
    qty_value = answers.get('qty_value', 'Não informado')
    installment = answers.get('installment', 'Não informado')
    
    # Build complete HTML
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estudo Técnico Preliminar - ETP</title>
    <style>
        body {{
            font-family: 'Arial', 'Helvetica', sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a73e8;
            border-bottom: 3px solid #1a73e8;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #333;
            margin-top: 30px;
            margin-bottom: 15px;
            font-size: 1.3em;
        }}
        .section {{
            margin-bottom: 25px;
        }}
        .label {{
            font-weight: bold;
            color: #555;
        }}
        ol, ul {{
            margin: 10px 0;
            padding-left: 30px;
        }}
        li {{
            margin-bottom: 8px;
        }}
        .info-box {{
            background-color: #f8f9fa;
            border-left: 4px solid #1a73e8;
            padding: 15px;
            margin: 15px 0;
        }}
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #777;
            font-size: 0.9em;
        }}
        @media print {{
            body {{
                background-color: white;
                margin: 0;
            }}
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Estudo Técnico Preliminar (ETP)</h1>
        
        <div class="section">
            <h2>1. Necessidade</h2>
            <p>{_escape_html(necessity)}</p>
        </div>
        
        <div class="section">
            <h2>2. Requisitos Técnicos</h2>
            {reqs_html}
        </div>
        
        <div class="section">
            <h2>3. Caminho da Solução</h2>
            {solution_html}
        </div>
        
        <div class="section">
            <h2>4. Previsão no PCA</h2>
            <div class="info-box">
                <p>{_escape_html(pca)}</p>
            </div>
        </div>
        
        <div class="section">
            <h2>5. Normas Legais Aplicáveis</h2>
            <div class="info-box">
                <p>{_escape_html(legal_norms)}</p>
            </div>
        </div>
        
        <div class="section">
            <h2>6. Quantitativo e Valor Estimado</h2>
            <div class="info-box">
                <p>{_escape_html(qty_value)}</p>
            </div>
        </div>
        
        <div class="section">
            <h2>7. Parcelamento</h2>
            <div class="info-box">
                <p>{_escape_html(installment)}</p>
            </div>
        </div>
        
        <div class="footer">
            <p>Documento gerado automaticamente pelo sistema AutoDoc-IA</p>
        </div>
    </div>
</body>
</html>"""
    
    return html


def _escape_html(text: str) -> str:
    """Escape HTML special characters"""
    if not isinstance(text, str):
        text = str(text)
    
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;'))
