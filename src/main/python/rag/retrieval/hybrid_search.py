from .bm25 import BM25Index
from .faiss_index import FaissIndex

def hybrid_search(query, bm25_index: BM25Index, faiss_index: FaissIndex, query_vector, top_n=5, w_lex=0.5, w_sem=0.5):
    bm25_results = bm25_index.search(query, top_n=top_n)
    faiss_results = faiss_index.search(query_vector, top_n=top_n)

    # Combine and rerank results
    combined_scores = {}
    for idx, score in bm25_results:
        if idx not in combined_scores:
            combined_scores[idx] = 0
        combined_scores[idx] += w_lex * score

    for idx, score in faiss_results:
        if idx not in combined_scores:
            combined_scores[idx] = 0
        combined_scores[idx] += w_sem * (1 / (1 + score))  # Invert distance to similarity

    # Sort by combined score
    sorted_results = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)

    return sorted_results[:top_n]

