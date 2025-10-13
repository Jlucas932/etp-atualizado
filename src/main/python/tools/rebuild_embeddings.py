import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from openai import OpenAI


def get_embedding(client: OpenAI, text: str):
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


def main():
    from application.config.FlaskConfig import create_api
    from domain.interfaces.dataprovider.DatabaseConfig import db
    from domain.dto.KbDto import KbChunk

    app = create_api()
    client = OpenAI()

    with app.app_context():
        chunks = db.session.query(KbChunk).filter(KbChunk.embedding == None).all()
        print(f"Encontrados {len(chunks)} chunks sem embedding.")

        for chunk in chunks:
            embedding = get_embedding(client, chunk.content_text)
            if embedding:
                # Se a coluna embedding foi criada como ARRAY(Float):
                chunk.embedding = embedding
                # Se foi criada como Text/JSON, troque a linha acima por:
                # chunk.embedding = json.dumps(embedding)
                db.session.add(chunk)

        db.session.commit()
        print("Embeddings atualizados com sucesso!")


if __name__ == "__main__":
    main()
