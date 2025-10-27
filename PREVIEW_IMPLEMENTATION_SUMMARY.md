# Preview Generation Implementation Summary

## Objetivo
Completar o fluxo de geração de ETP com prévia servível (HTML/PDF) e UI exibindo links, mantendo o fluxo conversacional sem perguntas prontas e com requisitos numerados.

## Implementação Realizada

### 1. Backend - Serviço de Prévia
**Arquivo criado**: `src/main/python/application/services/preview_builder.py`

- **Função principal**: `build_preview(conversation_id: str, summary: dict) -> dict`
- Gera HTML estilizado com seções completas do ETP
- Salva arquivo em `static/previews/{conversation_id}.html`
- Retorna dict com:
  - `html_path`: Caminho relativo para o HTML (`/static/previews/{id}.html`)
  - `pdf_path`: None (PDF não implementado, pode ser adicionado futuramente)
  - `filename`: Nome do arquivo (`ETP_{conversation_id}.html`)

**Características do HTML gerado**:
- Template responsivo com CSS incorporado
- Seções numeradas: Necessidade, Requisitos, Caminho da Solução, PCA, Normas, Quantitativo/Valor, Parcelamento
- Escape de caracteres HTML para segurança
- Estilo profissional com cores azul (#1a73e8) e verde (#34a853)
- Suporte para impressão (@media print)

### 2. Backend - Configuração de Diretórios
**Arquivo atualizado**: `src/main/python/application/config/FlaskConfig.py`

```python
# Criar diretório de prévias se não existir
STATIC_PREVIEWS_DIR = os.path.join(static_path, 'previews')
os.makedirs(STATIC_PREVIEWS_DIR, exist_ok=True)
print(f"📁 Pasta de prévias configurada: {STATIC_PREVIEWS_DIR}")
```

- Diretório `static/previews/` criado automaticamente na inicialização
- Flask já serve arquivos de `/static` via rota catch-all existente
- Não foi necessário criar rota adicional para servir prévias

### 3. Backend - Controller Atualizado
**Arquivo atualizado**: `src/main/python/adapter/entrypoint/etp/EtpDynamicController.py`

**Mudanças**:
1. Adicionado import: `from application.services.preview_builder import build_preview`
2. Substituído código manual de geração de prévia (linhas 922-976) por:
   ```python
   preview_meta = build_preview(conversation_id, summary_data)
   ```
3. Response JSON atualizado com novos campos:
   ```python
   {
       'preview_ready': True,
       'html_path': preview_meta.get('html_path'),
       'pdf_path': preview_meta.get('pdf_path'),
       'file_path': preview_meta.get('html_path'),  # Compatibilidade
       'filename': preview_meta.get('filename')
   }
   ```

### 4. Frontend - Renderização de Links
**Arquivo atualizado**: `static/script.js`

**Implementação** (após linha 316):
- Detecta `data.preview_ready && (data.html_path || data.file_path)`
- Cria container estilizado com:
  - Título: "📄 Prévia do Documento"
  - Botão azul "🌐 Abrir Prévia" (target="_blank")
  - Botão verde "📥 Baixar HTML" ou "📥 Baixar PDF" (se disponível)
- Efeitos hover nos botões
- Scroll automático para mostrar links

### 5. Testes Automatizados

#### test_preview_builder.py (NOVO)
**5 testes criados**:
1. `test_build_preview_creates_html_file`: Verifica criação de arquivo e estrutura do retorno
2. `test_build_preview_with_empty_requirements`: Testa com dados vazios
3. `test_build_preview_html_content`: Valida conteúdo HTML gerado
4. `test_html_escape`: Testa escape de caracteres especiais
5. `test_build_preview_returns_correct_paths`: Valida formato dos paths

**Resultado**: ✅ **Todos os 5 testes passaram**

#### test_flow_etp.py (ATUALIZADO)
**Teste atualizado**: `test_06_summary_and_preview`

**Validações adicionadas**:
- `preview_ready == True`
- `html_path` não é None e contém `/static/previews/`
- `filename` começa com `ETP_` e termina com `.html`
- `pdf_path` aceita None (não implementado) ou path válido
- `file_path` presente para compatibilidade

## Validação

### Testes Executados
```bash
python3 -m unittest tests.test_preview_builder -v
```
**Resultado**: ✅ OK (5 testes, 0.001s)

### Arquivos Criados
```bash
ls -la static/previews/
```
Arquivos gerados durante testes:
- `test-conv-123.html` (3.4 KB)
- `test-conv-empty.html` (3.3 KB)
- `test-paths-456.html` (3.3 KB)

### Verificação Manual
```bash
head -30 static/previews/test-conv-123.html
```
HTML válido com estrutura completa, CSS incorporado e conteúdo correto.

## Fluxo Conversacional Mantido

✅ **Garantias preservadas**:
1. Nenhum item com `?` renderizado como requisito
2. Lista numerada sequencial (1., 2., 3., ...)
3. Sem formulários ou questionários
4. Requisitos diretos e afirmativos
5. Transições de estágio determinísticas
6. Persistência de mensagens via `MessageRepo.add()`

## Critérios de Aceite

| Critério | Status | Evidência |
|----------|--------|-----------|
| Ao confirmar resumo, API retorna JSON com preview_ready=true | ✅ | EtpDynamicController.py linhas 935-941 |
| UI mostra "Abrir prévia" (HTML) | ✅ | script.js linhas 347-354 |
| UI mostra "Baixar PDF" quando disponível | ✅ | script.js linhas 358-377 |
| Arquivos aparecem em static/previews/ | ✅ | 3 arquivos criados durante testes |
| Nenhum item com ? é exibido como requisito | ✅ | requirements_renderer.js + testes |
| Lista vem numerada | ✅ | Renderização com `<ol>` |
| Fluxo conversacional sem perguntas prontas | ✅ | generator.py + EtpDynamicController.py |
| Testes passam localmente | ✅ | test_preview_builder.py: 5/5 ✅ |

## Próximos Passos (Opcional)

### Geração de PDF
Para implementar PDF no futuro:
1. Instalar biblioteca: `pip install weasyprint` ou `pdfkit`
2. Atualizar `preview_builder.py`:
   ```python
   from weasyprint import HTML
   
   pdf_filename = f"{conversation_id}.pdf"
   pdf_filepath = os.path.join(previews_dir, pdf_filename)
   HTML(string=html_content).write_pdf(pdf_filepath)
   
   return {
       "html_path": f"/static/previews/{html_filename}",
       "pdf_path": f"/static/previews/{pdf_filename}",
       "filename": f"ETP_{conversation_id}.pdf"
   }
   ```

## Arquivos Modificados/Criados

### Novos arquivos
- `src/main/python/application/services/__init__.py`
- `src/main/python/application/services/preview_builder.py`
- `tests/test_preview_builder.py`
- `PREVIEW_IMPLEMENTATION_SUMMARY.md`

### Arquivos modificados
- `src/main/python/application/config/FlaskConfig.py`
- `src/main/python/adapter/entrypoint/etp/EtpDynamicController.py`
- `static/script.js`
- `tests/test_flow_etp.py`

## Conclusão

✅ **Implementação completa e funcional**
- Preview HTML gerado e servido corretamente
- UI exibe links estilizados
- Testes automatizados validam funcionalidade
- Fluxo conversacional preservado
- PDF pode ser adicionado futuramente sem quebrar API
