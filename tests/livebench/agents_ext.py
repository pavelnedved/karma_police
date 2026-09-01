"""Agent variants used only for LiveBench evaluation, kept separate from
karma_police's own agents/ package so that repo is never modified by this
eval tooling.

AGENT_1_FORMATTED reuses agent_1's exact bracket schema and system prompt
verbatim, adding one line: the model's conclusion.text (defined by the
schema as "the final answer to the question") must follow whatever output
format the *question itself* asked for, instead of paraphrasing the answer
as free prose. Without this, agent_1's conclusion.text was semantically
correct but scored 0 against LiveBench's exact-format scorer because it
described "position 1, hobby filmmaking, ..." instead of writing
"<solution>1, filmmaking, ...</solution>" -- a format confound, not a
reasoning failure. This isolates that confound so the comparison against
agent_base measures reasoning, not incidental format compliance.
"""

from agents.agent_1 import AGENT_1
from agents.types import Agent

AGENT_1_FORMATTED = Agent(
    name="agent_1_formatted",
    system_prompt=AGENT_1.system_prompt + (
        "\n\nThe user's question will often specify an exact output format for the "
        "final answer (for example, wrapping it in <solution>...</solution> tags, or "
        "bolding it a specific way). The `conclusion.text` field must follow that "
        "requested format exactly, verbatim -- it is not a natural-language summary "
        "or paraphrase of the answer, it IS the answer, formatted exactly as the "
        "question asked."
    ),
    output_schema=AGENT_1.output_schema,
)
