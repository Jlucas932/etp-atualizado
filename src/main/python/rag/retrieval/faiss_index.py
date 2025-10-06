try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None
import numpy as np

class FaissIndex:
    def __init__(self, dimension):
        if faiss is None:
            raise RuntimeError("FAISS não está disponível neste ambiente.")
        self.index = faiss.IndexFlatL2(dimension)

    def add(self, vectors):
        self.index.add(np.asarray(vectors, dtype=np.float32))

    def search(self, query_vector, top_n=5):
        distances, indices = self.index.search(np.asarray([query_vector], dtype=np.float32), top_n)
        return list(zip(indices[0], distances[0]))

