# autodoc-ia: Consultor RAG para ETPs

## Visão Geral

O **autodoc-ia** é um sistema de Geração Aumentada por Recuperação (RAG) projetado para atuar como um consultor especialista na criação de Estudos Técnicos Preliminares (ETP). Ele utiliza uma base de conhecimento de documentos para sugerir requisitos, garantir a conformidade e agilizar o processo de elaboração de ETPs.

## Funcionalidades Principais

- **Fluxo de Conversa Consultivo:** Interaja com o sistema de forma natural, como se estivesse conversando com um consultor humano.
- **Geração de Requisitos Inteligente:** O sistema sugere requisitos com base na sua necessidade, utilizando uma base de conhecimento de ETPs anteriores.
- **Busca Híbrida (FAISS + BM25):** Combina busca semântica e lexical para encontrar os requisitos mais relevantes.
- **Cadeia de Veracidade:** Todas as sugestões são acompanhadas de evidências da base de conhecimento, garantindo transparência e rastreabilidade.
- **Flexibilidade na Ingestão de Dados:** Suporta a ingestão de documentos tanto no formato PDF quanto em um formato JSON estruturado.

## Como Rodar o Projeto

### Pré-requisitos

- Docker e Docker Compose
- Python 3.11+
- Conta na OpenAI com uma chave de API válida

### Configuração

1.  **Clone o repositório:**
    ```bash
    git clone <url-do-repositorio>
    cd autodoc-ia
    ```

2.  **Configure as variáveis de ambiente:**
    - Renomeie o arquivo `.env.example` para `.env`.
    - Preencha as variáveis de ambiente no arquivo `.env`, especialmente a `OPENAI_API_KEY`.

### Execução

1.  **Suba os contêineres:**
    ```bash
    docker-compose up -d
    ```

2.  **Ingestão de Dados:**
    - Para ingerir dados a partir de arquivos PDF:
      ```bash
      make ingest_pdf
      ```
    - Para ingerir dados a partir de arquivos JSON:
      ```bash
      make ingest_json
      ```

3.  **Construção dos Índices:**
    ```bash
    make build_indexes
    ```

4.  **Acesse a aplicação:**
    - Abra seu navegador e acesse `http://localhost:5002`.

### Testes

- Para rodar os testes unitários e de integração:
  ```bash
  make test
  ```

- Para rodar a demonstração de ponta a ponta:
  ```bash
  make e2e
  ```

## Estrutura do Projeto

- `src/`: Código fonte da aplicação.
  - `main/python/adapter/`: Adaptadores para entrada e saída (ex: controllers da API).
  - `main/python/domain/`: Lógica de negócio e regras de domínio.
  - `main/python/rag/`: Componentes do sistema RAG (ingestão, recuperação, etc.).
- `scripts/`: Scripts para automação de tarefas (ingestão, testes, etc.).
- `prompts/`: Arquivos de texto com os prompts utilizados pelo sistema.
- `knowledge/`: Base de conhecimento de documentos.
- `tests/`: Testes automatizados.
- `reports/`: Relatórios de auditoria e métricas.
