# Conversational ETP Flow (Buttonless, 13-State Machine)

## Overview

This feature implements a complete conversational flow for ETP (Estudo Técnico Preliminar) generation without any buttons. The entire interaction happens through natural text conversation, following a strict 13-state machine as specified in the issue requirements.

## Architecture

### Core Components

1. **State Machine Module** (`domain/usecase/etp/conversational_state_machine.py`)
   - Defines all 13 states and valid transitions
   - Intent parsing with regex patterns
   - State-specific response generators
   - Error handling without state advancement

2. **Chat Endpoint** (`/api/etp-dynamic/chat-conversational`)
   - Orchestrates the conversation flow
   - Handles state transitions
   - Integrates with RAG for requirements generation
   - Persists conversation state in database

3. **Session Management** (`domain/dto/EtpOrm.py`)
   - EtpSession model stores conversation state
   - JSON answers field for additional data (PCA, legal norms, etc.)
   - Requirements stored in session

## State Machine Flow

The conversation follows this mandatory order:

```
collect_need 
  ↓
suggest_requirements 
  ↓
refine_requirements (can loop)
  ↓
confirm_requirements 
  ↓
recommend_solution_path 
  ↓
ask_pca 
  ↓
ask_legal_norms 
  ↓
ask_quant_value 
  ↓
ask_parcelamento 
  ↓
confirm_summary 
  ↓
generate_etp 
  ↓
preview 
  ↓
finalize
```

## Key Features

### 1. No Buttons
- All interactions via text
- Never suggests or mentions buttons
- User responds by typing

### 2. No Auto-Advancement
- State changes only with explicit user confirmation
- Confirmation patterns: "ok", "pode seguir", "segue", "prosseguir", "manter", "aceito", "concordo", "fechou"
- Final generation requires: "pode gerar", "gerar etp", "gera etp", "ok gerar"

### 3. Skip/Don't Know Handling
- User can say "não sei", "pular", "depois"
- Field is marked as "não informado"
- Conversation proceeds to next state

### 4. Error Handling
- Service errors don't advance state
- Clear error message provided
- User must explicitly retry

### 5. Requirements Management
- Adjust: `ajustar 3: novo texto`
- Remove: `remover 2`
- Include: `incluir: novo requisito`
- Confirm: `pode seguir`

### 6. Natural Tone
- Human-like conversation
- Explains before listing items
- No jargon without explanation
- No phrases like "Perfeito! Coletei todas as informações"

## API Endpoint

### POST `/api/etp-dynamic/chat-conversational`

**Request:**
```json
{
  "session_id": "uuid-string",
  "message": "user message text"
}
```

**Response:**
```json
{
  "success": true,
  "ai_response": "Natural language response",
  "conversation_stage": "current_state_name",
  "session_id": "uuid-string",
  "state_changed": true,
  "requirements": [
    {"id": "R1", "text": "Requirement text"},
    {"id": "R2", "text": "Requirement text"}
  ]
}
```

## State Details

### 1. collect_need
**Purpose:** Collect the necessity description
**Trigger:** First message or empty necessity
**Response:** "Olá! Para começar, me descreva em poucas palavras: qual a necessidade desta contratação?"
**Transition:** answer → suggest_requirements

### 2. suggest_requirements
**Purpose:** Present suggested requirements with explanation
**Trigger:** After need is collected
**Response:** Presents 3-6 requirements with human explanation
**Transition:** auto → refine_requirements

### 3. refine_requirements
**Purpose:** Allow user to adjust requirements
**Accepts:** 
- Edit commands: `ajustar N: texto`
- Remove: `remover N`
- Include: `incluir: texto`
- Confirm: `pode seguir`
**Transition:** 
- requirements_edit → refine_requirements (loop)
- confirm → confirm_requirements

### 4. confirm_requirements
**Purpose:** Confirm requirements are ready
**Response:** "Requisitos registrados. Posso sugerir o melhor caminho..."
**Transition:** confirm → recommend_solution_path

