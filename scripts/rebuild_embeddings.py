import os
import sys

# Ajusta sys.path para importar módulos do projeto
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src", "main", "python")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from application.config.FlaskConfig import create_api
from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.KbDto import KbChunk
from infrastructure.embedding.openai_embedder import OpenAIEmbedder


def main():
    app = create_api()
    embedder = OpenAIEmbedder()
    with app.app_context():
        chunks = db.session.query(KbChunk).filter(KbChunk.embedding == None).all()
        print(f"Encontrados {len(chunks)} chunks sem embedding.")
        for chunk in chunks:
            embedding = embedder.embed(chunk.content_text)
            chunk.embedding = embedding
            db.session.add(chunk)
        db.session.commit()
        print("Embeddings atualizados com sucesso!")


if __name__ == "__main__":
    main()
