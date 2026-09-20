"""
Task 7 — Reciprocal Rank Fusion.

RRF gộp nhiều bảng xếp hạng mà không cộng trực tiếp cosine score với BM25
score. Công thức: RRF(d) = sum(1 / (k + rank)), rank bắt đầu từ 1.

Lưu ý: RRF score chỉ phản ánh thứ hạng, không dùng để quyết định fallback.

-> Dùng Jina hoặc self host hoặc bất cứ công cụ nào bạn quen
"""


def rerank_rrf(
    ranked_lists: list[list[dict]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """Fuse nhiều ranked lists và trả hybrid SearchResult."""
    if k < 0:
        raise ValueError("RRF k must be non-negative")
    limit = max(int(top_k), 0)
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    first_seen: dict[str, int] = {}
    seen_order = 0

    for ranked_list in ranked_lists:
        list_ids: set[str] = set()
        for rank, item in enumerate(ranked_list, 1):
            item_id = item["id"]
            if item_id in list_ids:
                raise ValueError(f"duplicate result ID in ranked list: {item_id}")
            list_ids.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1 / (k + rank)
            if item_id not in items:
                items[item_id] = item
                first_seen[item_id] = seen_order
                seen_order += 1

    ranked_ids = sorted(
        scores,
        key=lambda item_id: (-scores[item_id], first_seen[item_id]),
    )[:limit]
    results = []
    for item_id in ranked_ids:
        result = items[item_id].copy()
        result["score"] = scores[item_id]
        result["retrieval_method"] = "hybrid"
        results.append(result)
    return results


if __name__ == "__main__":
    print("RRF implementation is ready; run pytest tests/test_contracts.py -q to validate it.")
