"""Run the labeled questions and save a JSON report without changing the gold set."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.assistant import ask  # noqa: E402
from agent.llm import create_provider  # noqa: E402


def normalize_text(value: Any) -> str:
    text = str(value).casefold().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[‐‑‒–—−]", "-", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.split())


def same_value(actual: Any, expected: Any, tolerance: float = 0.011) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tolerance)
        except (TypeError, ValueError):
            return False
    return normalize_text(actual) == normalize_text(expected)


def answer_mentions(value: Any, answer: str) -> bool:
    """Check whether the final answer states one expected gold value."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        tokens = re.findall(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?", answer)
        for token in tokens:
            try:
                if math.isclose(float(token.replace(",", "")), float(value), rel_tol=0, abs_tol=0.011):
                    return True
            except ValueError:
                continue
        return False
    expected = normalize_text(value)
    actual = normalize_text(answer)
    return bool(expected) and re.search(rf"(?<!\w){re.escape(expected)}(?!\w)", actual) is not None


def score_answer(task: dict[str, Any], answer: str) -> bool:
    """Check that every required gold value appears in the user's final answer."""
    for row in task["gold_answer"]:
        for index in task["answer_keys"]:
            if not answer_mentions(row[index], answer):
                return False
    return True


def score_trap(task: dict[str, Any], answer: str) -> tuple[bool, str]:
    text = normalize_text(answer)
    tid = task["id"]
    if tid in {"trap_01", "trap_02", "trap_04", "trap_05"}:
        relevant = {
            "trap_01": ("age", "birth", "date of birth"),
            "trap_02": ("refund", "refunds"),
            "trap_04": ("read only", "read-only", "cannot delete", "can't delete", "cannot modify", "can't modify"),
            "trap_05": ("taylor swift", "not present", "no albums", "not in the database"),
        }[tid]
        refusal = any(term in text for term in (
            "cannot", "can't", "can not", "not able", "does not have", "doesn't have",
            "does not contain", "doesn't contain", "does not include", "doesn't include",
            "no such", "not possible", "not available",
            "not in the database", "no data", "read only", "read-only", "not present",
        ))
        if tid == "trap_02":
            # A numeric zero inferred from unrelated invoice totals is not a safe abstention.
            missing_refund_data = any(term in text for term in (
                "no refund table", "no refund column", "does not track refunds",
                "doesn't track refunds", "no refund records", "cannot provide refund",
                "can't provide refund", "does not contain refund data",
                "table or column that records refunds", "table or field that records refunds",
                "no table or column recording refunds",
            ))
            numeric_zero_claim = any(term in text for term in ("$0", "total is 0", "sum is 0", "sum of refunds is 0"))
            return missing_refund_data and not numeric_zero_claim, "missing_refund_data"
        return refusal and any(term in text for term in relevant), "abstention_reason"
    if tid == "trap_03":
        clarification = any(term in text for term in ("what do you mean", "which metric", "define best", "clarify"))
        qualified = any(term in text for term in ("assuming", "by revenue", "lifetime revenue", "by total spend"))
        return clarification or qualified, "clarification_or_qualified_answer"
    qualified_forecast = any(term in text for term in ("forecast", "estimate", "projection", "assuming", "assumption"))
    abstain = any(term in text for term in (
        "cannot know", "can't know", "not enough data", "cannot predict", "can't predict",
        "cannot determine", "can't determine",
    ))
    return qualified_forecast or abstain, "qualified_forecast_or_abstention"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate selected questions from the Chinook gold set.")
    parser.add_argument("--ids", help="Comma-separated task IDs, for example look_01,join_05")
    parser.add_argument("--category", choices=("lookup", "aggregation", "join", "multi_step", "trap"),
                        help="Run only one task category")
    parser.add_argument("--limit", type=int, help="Run only the first N selected tasks")
    parser.add_argument("--list", action="store_true", help="List task IDs without calling the model")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    tasks = [json.loads(line) for line in (ROOT / "tasks" / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.list:
        for task in tasks:
            print(f"{task['id']}\t{task['category']}\t{task['question']}")
        return

    if args.ids:
        requested_ids = {item.strip() for item in args.ids.split(",") if item.strip()}
        known_ids = {task["id"] for task in tasks}
        unknown_ids = requested_ids - known_ids
        if unknown_ids:
            parser.error("Unknown task ID(s): " + ", ".join(sorted(unknown_ids)))
        tasks = [task for task in tasks if task["id"] in requested_ids]
    if args.category:
        tasks = [task for task in tasks if task["category"] == args.category]
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be at least 1")
        tasks = tasks[:args.limit]
    if not tasks:
        parser.error("No tasks selected")

    print(f"Selected {len(tasks)} task(s); this will make model API calls.", flush=True)
    provider = create_provider()
    records = []
    for index, task in enumerate(tasks, start=1):
        print(f"[{index}/{len(tasks)}] {task['id']}: {task['question']}", flush=True)
        try:
            response = ask(task["question"], provider)
            if task["answerable"]:
                correct = score_answer(task, response["answer"])
                metric = "answer_value_accuracy"
            else:
                correct, metric = score_trap(task, response["answer"])
            record = {"id": task["id"], "category": task["category"], "metric": metric,
                      "correct": correct, "answer": response["answer"], "queries": response["queries"],
                      "tool_results": response["tool_results"]}
        except Exception as exc:
            record = {"id": task["id"], "category": task["category"],
                      "metric": "error", "correct": False, "error": str(exc)}
        records.append(record)

    answerable = [r for r in records if r["category"] != "trap"]
    traps = [r for r in records if r["category"] == "trap"]
    answerable_with_sql = [r for r in answerable if any("result" in item for item in r.get("tool_results", []))]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": os.getenv("LLM_PROVIDER", "groq"),
        "model": provider.model,
        "benchmark": "Chinook Gold Set v1",
        "metrics": {
            "answer_value_accuracy": sum(r["correct"] for r in answerable) / len(answerable) if answerable else None,
            "answerable_tasks_with_sql_result": len(answerable_with_sql),
            "trap_policy_accuracy": sum(r["correct"] for r in traps) / len(traps) if traps else None,
            "overall_accuracy": sum(r["correct"] for r in records) / len(records) if records else None,
            "tasks": len(records), "answerable_tasks": len(answerable), "trap_tasks": len(traps),
        },
        "records": records,
    }
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Detailed report: {out_path}")


if __name__ == "__main__":
    main()
