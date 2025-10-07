"""
Pacote de retrieval unificado.

- Mantém compatibilidade com imports legados, ex.:
    from rag.retrieval import get_retrieval_instance, search_requirements
- Reexporta símbolos definidos em .hybrid (antigo retrieval.py)
- FAISS segue opcional; se não instalado, BM25 permanece como fallback.
"""

from .hybrid import (
    RAGRetrieval,
    get_retrieval_instance,
    search_requirements,
    build_indices,
    search_legal,
)

# Exporta FaissIndex se disponível (opcional)
try:
    from .faiss_index import FaissIndex  # noqa: F401
except Exception:  # pragma: no cover
    FaissIndex = None  # type: ignore[assignment]

__all__ = [
    "RAGRetrieval",
    "get_retrieval_instance",
    "search_requirements",
    "build_indices",
    "search_legal",
    "FaissIndex",
]
