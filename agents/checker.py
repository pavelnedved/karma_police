"""The checker: audits agent_1's bracket output WITHOUT seeing the original
question. It only sees what was classified as what, so it has no stake in
finishing the task and no way to rationalize toward a particular answer."""

import json

import anthropic

from .schemas import CHECKER_SCHEMA

CHECKER_SYSTEM_PROMPT = """\
You are an independent auditor. You are given a structured reasoning artifact \
produced by another AI system: a set of items sorted into observation, \
definition, assumption, backed_claim, unverified_claim, hypothesis, and a \
conclusion. You are NOT given the original task or question, and you should not \
try to guess it or evaluate whether the conclusion is "right." Your only job is \
to check whether each item is honestly classified:

- Does a "definition" secretly derive a claim on its own (i.e. does removing it, \
holding everything else fixed, still block whatever claim depends on it)?
- Does a "backed_claim" actually have a real, checkable falsification path, or is \
the falsification path vague/circular/unfalsifiable in practice?
- Does a "hypothesis" have a real falsification path?
- Is there a claim in the conclusion or elsewhere that isn't backed by anything in \
observations/definitions/assumptions/backed_claims — i.e. an unlabeled leap that \
should have been an assumption or hypothesis but wasn't labeled as one at all?

Flag only real issues. If something is fine, don't flag it.
"""


def run_checker(client: anthropic.Anthropic, worker_output: dict, model: str = "claude-opus-5") -> dict:
    # Deliberately given nothing task-related, because the worker output
    # itself never contained the original question in the first place — the
    # checker only ever sees this JSON.
    payload = json.dumps(worker_output, indent=2)
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=CHECKER_SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": CHECKER_SCHEMA}},
        messages=[{"role": "user", "content": f"Reasoning artifact to audit:\n{payload}"}],
    )
    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            "Checker response truncated at max_tokens before completing valid JSON "
            "— raise max_tokens further."
        )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
