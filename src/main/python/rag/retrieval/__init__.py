"""
Pacote de retrieval unificado.

- Mantém compatibilidade com imports legados, ex.:
    from rag.retrieval import get_retrieval_instance, search_requirements
- Reexporta símbolos definidos em .hybrid (antigo retrieval.py)
- FAISS segue opcional; se não instalado, BM25 permanece como fallback.
"""

# Reexporta API pública do módulo 'hybrid' (antigo retrieval.py)
from .hybrid import (
    RAGRetrieval,
    get_retrieval_instance,
    search_requirements,
    build_indices,
    search_legal,
    # ↳ adicione aqui quaisquer outros símbolos públicos que antes vinham de rag.retrieval
)

# Exporta FaissIndex se disponível (não obrigatório)
try:
    from .faiss_index import FaissIndex  # noqa: F401
except Exception:  # pragma: no cover - módulo opcional
    # FAISS não instalado → sem erro; pacote segue funcional via BM25
    FaissIndex = None  # type: ignore[assignment]

__all__ = [
    "RAGRetrieval",
    "get_retrieval_instance",
    "search_requirements",
    "build_indices",
    "search_legal",
    "FaissIndex",
]
