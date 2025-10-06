# Problemas Identificados no Projeto autodoc-ia

## 1. Erro Principal: "string indices must be integers, not 'str'"

**Localização**: `domain/usecase/etp/utils_parser.py` - função `parse_requirements_response_safely`

**Causa**: A função está tentando acessar índices de string como se fosse um dicionário. Isso acontece quando:
- A resposta do OpenAI vem como string JSON mas não é parseada corretamente
- O código tenta acessar `response['suggested_requirements']` quando `response` é uma string

**Evidência**: No arquivo `EtpDynamicController.py` linha ~810, a função `parse_requirements_response_safely` é chamada diretamente na resposta do OpenAI.

## 2. Problemas de Parsing Inconsistente

**Localização**: `domain/usecase/etp/utils_parser.py`

**Problemas encontrados**:
- A função `parse_requirements_response_safely` não trata adequadamente quando a resposta vem como string JSON
- Não há validação consistente do tipo de dados recebidos
- Falta tratamento para respostas malformadas do OpenAI

## 3. Parâmetro `top_k` vs `k` na função search_requirements

**Localização**: `rag/retrieval.py`

**Problema**: 
- A função `search_requirements` espera parâmetro `k` (linha 285)
- Algumas chamadas podem estar passando `top_k` em vez de `k`
- Isso pode causar TypeError em algumas situações

## 4. Estrutura de Resposta Inconsistente

**Problema**: O sistema espera respostas em formatos diferentes:
- Formato novo: `{"suggested_requirements": [...], "consultative_message": "..."}`
- Formato legado: `{"requirements": [...]}`
- Às vezes recebe strings JSON que precisam ser parseadas

## 5. Tratamento de Erros Insuficiente

**Problemas**:
- Falta de validação de tipos antes de acessar propriedades
- Não há fallbacks adequados quando o parsing falha
- Logs insuficientes para debug

## 6. Possíveis Problemas de Sintaxe

**Status**: Verificação inicial não encontrou erros de sintaxe nos arquivos principais
- `utils_parser.py`: ✅ Compilação OK
- `EtpDynamicController.py`: ✅ Compilação OK

## Próximos Passos

1. Corrigir a função `parse_requirements_response_safely` para tratar strings JSON adequadamente
2. Padronizar o tratamento de respostas do OpenAI
3. Garantir que todas as chamadas para `search_requirements` usem o parâmetro correto
4. Adicionar validação robusta de tipos
5. Implementar fallbacks seguros para casos de erro
