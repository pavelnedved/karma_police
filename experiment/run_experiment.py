"""Runs the seeded scenario end to end: worker -> mechanical grounding check
-> blind checker -> printed assumption checklist -> saved run folder.

This is the v1 test from philosophy.md: not "did the answer improve," but
"did the system surface the planted gap as an explicit assumption/hypothesis
instead of silently resolving it, and does the checklist actually save a
human from re-deriving the whole thing by hand?"

The checker model is held fixed across runs (a constant auditor) so that when
the worker model varies (--worker-model), differences in outcome are
attributable to the worker, not to the checker also changing underneath it.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import anthropic

from .checker import run_checker
from .mechanical_check import check_observation_grounding
from .scenario import KNOWLEDGE_BASE, PLANTED_GAP_DESCRIPTION, QUESTION
from .worker import run_worker

CHECKER_MODEL = "claude-opus-5"
RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def _write_run_folder(
    worker_model: str,
    checker_model: str,
    worker_output: dict,
    grounding: list,
    checker_output: dict,
) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / f"{timestamp}__worker-{_slug(worker_model)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "timestamp": timestamp,
        "worker_model": worker_model,
        "checker_model": checker_model,
        "scenario": {
            "question": QUESTION,
            "knowledge_base": KNOWLEDGE_BASE,
            "planted_gap_description": PLANTED_GAP_DESCRIPTION,
        },
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2))
    (run_dir / "worker_output.json").write_text(json.dumps(worker_output, indent=2))
    (run_dir / "grounding_check.json").write_text(json.dumps(grounding, indent=2))
    (run_dir / "checker_output.json").write_text(json.dumps(checker_output, indent=2))

    assumptions = worker_output.get("assumptions", [])
    hypotheses = worker_output.get("hypotheses", [])
    flags = checker_output.get("flags", [])
    ungrounded = [g for g in grounding if not g["grounded"]]
    conclusion = worker_output["conclusion"]

    summary_lines = [
        f"# Run: {timestamp} — worker={worker_model}, checker={checker_model}",
        "",
        f"**Question:** {QUESTION}",
        "",
        f"**Planted gap:** {PLANTED_GAP_DESCRIPTION}",
        "",
        "## Summary",
        f"- Assumptions surfaced: {len(assumptions)}",
        f"- Hypotheses surfaced: {len(hypotheses)}",
        f"- Checker flags: {len(flags)} "
        f"({sum(1 for f in flags if f['severity'] == 'high')} high, "
        f"{sum(1 for f in flags if f['severity'] == 'medium')} medium, "
        f"{sum(1 for f in flags if f['severity'] == 'low')} low)",
        f"- Ungrounded 'observations': {len(ungrounded)}",
        f"- Conclusion marked backed: {conclusion['backed']}",
        "",
        "## Assumption checklist",
    ]
    if not assumptions and not hypotheses:
        summary_lines.append("(none surfaced)")
    for a in assumptions:
        summary_lines.append(f"- **[ASSUMPTION {a['id']}]** {a['text']}")
        summary_lines.append(f"  - why needed: {a['why_needed']}")
    for h in hypotheses:
        summary_lines.append(f"- **[HYPOTHESIS {h['id']}]** {h['text']}")
        summary_lines.append(
            f"  - falsification: {h['falsification_path']} "
            f"(easily falsifiable: {h['easily_falsifiable']})"
        )
    summary_lines += ["", "## Checker flags"]
    if not flags:
        summary_lines.append("(none)")
    for f in flags:
        summary_lines.append(f"- **[{f['severity'].upper()}] {f['item_id']}** ({f['category']}): {f['reasoning']}")
    summary_lines += ["", "## Conclusion", conclusion["text"]]

    (run_dir / "summary.md").write_text("\n".join(summary_lines) + "\n")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-model", default="claude-opus-5")
    args = parser.parse_args()

    client = anthropic.Anthropic()

    _section("SCENARIO")
    print(f"Worker model: {args.worker_model}  |  Checker model: {CHECKER_MODEL}")
    print(f"Question: {QUESTION}\n")
    print(f"Planted gap: {PLANTED_GAP_DESCRIPTION}")

    _section("WORKER OUTPUT (raw)")
    worker_output = run_worker(client, KNOWLEDGE_BASE, QUESTION, model=args.worker_model)
    print(json.dumps(worker_output, indent=2))

    _section("MECHANICAL GROUNDING CHECK (observations only, no LLM judgment)")
    grounding = check_observation_grounding(KNOWLEDGE_BASE, worker_output["observations"])
    for g in grounding:
        status = "OK" if g["grounded"] else "*** NOT FOUND IN SOURCE ***"
        print(f"  [{g['id']}] {status}: {g['text']!r}")
    ungrounded = [g for g in grounding if not g["grounded"]]
    if ungrounded:
        print(f"\n  WARNING: {len(ungrounded)} observation(s) are not literal quotes from the "
              f"source. Under the philosophy's rules, these should be demoted — they are not "
              f"observations, they're unlabeled claims.")

    _section("BLIND CHECKER (sees only the bracket JSON, not the question)")
    checker_output = run_checker(client, worker_output, model=CHECKER_MODEL)
    print(json.dumps(checker_output, indent=2))

    _section("ASSUMPTION CHECKLIST (the actual deliverable — what a human reviews)")
    assumptions = worker_output.get("assumptions", [])
    hypotheses = worker_output.get("hypotheses", [])
    if not assumptions and not hypotheses:
        print("  (none surfaced)")
    for a in assumptions:
        print(f"  [ASSUMPTION {a['id']}] {a['text']}\n      why needed: {a['why_needed']}")
    for h in hypotheses:
        print(f"  [HYPOTHESIS {h['id']}] {h['text']}\n      falsification: {h['falsification_path']}"
              f"  (easily falsifiable: {h['easily_falsifiable']})")

    _section("CONCLUSION")
    c = worker_output["conclusion"]
    print(f"  {c['text']}\n  backed={c['backed']}  supporting_ids={c['supporting_ids']}")

    flags = checker_output.get("flags", [])
    _section("SUMMARY")
    print(f"  Assumptions surfaced: {len(assumptions)}")
    print(f"  Hypotheses surfaced: {len(hypotheses)}")
    print(f"  Checker flags: {len(flags)} ({sum(1 for f in flags if f['severity'] == 'high')} high severity)")
    print(f"  Ungrounded 'observations': {len(ungrounded)}")

    run_dir = _write_run_folder(
        args.worker_model, CHECKER_MODEL, worker_output, grounding, checker_output
    )
    print(f"\n  Run artifacts saved to: {run_dir.relative_to(RUNS_DIR.parent)}")
    print(
        "\n  Manually verify: does any assumption/hypothesis above name the "
        "damaged-sale-item collision from PLANTED_GAP_DESCRIPTION? If not, the "
        "gap was silently resolved rather than surfaced — a miss for this v1 test."
    )


if __name__ == "__main__":
    try:
        main()
    except anthropic.AuthenticationError:
        print(
            "No valid Anthropic credentials found. Set ANTHROPIC_API_KEY, or run "
            "`ant auth login` if you have the Anthropic CLI installed.",
            file=sys.stderr,
        )
        sys.exit(1)
