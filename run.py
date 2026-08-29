"""CLI over api.run() -- pick a version, a task, a model (and a tool-mode
where the task has one), run it, save the result, print a summary.

    python run.py --version version_base --task weather --model claude-sonnet-5 --tool-mode contradiction
    python run.py --version version_1    --task return_policy --model claude-opus-5

This file owns nothing about routing (that's api.py) or execution (that's
runner.py) -- it's argument parsing, printing, version_1-specific
post-processing (grounding check + blind checker), and saving the audit
trail.
"""

import argparse
import json
import sys

import anthropic

import api
from agents.checker import run_checker
from agents.mechanical_check import check_observation_grounding
from runner import save_run
from tasks import return_policy, weather

CHECKER_MODEL = "claude-opus-5"


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=api.list_versions(), default="version_base")
    parser.add_argument("--task", choices=api.list_tasks(), required=True)
    parser.add_argument("--model", default="claude-opus-5")
    parser.add_argument(
        "--tool-mode", choices=list(weather.TOOL_MODES), default="silent",
        help="only used by --task weather",
    )
    args = parser.parse_args()

    _section(
        f"RUNNING version={args.version} task={args.task} model={args.model}"
        + (f" tool_mode={args.tool_mode}" if args.task == "weather" else "")
    )
    result = api.run(version=args.version, task=args.task, model=args.model, tool_mode=args.tool_mode)

    _section("RESULT")
    print(json.dumps(result, indent=2))

    extra = {}
    if "structured" in result and args.task == "return_policy":
        client = anthropic.Anthropic()
        grounding = check_observation_grounding(
            return_policy.KNOWLEDGE_BASE, result["structured"].get("observations", [])
        )
        _section("MECHANICAL GROUNDING CHECK")
        for g in grounding:
            status = "OK" if g["grounded"] else "*** NOT FOUND IN SOURCE ***"
            print(f"  [{g['id']}] {status}: {g['text']!r}")

        checker_output = run_checker(client, result["structured"], model=CHECKER_MODEL)
        _section("BLIND CHECKER (sees only the bracket JSON, not the question)")
        print(json.dumps(checker_output, indent=2))

        extra = {"grounding": grounding, "checker": checker_output, "checker_model": CHECKER_MODEL}

    label_parts = [args.task]
    if args.task == "weather":
        label_parts.append(args.tool_mode)
    label_parts += [args.version, args.model]

    config = {"version": args.version, "model": args.model, "task": args.task}
    if args.task == "weather":
        config["tool_mode"] = args.tool_mode

    run_dir = save_run(label_parts, config, {**result, **extra})
    print(f"\nSaved to: {run_dir.relative_to(run_dir.parent.parent)}")

    if result.get("hit_round_cap"):
        print("\n  NOTE: hit the tool-round cap without the model stopping tool use on its own.")


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