### 5. recommend_solution_path
**Purpose:** Suggest and select solution approach
**Accepts:** compra, locação, serviço, comparar, recomendação
**Response:** Explains 3 paths (compra/locação/serviço)
**Transition:** 
- choose_path → recommend_solution_path (confirm choice)
- confirm (with path set) → ask_pca

### 6. ask_pca
**Purpose:** Ask about PCA (Plano de Contratações Anual)
**Accepts:** sim, não, não informado, or description
**Response:** "Você possui previsão no PCA..."
**Transition:** answer_pca → ask_legal_norms

### 7. ask_legal_norms
**Purpose:** Collect legal norms to be used
**Accepts:** Any text with legal references or "não informado"
**Response:** "Quais normas legais pretende utilizar..."
**Transition:** answer_legal_norms → ask_quant_value

### 8. ask_quant_value
**Purpose:** Collect quantitative and value information
**Accepts:** Free text with numbers/currency
**Extracts:** quantitativo, valor, unidade, periodo
**Response:** "Qual o quantitativo e o valor estimado..."
**Transition:** answer_quant_value → ask_parcelamento

### 9. ask_parcelamento
**Purpose:** Ask about installment/phases
**Accepts:** sim, não, description
**Response:** "Haverá parcelamento da contratação..."
**Transition:** answer_parcelamento → confirm_summary

### 10. confirm_summary
**Purpose:** Show summary and get final confirmation
**Response:** Shows all collected data
**Accepts:** "pode gerar" to proceed
**Transition:** confirm_generate → generate_etp

### 11. generate_etp
**Purpose:** Generate the ETP document
**Response:** "Gerando o ETP..."
**Error:** Stays in state, offers retry
**Transition:** success → preview

### 12. preview
**Purpose:** Show preview and allow adjustments
**Response:** Shows preview, asks for final confirmation
**Transition:** confirm → finalize

### 13. finalize
**Purpose:** Terminal state
**Response:** "ETP finalizado! Você pode baixar..."
**Transition:** none (terminal)

## Intent Recognition

The system recognizes these intents:

1. **confirm** - Generic confirmation (ok, pode seguir, etc.)
2. **confirm_generate** - ETP generation confirmation (pode gerar, gerar etp)
3. **skip** - Skip/don't know (não sei, pular, depois)
4. **answer** - Generic text answer
5. **choose_path** - Solution path selection (compra, locação, serviço)
6. **answer_pca** - PCA response (sim, não, não informado)
7. **answer_legal_norms** - Legal norms text
8. **answer_quant_value** - Quantitative/value information
9. **answer_parcelamento** - Parcelamento response
10. **requirements_edit** - Requirement editing commands
11. **request_adjustment** - Summary adjustment request
12. **ask_clarification** - System asks for clarification

## Regex Patterns

### Generic Confirmation
```regex
\b(ok|pode seguir|seguir|segue|prosseguir|manter|aceito|acordo|concordo|fechou|confirmo|confirmado|perfeito|está bom|tá bom|pode manter|sim|correto)\b
```

### Generate Confirmation
```regex
\b(pode gerar|gerar etp|gera etp|fechou gerar|ok gerar|gerar)\b
```

### Skip Response
```regex
\b(não sei|nao sei|pular|depois|sem informação|não tenho|nao tenho|não informado|nao informado)\b
```

## Testing

### Run Tests
```bash
# Make sure server is running
python3 src/main/python/applicationApi.py

# In another terminal
python3 test_conversational_flow.py
```

### Test Coverage
- Complete 13-state flow
- Requirement editing (adjust, remove, include)
- Skip responses ("não sei", "pular")
- All confirmation patterns
- Error handling
- State persistence

## Example Conversation

