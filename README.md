# AutoDoc IA

O **AutoDoc IA** é um sistema inteligente para auxiliar na criação de **documentos técnicos e institucionais** de forma automatizada. Ele combina **Inteligência Artificial** com análise de documentos de referência para gerar conteúdos estruturados, seguindo padrões de órgãos públicos e boas práticas de gestão documental.

## 🚀 Funcionalidades

- **Criação de ETP (Estudos Técnicos Preliminares)** a partir das informações fornecidas pelo usuário.
- **Chat inteligente** para responder dúvidas relacionadas a contratações públicas e normas aplicáveis.
- **Análise de documentos modelo** já existentes no sistema para gerar novos arquivos padronizados.
- **Upload de arquivos** em formatos como PDF, DOCX e TXT, com extração automática do conteúdo.
- **API REST** para integração com outros sistemas.
- **Interface Web responsiva** para interação com usuários.
- **Gerenciamento via Docker** para rápida implantação em qualquer ambiente.

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python (Flask)
- **Frontend:** HTML, CSS, JavaScript
- **Banco de Dados:** PostgreSQL
- **Infraestrutura:** Docker e Docker Compose
- **Bibliotecas Principais:**
    - PyPDF2 / pdfplumber (extração de textos de PDF)
    - python-docx (manipulação de arquivos DOCX)
    - Flask / Flask-Restful (API e controllers)

## 📂 Estrutura do Projeto

```
.
├── docker-compose.yml        # Orquestração dos containers
├── init.sql                  # Script inicial do banco
├── start.sh                  # Script de inicialização
├── requirements.txt          # Dependências do Python
├── src/                      # Código-fonte principal
│   ├── main/python/          # Aplicação e controllers
│   ├── adapter/              # Gateways e entrypoints
│   ├── application/          # Configuração e fábricas
│   ├── domain/               # Entidades, DTOs e interfaces
│   └── ...
```

## ⚙️ Instalação e Execução

1. **Clonar o repositório**
   ```bash
   git clone <repo_url>
   cd autodoc-ia
   ```

2. **Configurar variáveis de ambiente**  
   Copiar o arquivo `.env.example` para `.env` e ajustar os valores.

3. **Subir os containers com Docker Compose**
   ```bash
   docker-compose up -d --build
   ```

4. **Executar migrações e iniciar o sistema**
   ```bash
   ./start.sh
   ```

5. A aplicação estará disponível em:
   ```
   http://localhost:5000
   ```

## 📌 Endpoints Principais

- `GET /health` → Verifica status da API
- `POST /api/chat` → Envia perguntas para o chat inteligente
- `POST /api/etp` → Gera um novo documento ETP
- `POST /api/upload` → Faz upload e processa documentos

## ✅ Próximos Passos

- Melhorar a barra de progresso para refletir a execução real.
- Implementar streaming de respostas no chat.
- Expandir suporte para novos tipos de documentos e templates.

## 📄 Licença

Este projeto é de uso interno e segue as diretrizes da organização.  
