"""agent_base: zero scaffolding. No system prompt, no output schema, no
bracket categories -- whatever the model does by default, unprompted. This
is the control condition every other agent is measured against."""

from .types import Agent

AGENT_BASE = Agent(name="agent_base")
