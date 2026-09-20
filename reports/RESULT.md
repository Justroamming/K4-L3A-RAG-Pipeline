# RAG evaluation results

## Run information

| Field | Value |
| --- | --- |
| Evaluation date | 2026-09-21 |
| Framework and version | Custom JSON evaluator runner; contract suite `15 passed` |
| Evaluator model | OpenRouter `openai/gpt-4o-mini`, 30 evaluations completed |
| Generator model | OpenRouter `openai/gpt-4o-mini`, 30 answers completed |
| Embedding model | `BAAI/bge-m3`, dimension 1024 |
| Corpus version/commit | Working tree on 2026-09-21; no evaluation commit/tag recorded |
| Golden dataset size | 15 cases |
| `top_k` | 5; retrieval candidate depth 10 |
| Fallback threshold and calibration | `0.30`; not calibrated with a scored sweep |

## Configurations

- **Config A — dense-only:** dense retrieval with 10 candidates, first 5 supplied to the generator.
- **Config B — hybrid + RRF:** dense and BM25 with 10 candidates each, one RRF pass with `k=60`, top 5 supplied to the generator.

Both configurations used the same dataset, generation prompt, evaluator prompt and model. The raw per-case artifact is `group_project/evaluation/raw_results.json`.

## Overall scores

| Metric | Config A | Config B | Delta B-A |
| --- | ---: | ---: | ---: |
| Faithfulness | 0.933333 | 0.866667 | -0.066666 |
| Answer relevance | 0.986667 | 0.900000 | -0.086667 |
| Context recall | 0.986667 | 0.900000 | -0.086667 |
| Context precision | 0.986667 | 0.886667 | -0.100000 |
| **Average** | **0.973333** | **0.888333** | **-0.085000** |

## Retrieval audit

Both configurations retrieved at least one chunk from the expected source file in all 15 cases: `15/15` for A and `15/15` for B. This file-level result does not replace chunk-level context scoring.

## A/B comparison

- **Cấu hình tốt hơn:** Config A, with average score `0.973333` versus `0.888333` for Config B.
- **Evidence:** A scored higher on all four metrics; 30/30 generation and evaluator calls completed.
- **Trade-off về latency/cost:** Median generation latency was `3.5012s` for A and `2.5144s` for B. Median evaluator latency was `2.5773s` and `3.0689s`. Token cost was not captured.

## Worst performers

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | Case 6: nguyên tắc tổ chức lễ hội | B | 0.000 | 0.000 | 0.000 | 0.000 | retrieval/generation | Retrieved context did not support the expected historical-cultural principles. |
| 2 | Case 9: ý nghĩa tục ăn trầu | A | 0.000 | 0.800 | 0.800 | 0.800 | generation/citation | Partial answer with an incorrect document citation and an unsupported claim. |
| 3 | Case 9: ý nghĩa tục ăn trầu | B | 0.000 | 0.500 | 0.500 | 0.500 | generation/citation | Relevant evidence existed, but the answer cited an unrelated document. |

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| ---: | --- | --- | --- | --- |
| 1 | Review Config B retrieval for cases 6 and 9 and improve citation grounding. | Config B trails A by `0.085000` average despite equal source-file hit rate. | Improve chunk-level precision and faithful citations. | Add expected evidence spans and rerun the evaluation runner. |
| 2 | Add chunk-level expected evidence spans to the golden set. | File-level hit rate is `15/15`, but case 6 received zero context scores in B. | More discriminating recall and precision diagnosis. | Compare evidence-span hits at top 1/3/5. |
| 3 | Repeat with configured `openai/gpt-4o` when OpenRouter credit is available. | The intended model hit `in_flight_budget_exhausted`; this run used `gpt-4o-mini`. | Direct comparison with the intended model configuration. | Set `LLM_MODEL=openai/gpt-4o` and rerun the runner. |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| --- | --- | ---: | ---: | --- |
| Reproducible A/B runner with raw per-case artifacts | Retrieval audit | Four metric means and deltas recorded | 30 generation + 30 evaluator calls | Completed; no bonus improvement claim made. |
