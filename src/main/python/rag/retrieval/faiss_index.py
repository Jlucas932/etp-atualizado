import numpy as np

try:
    import faiss  # type: ignore
    _FAISS_AVAILABLE = True
except Exception:  # pragma: no cover
    _FAISS_AVAILABLE = False


class FaissIndex:
    def __init__(self, dimension: int):
        if not _FAISS_AVAILABLE:
            raise RuntimeError("FAISS não está instalado; não é possível usar FaissIndex.")
        self.index = faiss.IndexFlatL2(int(dimension))

    def add(self, vectors):
        arr = np.asarray(vectors, dtype=np.float32)
        self.index.add(arr)

    def search(self, query_vector, top_n: int = 5):
        q = np.asarray([query_vector], dtype=np.float32)
        distances, indices = self.index.search(q, int(top_n))
        return list(zip(indices[0], distances[0]))

