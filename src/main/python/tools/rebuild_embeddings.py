import sys, os, json
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.KbDto import KbChunk
from openai import OpenAI

# Cliente OpenAI já configurado via variável de ambiente
client = OpenAI()

def get_embedding(text: str):
    """Gera embedding usando OpenAI API"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Erro ao gerar embedding: {e}")
        return None

chunks = db.session.query(KbChunk).filter(KbChunk.embedding == None).all()
print(f"Encontrados {len(chunks)} chunks sem embedding.")

for chunk in chunks:
    embedding = get_embedding(chunk.content_text)
    if embedding:
        # Se a coluna embedding foi criada como ARRAY(Float):
        chunk.embedding = embedding
        # Se foi criada como Text/JSON, troca a linha acima por:
        # chunk.embedding = json.dumps(embedding)
        db.session.add(chunk)

db.session.commit()
print("Embeddings atualizados com sucesso!")
