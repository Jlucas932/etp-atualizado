import sys, os

# Caminho absoluto até src/main/python dentro do container
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src", "main", "python")
sys.path.append(SRC_DIR)

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.KbDto import KbChunk
from infrastructure.embedding.openai_embedder import OpenAIEmbedder

embedder = OpenAIEmbedder()

chunks = db.session.query(KbChunk).filter(KbChunk.embedding == None).all()
print(f"Encontrados {len(chunks)} chunks sem embedding.")

for chunk in chunks:
    embedding = embedder.embed(chunk.content_text)
    chunk.embedding = embedding
    db.session.add(chunk)

db.session.commit()
print("Embeddings atualizados com sucesso!")
