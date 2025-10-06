"""Ponto de entrada para execução da API com Gunicorn ou Flask nativo."""

import logging
import os
from datetime import datetime

from dotenv import load_dotenv

# Carregar variáveis de ambiente antes de inicializar o app
load_dotenv()

from application.config.FlaskConfig import create_api  # noqa: E402

# Alias utilizado pelo Gunicorn (applicationApi:app)
create_app = create_api


def _enforce_valid_openai_key() -> str:
    """Garante que a chave OpenAI configurada não seja um placeholder."""

    api_key = os.getenv('OPENAI_API_KEY', '')
    if api_key == 'sua_api_key_aqui':
        logging.getLogger(__name__).error(
            "OPENAI_API_KEY configurada com placeholder. Atualize o .env antes de iniciar a aplicação."
        )
        raise SystemExit(1)

    return api_key


def _initialize_rag(api_key: str) -> None:
    """Inicializa componentes opcionais do pipeline RAG."""

    logger = logging.getLogger(__name__)

    try:
        from pathlib import Path
        import os

        import openai

        from rag.retrieval import get_retrieval_instance

        index_dir = Path(os.getenv('RAG_FAISS_PATH', 'src/main/python/rag/index/faiss'))
        if not index_dir.exists() or not (index_dir / 'etp_index.faiss').exists():
            logger.info(
                "Índices FAISS não encontrados — operação seguirá com fallback BM25."
            )
            logger.info("Execute 'python -m rag.ingest_etps --rebuild' para gerar os índices.")
            return

        logger.info("Carregando índices FAISS para o pipeline RAG...")

        openai_client = None
        if api_key:
            try:
                openai_client = openai.OpenAI(api_key=api_key)
            except Exception as exc:  # pragma: no cover - apenas log defensivo
                logger.warning("Não foi possível inicializar cliente OpenAI: %s", exc)

        retrieval = get_retrieval_instance(openai_client=openai_client)
        if retrieval.build_indices():
            logger.info("Pipeline RAG inicializado com sucesso.")
        else:
            logger.warning("Falha ao construir índices RAG; operação seguirá apenas com BM25.")

    except Exception as exc:  # pragma: no cover - apenas log defensivo
        logger.exception("Erro ao inicializar sistema RAG: %s", exc)


try:
    app = create_app()
except Exception:  # pragma: no cover - garantimos que a exceção seja propagada
    logging.getLogger(__name__).exception("Falha ao criar a aplicação Flask.")
    raise


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    api_key = _enforce_valid_openai_key()

    logger.info("🚀 Iniciando servidor ETP Sistema Padronizado (Docker)...")
    logger.info("📍 Acesse: http://localhost:5002")
    logger.info("🔄 Para parar o servidor: Ctrl+C")
    logger.info("🕒 Iniciado em: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    with app.app_context():
        _initialize_rag(api_key)

    app.run(
        host="0.0.0.0",
        port=5002,
        debug=False,
        use_reloader=False,
    )

