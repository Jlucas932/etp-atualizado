## CHANGELOG

### v3.0.0 (2025-09-30)

**Funcionalidades Adicionadas:**

- **Busca Híbrida:** Implementado sistema de busca híbrida combinando FAISS (semântico) e BM25 (léxico) para resultados de recuperação mais precisos.
- **Plano Alternativo de Ingestão (PDF→JSON):** Adicionada a capacidade de converter PDFs para um formato JSON estruturado antes da ingestão, controlável através da variável de ambiente `INGEST_MODE`.
- **Cadeia de Veracidade:** As respostas geradas agora incluem citações e evidências da base de conhecimento, aumentando a transparência e a confiabilidade.
- **Deduplicação de Documentos:** Implementado sistema de deduplicação para evitar o processamento de documentos duplicados.

**Melhorias:**

- **Comportamento Consultivo:** O sistema agora lista todos os requisitos relevantes, sem o limite artificial de 5, e os agrupa por tema quando a lista é longa.
- **Formatação de Resposta:** Removidas as molduras/caixas das respostas, que agora são formatadas com Markdown leve para uma aparência de chat mais natural.
- **Numeração de Requisitos:** A numeração de requisitos foi padronizada para 1, 2, 3... em toda a aplicação, eliminando o prefixo "R".
- **Chunking Otimizado:** A estratégia de chunking foi refinada para um tamanho alvo de 800-1200 tokens com uma sobreposição de 10-15%.
- **Prompts Externalizados:** Os prompts do sistema, recuperador e formatador foram movidos para arquivos de texto externos para facilitar a manutenção.

**Correções de Bugs:**

- **Encoding UTF-8:** Corrigidos problemas de encoding em todo o pipeline, garantindo a consistência do tratamento de caracteres especiais.
- **Loop de Estágio da Conversa:** Corrigido o bug que fazia o fluxo da conversa reiniciar para a etapa de coleta de necessidade após a aceitação dos requisitos.
- **Índice BM25 Ausente:** Implementada a função `_create_bm25_index` que estava faltando no processo de ingestão.

**Outras Mudanças:**

- **Scripts CLI:** Adicionados novos scripts para ingestão de PDFs e JSONs, conversão de PDF para JSON, construção de índices e demonstração de ponta a ponta.
- **Configurações de Ambiente:** O arquivo `.env.example` foi atualizado com novas variáveis para controlar o modo de ingestão, cache de embeddings, e parâmetros da busca híbrida.
- **Testes:** Adicionados testes de integração para validar o fluxo da conversa e a correção do loop de estágio.

### v2.0.0 (2024-12-29)

**Correções Críticas Implementadas:**

- **Sessão instável:** Nova sessão criada a cada mensagem → Persistência correta de `session_id`
- **Parser frágil:** Falhas com cercas ```json``` → Parser robusto tolerante
- **Fluxo incorreto:** "pode manter" virava nova necessidade → Interpretador PT-BR
- **Renderização problemática:** JSON cru na interface → Interface limpa
- **Contrato inconsistente:** Endpoints com formatos diferentes → Contrato unificado

