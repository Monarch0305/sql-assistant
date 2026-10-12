"""Apply the current scoring rules to a saved run without calling the model."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.run_eval import score_answer, score_trap  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python eval/rescore_report.py results/eval_YYYYMMDD_HHMMSS.json")

    report_path = Path(sys.argv[1]).resolve()
    if not report_path.is_file():
        raise SystemExit(f"Report not found: {report_path}")
    try:
        report_path.relative_to(ROOT / "results")
    except ValueError:
        raise SystemExit("Choose a report inside this project's results folder.")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    tasks = {
        task["id"]: task
        for line in (ROOT / "tasks" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
        for task in [json.loads(line)]
    }
    for record in report["records"]:
        task = tasks.get(record["id"])
        if task is None:
            raise SystemExit(f"Task {record['id']} is missing from tasks/tasks.jsonl")
        if task["answerable"]:
            record["metric"] = "answer_value_accuracy"
            record["correct"] = score_answer(task, record.get("answer", ""))
        else:
            record["correct"], record["metric"] = score_trap(task, record.get("answer", ""))

    answerable = [r for r in report["records"] if r["category"] != "trap"]
    traps = [r for r in report["records"] if r["category"] == "trap"]
    answerable_with_sql = [
        r for r in answerable
        if any("result" in item for item in r.get("tool_results", []))
    ]
    all_records = report["records"]
    report["scoring_version"] = 2
    report["metrics"] = {
        "answer_value_accuracy": (
            sum(r["correct"] for r in answerable) / len(answerable) if answerable else None
        ),
        "answerable_tasks_with_sql_result": len(answerable_with_sql),
        "trap_policy_accuracy": (
            sum(r["correct"] for r in traps) / len(traps) if traps else None
        ),
        "overall_accuracy": (
            sum(r["correct"] for r in all_records) / len(all_records) if all_records else None
        ),
        "tasks": len(all_records),
        "answerable_tasks": len(answerable),
        "trap_tasks": len(traps),
    }

    output_path = report_path.with_name(f"{report_path.stem}_rescored.json")
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Rescored report: {output_path}")


if __name__ == "__main__":
    main()
