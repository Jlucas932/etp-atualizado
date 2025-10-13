import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src", "main", "python")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from application.config.FlaskConfig import create_api
from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.KbDto import KbChunk
from openai import OpenAI


def get_embedding(client: OpenAI, text: str):
    """Gera embedding usando OpenAI API"""
    try:
        response = client.embeddings.create(model="text-embedding-3-small", input=text)
        return response.data[0].embedding
    except Exception as e:
        print(f"Erro ao gerar embedding: {e}")
        return None


def main():
    app = create_api()
    client = OpenAI()
    with app.app_context():
        chunks = db.session.query(KbChunk).filter(KbChunk.embedding == None).all()
        print(f"Encontrados {len(chunks)} chunks sem embedding.")
        for chunk in chunks:
            embedding = get_embedding(client, chunk.content_text)
            if embedding:
                chunk.embedding = embedding
                db.session.add(chunk)
        db.session.commit()
        print("Embeddings atualizados com sucesso!")


if __name__ == "__main__":
    main()
