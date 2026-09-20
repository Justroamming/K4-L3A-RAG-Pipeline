# Individual contribution report

Mỗi thành viên copy template này thành:

```text
reports/<student-id>-<short-name>.md
```

Giới hạn khuyến nghị: 1 trang, không chép lại README hoặc mô tả lý thuyết chung. Báo cáo không phải một bài pipeline cá nhân; mục đích là ghi nhận ownership và bằng chứng đóng góp trong sản phẩm nhóm.

---

## Thông tin

- Họ và tên: Lê Tuấn Hưng
- Mã học viên: 2A202602665
- Nhóm: G50
- Repository/branch: K4-L3A-RAG-Pipeline / main

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Retrieval pipeline | Hoàn thiện dense search, BM25, RRF và pipeline fallback theo cosine score gốc. | `src/task5_semantic_search.py`, `src/task6_lexical_search.py`, `src/task7_reranking.py`, `src/task9_retrieval_pipeline.py` | Done |
| Generation có citation | Duy trì context có title/source, reorder chunks và safe refusal khi provider/context lỗi. | `src/task10_generation.py`, `tests/test_contracts.py` | Done |
| Evaluation runner | Xây dựng runner chạy dense-only và hybrid + RRF trên 15 cases, lưu answer, chunks, scores và latency; có checkpoint/resume. | `group_project/evaluation/run_evaluation.py`, `group_project/evaluation/raw_results.json` | Done |
| Evaluation report | Cập nhật bảng điểm bốn metric, A/B comparison, retrieval audit, worst performers và recommendations. | `group_project/evaluation/RESULT.md`, `reports/RESULT.md` | Done |
| Contract và acceptance checks | Chạy và kiểm tra contract, acceptance và full test suite trước khi hoàn thiện artifact. | `tests/test_contracts.py`, `tests/test_acceptance.py` | Done |

Chỉ kê khai công việc có thể đối chiếu bằng file, commit, pull request, test hoặc kết quả evaluation.

## Quyết định kỹ thuật quan trọng

Mô tả tối đa hai quyết định mà bạn trực tiếp tham gia:

1. **Quyết định:** Dùng RRF để hợp nhất dense retrieval và BM25, nhưng quyết định fallback bằng cosine score gốc của dense search.  
   **Lý do/evidence:** Cosine và BM25 có thang điểm khác nhau; RRF chỉ phản ánh thứ hạng. Quy tắc này được kiểm tra trong `tests/test_contracts.py` và triển khai ở `src/task9_retrieval_pipeline.py`.  
   **Trade-off:** Hybrid giúp kết hợp ngữ nghĩa và từ khóa, nhưng thêm chi phí BM25/RRF và có thể đưa context liên quan nhưng kém chính xác lên trước.

2. **Quyết định:** Tách retrieval khỏi generation trong evaluation runner để Config A thực sự là dense-only.  
   **Lý do/evidence:** `generate_with_citation()` của ứng dụng gọi pipeline hybrid mặc định, nên runner dùng `semantic_search()` trực tiếp cho A và `semantic_search()` + `lexical_search()` + `rerank_rrf()` cho B. Raw output lưu đủ context và metric tại `group_project/evaluation/raw_results.json`.  
   **Trade-off:** Runner dài hơn và cần duy trì prompt/evaluator riêng, nhưng kết quả A/B không bị sai do dùng nhầm retrieval strategy.

## Kiểm thử và kết quả

- Test hoặc query tôi đã dùng: `pytest tests/test_contracts.py -q`, `pytest tests/test_acceptance.py -q`, `pytest -q`; evaluation runner chạy 15 golden cases cho mỗi config.
- Kết quả trước/sau nếu có: Full suite đạt `20 passed`. Config A đạt average `0.973333`; Config B đạt `0.888333`; cả hai đạt source-file hit rate `15/15`.
- Lỗi đã phát hiện và cách xử lý: Runner ban đầu không import được `src` khi chạy trực tiếp, đã bổ sung repository root vào `sys.path`. OpenRouter `gpt-4o` gặp `in_flight_budget_exhausted`, nên chạy hoàn chỉnh bằng `openai/gpt-4o-mini` và ghi rõ trong `RESULT.md`.

## Điều còn hạn chế

- Một hạn chế cụ thể của phần tôi làm: PageIndex fallback trong `src/task8_pageindex_vectorless.py` vẫn chưa triển khai; evaluation run dùng `gpt-4o-mini` thay vì model `gpt-4o` dự kiến do giới hạn credit OpenRouter.
- Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện: Bổ sung expected evidence span theo chunk, cải thiện citation grounding cho các case 6 và 9, sau đó chạy lại A/B với `gpt-4o` khi có đủ credit.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 2026-09-20
- Tên thành viên: Lê Tuấn Hưng
