"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.
"""

from pathlib import Path

from rank_bm25 import BM25Okapi

from .task4_chunking_indexing import chunk_documents, load_documents


CORPUS: list[dict] = []
_BM25_INDEX: BM25Okapi | None = None
_CORPUS_ID: int = 0


def _load_corpus() -> list[dict]:
    """Load và chunk documents để tạo corpus dùng chung."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    return chunks


def build_bm25_index(corpus: list[dict]) -> BM25Okapi:
    """Tạo BM25 index từ cùng corpus chunks của Task 4."""
    tokenized = [item["content"].lower().split() for item in corpus]
    return BM25Okapi(tokenized)


def _get_bm25_index() -> BM25Okapi:
    global _BM25_INDEX, _CORPUS_ID
    global CORPUS
    if not CORPUS:
        CORPUS = _load_corpus()

    corpus_id = id(CORPUS)
    if _BM25_INDEX is None or _CORPUS_ID != corpus_id:
        _BM25_INDEX = build_bm25_index(CORPUS)
        _CORPUS_ID = corpus_id
    return _BM25_INDEX


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    global CORPUS, _BM25_INDEX, _CORPUS_ID
    limit = max(int(top_k), 0)
    if limit == 0:
        return []
    if not CORPUS:
        CORPUS = _load_corpus()

    # Force rebuild if CORPUS was replaced (e.g. by test monkeypatch)
    corpus_id = id(CORPUS)
    if _CORPUS_ID != corpus_id:
        _BM25_INDEX = None
        _CORPUS_ID = corpus_id

    bm25 = _get_bm25_index()
    scores = bm25.get_scores(query.lower().split())
    indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:limit]

    results = []
    for index in indices:
        item = CORPUS[index]
        results.append({
            "id": item["id"],
            "content": item["content"],
            "score": float(scores[index]),
            "metadata": item["metadata"],
            "retrieval_method": "bm25",
        })
    return results


if __name__ == "__main__":
    for result in lexical_search("test query", top_k=3):
        print(result)
