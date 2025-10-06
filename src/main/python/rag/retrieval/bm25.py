from rank_bm25 import BM25Okapi

class BM25Index:
    def __init__(self, documents):
        self.documents = documents
        self.tokenized_documents = [doc.split(" ") for doc in documents]
        self.bm25 = BM25Okapi(self.tokenized_documents)

    def search(self, query, top_n=5):
        tokenized_query = query.split(" ")
        doc_scores = self.bm25.get_scores(tokenized_query)
        top_n_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:top_n]
        return [(i, doc_scores[i]) for i in top_n_indices]

