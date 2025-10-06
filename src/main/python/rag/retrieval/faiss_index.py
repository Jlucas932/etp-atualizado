import faiss
import numpy as np

class FaissIndex:
    def __init__(self, dimension):
        self.index = faiss.IndexFlatL2(dimension)

    def add(self, vectors):
        self.index.add(np.array(vectors, dtype=\'np.float32\'))

    def search(self, query_vector, top_n=5):
        distances, indices = self.index.search(np.array([query_vector], dtype=\'np.float32\'), top_n)
        return list(zip(indices[0], distances[0]))