```
AI: Olá! Para começar, me descreva em poucas palavras: qual a necessidade desta contratação?
USER: Preciso contratar manutenção de aeronaves

AI: Pelo que você descreveu, faz sentido garantir alguns requisitos...
    R1 — Conformidade com normas técnicas aplicáveis
    R2 — Capacidade de integração com sistemas existentes
    ...
    Se quiser ajustar, escreva 'ajustar 3: <novo texto>'...
USER: ajustar 3: Manutenção preventiva e corretiva mensal

AI: Lista atualizada. Mais algum ajuste ou posso seguir?
USER: incluir: Treinamento de equipe técnica

AI: Lista atualizada. Mais algum ajuste ou posso seguir?
USER: pode seguir

AI: Requisitos registrados. Posso sugerir o melhor caminho...
USER: ok

AI: Para atingir sua necessidade, normalmente existem três caminhos...
    • Compra: controle total...
    • Locação: baixo investimento...
    • Serviço: foco em desempenho...
USER: prefiro locação

AI: Registrado: Locação. Posso seguir?
USER: ok

AI: Você possui previsão no PCA?
USER: sim

AI: Quais normas legais pretende utilizar?
USER: Lei 14.133/21

... (continues through all states)
```

## Integration with Existing System

The conversational flow:
- Uses existing `EtpSession` model
- Integrates with RAG system for requirements
- Can coexist with other endpoints
- Independent from button-based flows

## Session Data Structure

```json
{
  "session_id": "uuid",
  "conversation_stage": "ask_pca",
  "necessity": "Contratar manutenção de aeronaves",
  "answers": {
    "requirements": [
      {"id": "R1", "text": "Conformidade..."},
      {"id": "R2", "text": "Integração..."}
    ],
    "solution_path": "locacao",
    "pca": "sim",
    "legal_norms": "Lei 14.133/21",
    "quant_value": "3 aeronaves, R$ 1.200.000 por ano",
    "parcelamento": "sim - por lotes regionais"
  }
}
```

## Error Handling

### Service Errors
```python
{
  "success": false,
  "error": "Error message",
  "ai_response": "Ocorreu um erro técnico... Vou permanecer nesta etapa...",
  "conversation_stage": "current_state",  # State unchanged
  "state_changed": false
}
```

### Unclear Intent
```python
{
  "success": true,
  "ai_response": "Clarification question",
  "conversation_stage": "current_state",
  "state_changed": false,
  "requires_clarification": true
}
```

## Validation Checklist (from Issue)

- [x] After necessity, suggests requirements with explanation, awaits text adjustments; no buttons
- [x] Only advances with "pode seguir" confirmation
- [x] Recommends path (compra/locação/serviço) before PCA
- [x] Asks in order: PCA → Normas → Quantitativo/Valor → Parcelamento
- [x] Shows summary and only generates with "pode gerar"
- [x] On generation error, doesn't advance; offers retry
- [x] Preview shown and finalization by text
- [x] Handles "não sei"/"pular" by marking as "não informado" and proceeding
- [x] Natural, human tone without jargon
- [x] No "Perfeito! Coletei todas as informações" before final confirmation

## Future Enhancements

1. **OpenAI Integration for Advanced Parsing**
   - Use GPT for ambiguous intent detection
   - Fallback to regex patterns
   - Context-aware clarification questions

2. **RAG Enhancement**
   - Better requirement suggestions based on domain
   - Context from previous similar ETPs

3. **Summary Adjustment**
   - Allow editing specific fields in confirm_summary
   - Go back to specific states

4. **Export Options**
   - PDF generation
   - DOCX export
   - HTML preview

## Troubleshooting

### State Not Advancing
- Check if user confirmation matches regex patterns
- Verify state transition is allowed in VALID_TRANSITIONS
- Check logs for intent parsing results

### Requirements Not Updating
- Verify command format: `ajustar N: texto`, `remover N`, `incluir: texto`
- Check session.set_requirements() is called and committed

### Skip Not Working
- Verify skip patterns in is_skip_response()
- Check intent parsing returns 'skip' intent
- Confirm state advances on skip

## Support

For issues or questions:
1. Check logs for [CONVERSATIONAL] markers
2. Review session data in database
3. Test with test_conversational_flow.py
4. Check state machine module for intent patterns
