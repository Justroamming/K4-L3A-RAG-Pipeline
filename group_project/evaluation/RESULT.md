# RAG evaluation results

## Run information

| Field | Value |
| --- | --- |
| Evaluation date | 2026-09-21 |
| Framework and version | Custom JSON evaluator runner over the shared golden set; contract suite `15 passed` |
| Evaluator model | OpenRouter `openai/gpt-4o-mini`, 30 per-case evaluations completed |
| Generator model | OpenRouter `openai/gpt-4o-mini`, 30 answers completed; the configured `gpt-4o` model hit an in-flight credit limit |
| Embedding model | `BAAI/bge-m3`, dimension 1024 |
| Corpus version/commit | Working tree on 2026-09-21; no evaluation commit/tag recorded |
| Golden dataset size | 15 cases in `golden_dataset.json` |
| `top_k` | 5 for both configurations |
| Fallback threshold and calibration | `0.30`; starter value, not yet calibrated with a scored in/out-of-domain sweep |

## Configurations

- **Config A — dense-only:** `semantic_search(query, top_k=10)` followed by the same generator, prompt, evaluator and `top_k=5`.
- **Config B — hybrid + RRF:** dense and BM25 with `top_k=10`, one RRF pass (`k=60`), then the same generator, prompt, evaluator and `top_k=5`.

The two configurations differ only in retrieval strategy. The same 15-case dataset, generation prompt, evaluator prompt and model are used for both configurations. Raw per-case answers, retrieved chunks, scores and latencies are stored in `raw_results.json`.

## Retrieval audit

Using the same 15 questions and `top_k=5`, both configurations retrieved at least one chunk from the `expected_context` source file in every case.

| Retrieval check | Config A | Config B | Delta B-A |
| --- | ---: | ---: | ---: |
| Expected source-file hit rate | 1.00 (15/15) | 1.00 (15/15) | 0.00 |

This is a source-file hit audit, not a substitute for context recall/precision or generation metrics. Cases 2, 13 and 14 still need chunk-level review because the top result came from a related article even though the expected source appeared within top 5.

## Overall scores

The model-based A/B measurement completed for all 15 cases and both configurations. Scores are LLM-judge scores on a 0.0 to 1.0 scale; inspect `raw_results.json` for per-case evidence and justifications.

| Metric | Config A | Config B | Delta B-A |
| --- | ---: | ---: | ---: |
| Faithfulness | 0.933333 | 0.866667 | -0.066666 |
| Answer relevance | 0.986667 | 0.900000 | -0.086667 |
| Context recall | 0.986667 | 0.900000 | -0.086667 |
| Context precision | 0.986667 | 0.886667 | -0.100000 |
| **Average** | **0.973333** | **0.888333** | **-0.085000** |

## A/B comparison

- **Cấu hình tốt hơn:** Config A (dense-only) theo điểm trung bình: `0.973333` so với `0.888333` của Config B.
- **Evidence:** 30/30 generation and evaluator calls completed; Config A scored higher on all four metrics. Both configurations had source-file hit rate `15/15`.
- **Trade-off về latency/cost:** Median generation latency was `3.5012s` for A and `2.5144s` for B; median evaluator latency was `2.5773s` and `3.0689s`. Token cost was not returned by the current runner, so no cost claim is made.

## Worst performers

These are the lowest-scoring evaluated cases from the raw per-case results.

| # | Question/case | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
| --: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | Case 6: nguyên tắc tổ chức lễ hội | B | 0.000 | 0.000 | 0.000 | 0.000 | retrieval/generation | Retrieved context did not support the reference principles, and the answer did not address the expected historical-cultural requirements. |
| 2 | Case 9: ý nghĩa tục ăn trầu | A | 0.000 | 0.800 | 0.800 | 0.800 | generation/citation | Answer partially addressed the topic but cited the wrong document and introduced an unsupported claim. |
| 3 | Case 9: ý nghĩa tục ăn trầu | B | 0.000 | 0.500 | 0.500 | 0.500 | generation/citation | Relevant evidence existed, but the answer cited an unrelated document and only partially matched the reference. |

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| ---: | --- | --- | --- | --- |
| 1 | Review Config B retrieval for cases 6 and 9 and improve citation grounding. | Config B trails A by `0.085000` average despite equal source-file hit rate. | Improve chunk-level precision and faithful citations. | Add expected evidence spans and re-run `run_evaluation.py`. |
| 2 | Add chunk-level expected evidence spans to the golden set. | File-level hit rate is `15/15`, but case 6 still received zero context scores in B. | Makes precision and recall diagnosis more discriminating than file-level hits. | Re-run both configs and compare evidence-span hits at top 1/3/5. |
| 3 | Repeat with configured `openai/gpt-4o` after adding OpenRouter credit. | The requested model was blocked by `in_flight_budget_exhausted`; this run used `gpt-4o-mini`. | Makes the result directly comparable to the intended model configuration. | Set `LLM_MODEL=openai/gpt-4o` and rerun the saved runner. |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| --- | --- | ---: | ---: | --- |
| Reproducible A/B runner with raw per-case artifacts | Baseline retrieval audit | Four metric means and deltas recorded | 30 generation + 30 evaluator calls; p50 latency recorded | Completed; no bonus improvement claim made. |
