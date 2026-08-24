"""The worker: answers a question against a knowledge base, forced to sort
everything it uses into the bracket categories from philosophy.md."""

import json

import anthropic

from .schemas import WORKER_SCHEMA

WORKER_SYSTEM_PROMPT = """\
You answer questions using ONLY the provided knowledge base. You must sort every \
piece of information you use into exactly these categories, and you must not skip \
the sorting step even when the answer feels obvious.

- observation: only what is literally in the knowledge base. Quote it verbatim — \
this will be checked against the source text mechanically, so paraphrasing here is \
a hard failure, not a style issue.
- definition: a description of a term. A definition must not, by itself, derive a \
claim — if it does, it was smuggling in a claim, not defining a term.
- assumption: something you need to bridge a gap between what's stated and what \
you want to conclude, when the knowledge base doesn't directly settle it. Required \
to be explicit whenever you use one — never resolve a gap silently.
- backed_claim: a claim derived from observations/definitions/assumptions via an \
explicit chain, with a real falsification path (what would show this is wrong).
- unverified_claim: a claim you can't back, or that you checked and found false.
- hypothesis: a forward-looking assumption — "I'm proceeding on this basis, but \
here's how it could break." Every hypothesis needs a falsification path.

Critically: if the knowledge base states two rules independently but never states \
what happens when both apply to the same situation at once, that combination is a \
GAP. Do not silently pick one rule and apply it. Surface the collision explicitly \
as an assumption or hypothesis, and say what you're assuming about how the rules \
interact and why.
"""


def run_worker(
    client: anthropic.Anthropic, knowledge_base: str, question: str, model: str = "claude-opus-5"
) -> dict:
    user_content = (
        f"Knowledge base:\n---\n{knowledge_base}\n---\n\nQuestion: {question}"
    )
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=WORKER_SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": WORKER_SCHEMA}},
        messages=[{"role": "user", "content": user_content}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
