"""Run a karma_police agent version against LiveBench reasoning questions
(the 3 tasks with public ground truth: web_of_lies_v2, spatial, zebra_puzzle)
and score with LiveBench's own scoring logic (scorers.py, copied verbatim).

Usage:
    ./.venv/bin/python livebench_eval/run_eval.py --version version_base --model claude-sonnet-5
    ./.venv/bin/python livebench_eval/run_eval.py --version version_base --model claude-sonnet-5 --task zebra_puzzle --limit 10

Writes:
    livebench_eval/results/<timestamp>__<version>__<model>.json   (per-question detail)
    livebench_eval/RESULTS.md                                      (appended summary row)
"""

import argparse
import collections
import datetime
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent  # karma_police/ (tests/livebench/ -> tests/ -> repo root)
sys.path.insert(0, str(REPO_ROOT))

from agents.agent_base import AGENT_BASE  # noqa: E402
from agents.agent_1 import AGENT_1  # noqa: E402
from runner import run_agent  # noqa: E402
from scorers import SCORERS  # noqa: E402
from agents_ext import AGENT_1_FORMATTED  # noqa: E402

AGENTS = {"version_base": AGENT_BASE, "version_1": AGENT_1, "version_1_formatted": AGENT_1_FORMATTED}


def load_questions(task_filter=None, limit=None, ids_file=None):
    questions = json.loads((HERE / "data" / "questions.json").read_text())
    if ids_file:
        wanted = set(json.loads(Path(ids_file).read_text()))
        questions = [q for q in questions if q["question_id"] in wanted]
        return questions
    if task_filter:
        questions = [q for q in questions if q["task"] == task_filter]
    if limit:
        by_task = collections.defaultdict(list)
        for q in questions:
            by_task[q["task"]].append(q)
        questions = [q for bucket in by_task.values() for q in bucket[:limit]]
    return questions


def score_one(agent, model, question, max_tokens):
    q = question
    try:
        out = run_agent(agent, model=model, user_message=q["prompt"], max_tokens=max_tokens)
        # agent_1 forces JSON output (no bold/<solution> markdown possible) --
        # the schema's conclusion.text field is documented as "the final answer
        # to the question", so score against that instead of the raw JSON blob.
        if agent.output_schema and "structured" in out:
            scored_text = out["structured"].get("conclusion", {}).get("text", "")
        else:
            scored_text = out["final_text"]
        scorer = SCORERS[q["task"]]
        score = scorer(q["ground_truth"], scored_text, q["livebench_release_date"])
        return {
            "question_id": q["question_id"],
            "task": q["task"],
            "ground_truth": q["ground_truth"],
            "final_text": out["final_text"],
            "scored_text": scored_text,
            "score": score,
            "error": None,
        }
    except Exception as e:
        return {
            "question_id": q["question_id"],
            "task": q["task"],
            "ground_truth": q["ground_truth"],
            "final_text": None,
            "scored_text": None,
            "score": 0.0,
            "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="version_base", choices=sorted(AGENTS))
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--task", default=None, choices=sorted(SCORERS))
    ap.add_argument("--limit", type=int, default=None, help="cap questions per task")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--ids-file", default=None, help="JSON file with a list of question_ids to rerun (overrides --task/--limit)")
    args = ap.parse_args()

    agent = AGENTS[args.version]
    questions = load_questions(task_filter=args.task, limit=args.limit, ids_file=args.ids_file)
    print(f"Running version={args.version} model={args.model} on {len(questions)} questions "
          f"({args.workers} workers)...")

    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(score_one, agent, args.model, q, args.max_tokens): q for q in questions}
        done = 0
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            if done % 20 == 0 or done == len(questions):
                print(f"  {done}/{len(questions)} done")
    elapsed = time.time() - t0

    by_task = collections.defaultdict(list)
    for r in results:
        by_task[r["task"]].append(r["score"])

    summary = {}
    for task, scores in sorted(by_task.items()):
        summary[task] = {
            "n": len(scores),
            "mean_score": sum(scores) / len(scores),
            "exact_1.0_count": sum(1 for s in scores if s == 1.0),
        }

    overall_n = len(results)
    overall_mean = sum(r["score"] for r in results) / overall_n if overall_n else 0.0
    error_count = sum(1 for r in results if r["error"])

    print(f"\n=== Done in {elapsed:.1f}s ===")
    for task, s in summary.items():
        print(f"  {task:20s} n={s['n']:4d}  mean_score={s['mean_score']:.3f}  exact_correct={s['exact_1.0_count']}")
    print(f"  {'OVERALL':20s} n={overall_n:4d}  mean_score={overall_mean:.3f}  errors={error_count}")

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"{timestamp}__{args.version}__{args.model}.json"
    out_path.write_text(json.dumps({
        "timestamp": timestamp,
        "version": args.version,
        "model": args.model,
        "task_filter": args.task,
        "limit": args.limit,
        "elapsed_seconds": elapsed,
        "summary": summary,
        "overall": {"n": overall_n, "mean_score": overall_mean, "errors": error_count},
        "results": results,
    }, indent=2))
    print(f"\nDetail written to {out_path.relative_to(REPO_ROOT)}")

    append_results_md(timestamp, args, summary, overall_n, overall_mean, error_count, elapsed, out_path)


def append_results_md(timestamp, args, summary, overall_n, overall_mean, error_count, elapsed, out_path):
    md_path = HERE / "RESULTS.md"
    header = (
        "# LiveBench reasoning eval results\n\n"
        "Data source: `livebench/reasoning` on HuggingFace (public rows only: "
        "web_of_lies_v2, spatial, zebra_puzzle — the other 5 reasoning tasks have no "
        "public ground truth as of this writing). Scoring uses LiveBench's own scorer "
        "functions, copied verbatim in `scorers.py`.\n\n"
        "| timestamp | version | model | task filter | n | overall mean score | errors | elapsed (s) | detail file |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    row = (
        f"| {timestamp} | {args.version} | {args.model} | {args.task or 'all'} | "
        f"{overall_n} | {overall_mean:.3f} | {error_count} | {elapsed:.1f} | "
        f"`{out_path.relative_to(HERE)}` |\n"
    )
    per_task_lines = "".join(
        f"  - `{task}`: n={s['n']}, mean_score={s['mean_score']:.3f}, exact_correct={s['exact_1.0_count']}\n"
        for task, s in summary.items()
    )

    if not md_path.exists():
        md_path.write_text(header)

    with md_path.open("a") as f:
        f.write(row)
        f.write(per_task_lines)

    print(f"Summary appended to {md_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
