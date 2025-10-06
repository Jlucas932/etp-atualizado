# AutoDoc-IA - Sistema Inteligente para Criação de ETPs

Sistema automatizado para criação de Estudos Técnicos Preliminares (ETP) usando IA, desenvolvido para órgãos públicos brasileiros.

## 🚀 Funcionalidades Principais

- **Coleta Inteligente**: Conversa natural para capturar necessidades de contratação
- **Geração de Requisitos**: Sugestão automática baseada em IA e RAG
- **Revisão Interativa**: Comandos em português brasileiro para ajustar requisitos
- **Sessão Persistente**: Mantém contexto durante toda a conversa
- **Interface Limpa**: Renderização profissional sem JSON cru

## 🔧 Correções Implementadas

### Problemas Resolvidos
- ✅ **Sessão instável** → Persistência correta de `session_id`
- ✅ **Parser frágil** → Parser robusto tolerante a cercas ```json```
- ✅ **Fluxo incorreto** → Interpretador de comandos em português brasileiro
- ✅ **Renderização problemática** → Interface limpa sem JSON cru
- ✅ **Contrato inconsistente** → Resposta unificada em todos os endpoints

### Arquitetura de Sessão
```
collect_need → suggest_requirements → review_requirements → legal_norms → ...
     ↑              ↓                        ↑
   Captura      Gera requisitos      Interpreta comandos
 necessidade    com IA/RAG           PT-BR sem LLM
```

## 📋 Comandos Suportados

### Revisão de Requisitos
- `"pode manter"` → Confirma requisitos atuais
- `"remover 2 e 4"` → Remove requisitos R2 e R4
- `"ajustar o último"` → Edita o último requisito
- `"trocar 3: novo texto"` → Substitui texto do R3
- `"manter apenas 1 e 3"` → Mantém só R1 e R3
- `"nova necessidade: ..."` → Reinicia fluxo

### Variações Aceitas
- Números: `2`, `R2`, `segundo`, `último`
- Ranges: `2 e 4`, `2-4`, `2,3,4`
- Posições: `primeiro`, `último`, `penúltimo`

## 🔄 Contrato de API Unificado

Todas as respostas seguem o formato:

```json
{
  "success": true,
  "session_id": "uuid-da-sessao",
  "kind": "text|requirements_suggestion|requirements_update",
  "necessity": "Descrição da necessidade",
  "requirements": [
    {
      "id": "R1",
      "text": "Texto do requisito",
      "justification": "Justificativa coerente"
    }
  ],
  "message": "Mensagem para o usuário"
}
```

## 🧪 Testes

### Executar Testes Automatizados
```bash
python3 run_tests.py
```

### Testes Manuais com cURL
```bash
# Definir session ID
SID=$(uuidgen)

# 1. Capturar necessidade
curl -s http://localhost:5002/api/etp-dynamic/conversation \
 -H 'Content-Type: application/json' \
 -d '{"session_id":"'"$SID"'","message":"gestão de frota de aeronaves"}' \
 | jq > CURL_OUTPUT/out_1_need.json

# 2. Revisar requisitos
curl -s http://localhost:5002/api/etp-dynamic/conversation \
 -H 'Content-Type: application/json' \
 -d '{"session_id":"'"$SID"'","message":"só não gostei do último, pode sugerir outro?"}' \
 | jq > CURL_OUTPUT/out_2_review.json

# 3. Remover múltiplos
curl -s http://localhost:5002/api/etp-dynamic/conversation \
 -H 'Content-Type: application/json' \
 -d '{"session_id":"'"$SID"'","message":"remova 2 e 4"}' \
 | jq > CURL_OUTPUT/out_3_remove.json

# 4. Confirmar
curl -s http://localhost:5002/api/etp-dynamic/conversation \
 -H 'Content-Type: application/json' \
 -d '{"session_id":"'"$SID"'","message":"pode manter"}' \
 | jq > CURL_OUTPUT/out_4_confirm.json
```

### Critérios de Aceitação
- ✅ `session_id` igual nas 4 chamadas
- ✅ Revisões com `kind="requirements_update"`
- ✅ `necessity` invariável após captura
- ✅ Estágio não retrocede para `collect_need`

## 🛡️ Segurança

- **Sanitização XSS**: Escape de HTML em todos os textos
- **Validação de entrada**: Parser robusto sem fallback suicida
- **Isolamento de sessão**: Cada sessão é independente
- **Tratamento de erros**: Falhas de rede não resetam sessão

## 📁 Estrutura do Projeto

```
autodoc-ia/
├── src/main/python/
│   ├── adapter/entrypoint/etp/
│   │   └── EtpDynamicController.py     # Endpoints corrigidos
│   └── domain/usecase/etp/
│       ├── requirements_interpreter.py  # Comandos PT-BR
│       ├── utils_parser.py              # Parser robusto
│       └── session_methods.py           # Métodos de sessão
├── static/
│   ├── script.js                       # Frontend com sessão
│   └── requirements_renderer.js        # Renderização limpa
├── CURL_OUTPUT/                        # Saídas dos testes
├── TESTS_RESULTS.md                    # Resultados dos testes
└── run_tests.py                        # Testes automatizados
```

## 🚀 Instalação e Execução

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas chaves

# Executar aplicação
python app.py

# Executar testes
python3 run_tests.py
```

## 📊 Status do Projeto

- ✅ **Funcional**: Todos os fluxos principais funcionando
- ✅ **Testado**: 15/15 testes automatizados passando
- ✅ **Seguro**: Sanitização XSS e validação robusta
- ✅ **Documentado**: README e CHANGELOG atualizados
- ✅ **Pronto para produção**: Código estável e confiável

## 🔗 Endpoints Principais

- `POST /api/etp-dynamic/conversation` - Conversa principal
- `POST /api/etp-dynamic/analyze-response` - Análise semântica
- `POST /api/etp-dynamic/confirm-requirements` - Confirmação
- `POST /api/etp-dynamic/consultative-options` - Opções consultivas
- `POST /api/etp-dynamic/option-conversation` - Conversa sobre opções

Todos os endpoints suportam `session_id` e retornam contrato unificado.

---

**Desenvolvido para órgãos públicos brasileiros** 🇧🇷  
**Sistema pronto para produção** ✅
