"""An Agent is just a system prompt (or none) plus an optional output schema
(or none) that forces structured output. Nothing task-specific lives here --
any Agent should be runnable against any task via runner.run_agent."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Agent:
    name: str
    system_prompt: Optional[str] = None
    output_schema: Optional[dict] = None
