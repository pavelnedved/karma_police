"""CLI entrypoint: pick an agent, a task, a model (and a tool-mode where the
task has one), run it, save the result, and print a summary.

    python run.py --agent agent_base --task weather --model claude-sonnet-5 --tool-mode contradiction
    python run.py --agent agent_1    --task return_policy --model claude-opus-5

Any agent can be pointed at any task -- that's the point of this refactor.
The bracket-schema post-processing (mechanical grounding check + blind
checker) only runs when the agent actually produced structured bracket
output, so it's not hardcoded to one task or one agent.
"""

import argparse
import json
import sys

import anthropic

from agents.agent_1 import AGENT_1
from agents.agent_base import AGENT_BASE
from agents.checker import run_checker
from agents.mechanical_check import check_observation_grounding
from runner import run_agent, save_run
from tasks import return_policy, weather

AGENTS = {"agent_base": AGENT_BASE, "agent_1": AGENT_1}
CHECKER_MODEL = "claude-opus-5"


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=list(AGENTS), default="agent_base")
    parser.add_argument("--task", choices=["weather", "return_policy"], required=True)
    parser.add_argument("--model", default="claude-opus-5")
    parser.add_argument(
        "--tool-mode", choices=list(weather.TOOL_MODES), default="silent",
        help="only used by --task weather",
    )
    args = parser.parse_args()

    agent = AGENTS[args.agent]

    if args.task == "weather":
        user_message = weather.QUESTION
        tools = [weather.GET_WEATHER_TOOL]
        tool_impls = weather.build_tool_impls(args.tool_mode)
        config = {
            "agent": agent.name, "model": args.model, "task": "weather",
            "tool_mode": args.tool_mode, "question": weather.QUESTION,
            "tool": weather.GET_WEATHER_TOOL,
        }
        label_parts = ["weather", args.tool_mode, agent.name, args.model]
    else:
        user_message = return_policy.build_user_message()
        tools = None
        tool_impls = None
        config = {
            "agent": agent.name, "model": args.model, "task": "return_policy",
            "question": return_policy.QUESTION,
            "planted_gap_description": return_policy.PLANTED_GAP_DESCRIPTION,
            "knowledge_base": return_policy.KNOWLEDGE_BASE,
        }
        label_parts = ["return-policy", agent.name, args.model]

    _section(f"RUNNING agent={agent.name} task={args.task} model={args.model}"
              + (f" tool_mode={args.tool_mode}" if args.task == "weather" else ""))
    result = run_agent(agent, args.model, user_message, tools=tools, tool_impls=tool_impls)

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
