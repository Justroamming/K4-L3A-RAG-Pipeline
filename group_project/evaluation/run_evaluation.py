"""Run the reproducible two-configuration RAG evaluation.

The runner deliberately keeps retrieval and generation separate so the dense-only
configuration does not accidentally call the hybrid pipeline through
``generate_with_citation``.
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "group_project" / "evaluation" / "golden_dataset.json"
DEFAULT_OUTPUT = ROOT / "group_project" / "evaluation" / "raw_results.json"
TOP_K = 5
RETRIEVAL_K = 10

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.task10_generation import SYSTEM_PROMPT, call_llm, format_context, reorder_for_llm
from src.task5_semantic_search import semantic_search
from src.task6_lexical_search import lexical_search
from src.task7_reranking import rerank_rrf

EVALUATOR_PROMPT = """You are a strict RAG evaluator. Score the answer against the question,
reference answer, and retrieved context. Return JSON only, with no markdown:
{"faithfulness": 0.0, "answer_relevance": 0.0, "context_recall": 0.0,
"context_precision": 0.0, "justification": "short explanation"}

Use a 0.0 to 1.0 scale. Faithfulness measures whether answer claims are supported
by context. Answer relevance measures whether it answers the question. Context
recall measures whether the context contains the evidence needed for the reference
answer. Context precision measures how much retrieved context is relevant rather
than unrelated. Do not reward plausible claims that are absent from context.
"""


def retrieve_for_config(question: str, config: str) -> list[dict]:
    """Retrieve exactly the chunks used by one evaluation configuration."""
    dense = semantic_search(question, top_k=RETRIEVAL_K)
    if config == "A":
        return dense[:TOP_K]
    sparse = lexical_search(question, top_k=RETRIEVAL_K)
    return rerank_rrf([dense, sparse], top_k=TOP_K, k=60)


def generate_answer(question: str, chunks: list[dict]) -> str:
    """Generate an answer from explicitly supplied chunks."""
    context = format_context(reorder_for_llm(chunks))
    message = f"Context:\n{context}\n\nQuestion: {question}"
    return call_llm(SYSTEM_PROMPT, message)


def parse_json_object(text: str) -> dict:
    """Parse JSON even when a provider wraps it in a markdown code fence."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError(f"Evaluator did not return a JSON object: {text!r}") from None
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Evaluator response must be a JSON object")
    return value


def evaluate_case(case: dict, config: str, chunks: list[dict]) -> dict:
    """Generate and score one case, retaining enough evidence for audit."""
    question = case["question"]
    started = time.perf_counter()
    answer = generate_answer(question, chunks)
    generation_seconds = time.perf_counter() - started
    evaluation_message = (
        f"Question:\n{question}\n\nReference answer:\n{case['expected_answer']}\n\n"
        f"Expected context note:\n{case['expected_context']}\n\n"
        f"Retrieved context:\n{format_context(chunks)}\n\nGenerated answer:\n{answer}"
    )
    started = time.perf_counter()
    score = parse_json_object(call_llm(EVALUATOR_PROMPT, evaluation_message))
    evaluation_seconds = time.perf_counter() - started
    metrics = {}
    for metric in (
        "faithfulness",
        "answer_relevance",
        "context_recall",
        "context_precision",
    ):
        value = float(score[metric])
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{metric} must be between 0 and 1, got {value}")
        metrics[metric] = value
    return {
        "config": config,
        "question": question,
        "expected_answer": case["expected_answer"],
        "expected_context": case["expected_context"],
        "answer": answer,
        "metrics": metrics,
        "justification": str(score.get("justification", "")),
        "retrieved_chunks": [
            {
                "id": chunk["id"],
                "source": chunk["metadata"]["source"],
                "chunk_index": chunk["metadata"].get("chunk_index"),
                "score": chunk["score"],
                "retrieval_method": chunk["retrieval_method"],
                "content": chunk["content"],
            }
            for chunk in chunks
        ],
        "generation_seconds": round(generation_seconds, 4),
        "evaluation_seconds": round(evaluation_seconds, 4),
    }


def summarize(results: list[dict]) -> dict:
    metrics = ("faithfulness", "answer_relevance", "context_recall", "context_precision")
    summary = {}
    for config in ("A", "B"):
        rows = [row for row in results if row["config"] == config]
        if not rows:
            continue
        summary[config] = {
            metric: round(statistics.mean(row["metrics"][metric] for row in rows), 6)
            for metric in metrics
        }
        summary[config]["average"] = round(
            statistics.mean(summary[config][metric] for metric in metrics), 6
        )
        summary[config]["generation_p50_seconds"] = round(
            statistics.median(row["generation_seconds"] for row in rows), 4
        )
        summary[config]["evaluation_p50_seconds"] = round(
            statistics.median(row["evaluation_seconds"] for row in rows), 4
        )
    return summary


def run(limit: int | None, output_path: Path) -> dict:
    load_dotenv(ROOT / ".env")
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    cases = dataset[:limit] if limit else dataset
    if len(cases) != 15 and limit is None:
        raise ValueError(f"Expected 15 golden cases, found {len(cases)}")
    results = []
    if output_path.exists():
        previous = json.loads(output_path.read_text(encoding="utf-8"))
        results = previous.get("results", [])
    completed = {(row["question"], row["config"]) for row in results}

    def save(status: str) -> dict:
        payload = {
            "status": status,
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "generator_model": os.getenv("LLM_MODEL", "openai/gpt-4o"),
            "evaluator_model": os.getenv("LLM_MODEL", "openai/gpt-4o"),
            "dataset_size": len(cases),
            "top_k": TOP_K,
            "retrieval_k": RETRIEVAL_K,
            "results": results,
            "summary": summarize(results) if results else {},
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    for index, case in enumerate(cases, 1):
        for config in ("A", "B"):
            if (case["question"], config) in completed:
                continue
            print(f"[{len(results) + 1}/ {len(cases) * 2}] case {index}, config {config}", flush=True)
            try:
                chunks = retrieve_for_config(case["question"], config)
                results.append(evaluate_case(case, config, chunks))
                completed.add((case["question"], config))
                save("running")
            except Exception:
                save("partial")
                raise
    return save("complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Run only the first N cases for a smoke test")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.limit, args.output)