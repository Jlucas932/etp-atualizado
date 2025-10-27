"""
Strict per-stage prompt templates for ETP generation.
Each template enforces JSON output and prohibits onboarding phrases.
"""

PROMPT_SUGGEST_REQUIREMENTS = """
Gere APENAS uma lista numerada de requisitos técnicos e operacionais, sem perguntas e sem textos de abertura.
Cada item deve terminar com (Obrigatório) ou (Desejável) e incluir critério de verificação/auditoria.
É EXPRESSAMENTE PROIBIDO incluir:
- "Descrição da Necessidade"
- "Justificativa da Contratação" (em qualquer forma)
- Frases como "Vamos começar", "Posso seguir", "Posso avançar"

Saída OBRIGATÓRIA (JSON estrito, somente esta chave):
{"requirements": ["1. ... (Obrigatório)", "2. ... (Desejável)"]}
"""

PROMPT_SOLUTION_STRATEGIES = """
Proponha APENAS 2–3 estratégias de contratação coerentes com a necessidade e os requisitos aprovados.
Para cada estratégia, retorne exclusivamente:
  - name  (nome curto da estratégia)
  - when  (em que contexto/condições a estratégia é indicada)
  - pros  (bullets curtos)
  - cons  (bullets curtos)

PROIBIDO nesta etapa:
  - "Justificativa da Contratação", "justificativas curtas", qualquer parágrafo narrativo
  - "recomendação", "recomendação final"
  - Reabrir "Descrição da Necessidade" ou onboarding ("vamos começar", "posso seguir")

Saída JSON **estrita** (apenas esta chave):
{
  "strategies": [
    {"name":"...","when":"...","pros":["...","..."],"cons":["...","..."]},
    {"name":"...","when":"...","pros":["..."],"cons":["..."]}
  ]
}
"""

PROMPT_PCA = """
Redija texto objetivo sobre a situação de previsão no PCA (com/sem/não se aplica).
PROIBIDO inserir "Descrição da Necessidade" ou "Justificativa da Contratação".
Saída JSON: {"status":"com_previsao|sem_previsao|nao_se_aplica","text":"..."}
"""

PROMPT_LEGAL_NORMS = """
Liste normas aplicáveis com breve justificativa de aplicabilidade.
PROIBIDO "Descrição da Necessidade"/"Justificativa da Contratação".
Saída JSON: {"norms":[{"ref":"Lei 14.133/2021, art. X","aplica":"..."}]}
"""

PROMPT_QTY_VALUE = """
Consolide quantitativos e valor estimado, com metodologia (cotações, painéis, histórico etc.).
Saída JSON: {"items":[{"descricao":"...","quantidade":...,"valor_unit":...}],"methodology":"..."}
"""

PROMPT_INSTALLMENT = """
Decida sobre parcelamento (sim/não) com justificativa técnica e legal. Sem textos de abertura.
Saída JSON: {"decision":"parcelar|nao_parcelar","text":"..."}
"""

PROMPT_SUMMARY = """
Resumo executivo final do ETP, coerente com as etapas anteriores. Sem onboarding.
Saída JSON: {"executive_summary":"..."}
"""

# Export prompt templates as a dictionary for easy access
prompt_templates = {
    "prompt_suggest_requirements": PROMPT_SUGGEST_REQUIREMENTS,
    "prompt_solution_strategies": PROMPT_SOLUTION_STRATEGIES,
    "prompt_pca": PROMPT_PCA,
    "prompt_legal_norms": PROMPT_LEGAL_NORMS,
    "prompt_qty_value": PROMPT_QTY_VALUE,
    "prompt_installment": PROMPT_INSTALLMENT,
    "prompt_summary": PROMPT_SUMMARY,
}

# Also export individual prompts for direct import
prompt_suggest_requirements = PROMPT_SUGGEST_REQUIREMENTS
prompt_solution_strategies = PROMPT_SOLUTION_STRATEGIES
prompt_pca = PROMPT_PCA
prompt_legal_norms = PROMPT_LEGAL_NORMS
prompt_qty_value = PROMPT_QTY_VALUE
prompt_installment = PROMPT_INSTALLMENT
prompt_summary = PROMPT_SUMMARY
