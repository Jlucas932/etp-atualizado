# trecho dentro do handler POST do chat, após ler user_message
from sqlalchemy import text as sql_text
from domain.interfaces.dataprovider.DatabaseConfig import db

q = (body.get("message") or "").strip()
context_snippets = ""
if q:
    # tenta full-text; se não tiver dicionário pt, cai no ILIKE
    try:
        rows = db.session.execute(sql_text("""
            SELECT content_text
            FROM kb_chunk
            WHERE to_tsvector('portuguese', content_text) @@ plainto_tsquery('portuguese', :q)
            ORDER BY ts_rank(to_tsvector('portuguese', content_text), plainto_tsquery('portuguese', :q)) DESC
            LIMIT 5
        """), {"q": q}).fetchall()
    except Exception:
        rows = db.session.execute(sql_text("""
            SELECT content_text
            FROM kb_chunk
            WHERE content_text ILIKE '%' || :q || '%'
            ORDER BY id DESC
            LIMIT 5
        """), {"q": q}).fetchall()

    if rows:
        context_snippets = "\n\n".join([r[0][:800] for r in rows])

# depois, ao montar a prompt do modelo:
if context_snippets:
    system_context = f"""Use APENAS os trechos a seguir para responder. Se algo não estiver coberto nos trechos, diga que não há base nos documentos ingeridos.
Trechos:
{context_snippets}
"""
    # injete system_context no role=system ou no prefixo da prompt conforme seu gerador
