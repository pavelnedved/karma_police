"""Generic harness: run any Agent (system prompt + optional output schema)
against any task (a user message, optionally with tools + their Python
implementations), the same way regardless of which agent or which task is
plugged in. Handles a full multi-round tool-use loop -- not just one round --
so a model that retries a tool call actually gets to finish doing so instead
of being cut off mid-thought. Saves every run to runs/<timestamp>__<label>/
for audit.
"""

import datetime
import json
import re
from pathlib import Path
from typing import Callable, Optional

import anthropic

from agents.types import Agent

RUNS_DIR = Path(__file__).resolve().parent / "runs"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _block_to_dict(block) -> dict:
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "name": block.name, "input": block.input, "id": block.id}
    if block.type == "thinking":
        return {"type": "thinking", "thinking": block.thinking}
    return {"type": block.type}


def run_agent(
    agent: Agent,
    model: str,
    user_message: str,
    tools: Optional[list] = None,
    tool_impls: Optional[dict] = None,
    max_tool_rounds: int = 4,
    max_tokens: int = 4096,
) -> dict:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": user_message}]
    tool_impls: dict = tool_impls or {}

    rounds = []
    response = None
    hit_round_cap = False
    for i in range(max_tool_rounds):
        kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if agent.system_prompt:
            kwargs["system"] = agent.system_prompt
        if tools:
            kwargs["tools"] = tools
        # Structured output is only requested on tool-free tasks -- forcing a
        # JSON schema mid tool-use loop isn't a case this harness resolves
        # yet, so agent_1's schema only applies when no tools are in play.
        if agent.output_schema and not tools:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": agent.output_schema}
            }

        response = client.messages.create(**kwargs)
        rounds.append({
            "stop_reason": response.stop_reason,
            "content": [_block_to_dict(b) for b in response.content],
        })

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for call in tool_calls:
            impl = tool_impls.get(call.name)
            result_text = (
                impl(call.input) if impl else f"No implementation registered for tool '{call.name}'"
            )
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": result_text,
            })
        messages.append({"role": "user", "content": tool_results})

        if i == max_tool_rounds - 1:
            hit_round_cap = True

    final_text = next((b.text for b in response.content if b.type == "text"), "")
    result = {
        "agent": agent.name,
        "model": model,
        "rounds": rounds,
        "final_text": final_text,
        "hit_round_cap": hit_round_cap,
    }

    if agent.output_schema and not tools:
        result["structured"] = json.loads(final_text)

    return result


def save_run(label_parts: list, config: dict, result: dict) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    label = "-".join(_slug(p) for p in label_parts)
    run_dir = RUNS_DIR / f"{timestamp}__{label}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(json.dumps(config, indent=2))
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    return run_dir
