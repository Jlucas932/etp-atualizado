# Migrações de Banco de Dados - Alembic

Este diretório contém as migrações de schema do banco de dados usando Alembic.

## Comandos Principais

### Aplicar migrações (upgrade)

```bash
# Aplicar todas as migrações pendentes
alembic upgrade head

# Aplicar até uma revisão específica
alembic upgrade <revision_id>

# Aplicar próxima migração
alembic upgrade +1
```

### Reverter migrações (downgrade)

```bash
# Reverter última migração
alembic downgrade -1

# Reverter até uma revisão específica
alembic downgrade <revision_id>

# Reverter todas as migrações
alembic downgrade base
```

### Criar novas migrações

```bash
# Criar migração vazia (manual)
alembic revision -m "descrição da mudança"

# Criar migração autogenerate (detecta mudanças nos modelos)
alembic revision --autogenerate -m "descrição da mudança"
```

### Histórico e status

```bash
# Ver histórico de migrações
alembic history

# Ver migração atual
alembic current

# Ver migrações pendentes
alembic history --indicate-current
```

## Configuração

### Variáveis de Ambiente

As migrações usam a variável `DATABASE_URL` do arquivo `.env`:

```bash
# PostgreSQL
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/dbname

# MySQL
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/dbname

# SQL Server
DATABASE_URL=mssql+pyodbc://user:pass@localhost:1433/dbname?driver=ODBC+Driver+17+for+SQL+Server

# SQLite (desenvolvimento)
DATABASE_URL=sqlite:///./data/autodoc.db
```

### Naming Convention

As migrações usam `naming_convention` para garantir nomes de constraints portáveis entre SGBDs:

- **Índices:** `ix_<column_name>`
- **Unique:** `uq_<table_name>_<column_name>`
- **Check:** `ck_<table_name>_<constraint_name>`
- **Foreign Key:** `fk_<table_name>_<column_name>_<referred_table_name>`
- **Primary Key:** `pk_<table_name>`

## Portabilidade Multi-SGBD

As migrações são compatíveis com:
- ✅ PostgreSQL (psycopg2)
- ✅ MySQL/MariaDB (pymysql)
- ✅ SQL Server (pyodbc)
- ✅ SQLite (desenvolvimento)

**Dicas para portabilidade:**
1. Use tipos genéricos do SQLAlchemy (`String`, `Integer`, `Text`) ao invés de tipos específicos
2. Evite SQL raw quando possível
3. Use `batch_alter_table` para SQLite (não suporta ALTER TABLE completo)
4. Teste migrações em todos os SGBDs alvo antes de deploy

## Fluxo de Trabalho

### 1. Desenvolvimento Local

```bash
# 1. Modificar modelos em domain/dto/
# 2. Criar migração
alembic revision --autogenerate -m "adicionar campo X na tabela Y"

# 3. Revisar arquivo gerado em alembic/versions/
# 4. Testar upgrade
alembic upgrade head

# 5. Testar downgrade
alembic downgrade -1

# 6. Se OK, fazer upgrade novamente
alembic upgrade head
```

### 2. Deploy em Produção

```bash
# 1. Fazer backup do banco de dados
pg_dump -h localhost -U user dbname > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Aplicar migrações
alembic upgrade head

# 3. Verificar status
alembic current

# 4. Se houver problema, reverter
alembic downgrade -1
```

## Troubleshooting

### Erro: "Can't locate revision identified by '<revision_id>'"

**Causa:** Banco de dados não está sincronizado com as migrações.

**Solução:**
```bash
# Marcar banco como estando na revisão atual (sem executar SQL)
alembic stamp head
```

### Erro: "Target database is not up to date"

**Causa:** Há migrações pendentes.

**Solução:**
```bash
alembic upgrade head
```

### Erro: "ModuleNotFoundError: No module named 'domain'"

**Causa:** Path do Python não está configurado corretamente.

**Solução:** Executar alembic da raiz do projeto:
```bash
cd /path/to/autodoc-ia-fixed
alembic upgrade head
```

### Conflito de Migrações (branches)

**Causa:** Múltiplos desenvolvedores criaram migrações em paralelo.

**Solução:**
```bash
# Mesclar branches de migração
alembic merge -m "merge branches" <revision1> <revision2>
```

## Migração Inicial

A migração inicial (`d39055272e4d_initial_schema.py`) cria todas as tabelas:

- `users` - Usuários do sistema
- `etp_sessions` - Sessões de geração de ETP
- `etp_templates` - Templates de ETP
- `chat_sessions` - Histórico de chat
- `document_analyses` - Análises de documentos
- `knowledge_base` - Base de conhecimento (legado)
- `kb_document` - Documentos da base de conhecimento
- `kb_chunk` - Chunks de documentos para RAG
- `legal_norm_cache` - Cache de normas legais

## Referências

- [Documentação Alembic](https://alembic.sqlalchemy.org/)
- [Tutorial Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
