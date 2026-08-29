"""The public entrypoint for this project — call this the way you'd call an
SDK function, e.g. client.messages.create(model=...).

`version` is a stable, externally-facing routing string. It maps to an
internal Agent implementation, but the mapping is this module's problem, not
the caller's — a caller pinned to "version_1" keeps working even if agent_1's
internals change, and a new "version_2" can be added later without touching
this function's signature or breaking version_base/version_1 callers.

    import api
    result = api.run(version="version_1", task="return_policy", model="claude-opus-5")
    result = api.run(version="version_base", task="weather", model="claude-sonnet-5",
                      tool_mode="contradiction")

This function returns the raw result from runner.run_agent, unprocessed —
version_1-specific post-processing (the mechanical grounding check, the
blind checker) is a concern of the caller (see run.py), not of this routing
layer, since it only makes sense for agents that emit bracket-schema output.
"""

from agents.agent_1 import AGENT_1
from agents.agent_base import AGENT_BASE
from agents.types import Agent
from runner import run_agent
from tasks import return_policy, weather

VERSIONS: dict = {
    "version_base": AGENT_BASE,
    "version_1": AGENT_1,
}

TASKS = ("return_policy", "weather")


def list_versions() -> list:
    return sorted(VERSIONS)


def list_tasks() -> list:
    return list(TASKS)


def get_agent(version: str) -> Agent:
    if version not in VERSIONS:
        raise ValueError(f"Unknown version {version!r}. Available: {list_versions()}")
    return VERSIONS[version]


def run(
    version: str,
    task: str,
    model: str,
    tool_mode: str = "silent",
    **run_agent_kwargs,
) -> dict:
    agent = get_agent(version)

    if task == "weather":
        if tool_mode not in weather.TOOL_MODES:
            raise ValueError(
                f"Unknown tool_mode {tool_mode!r}. Available: {sorted(weather.TOOL_MODES)}"
            )
        return run_agent(
            agent,
            model,
            weather.QUESTION,
            tools=[weather.GET_WEATHER_TOOL],
            tool_impls=weather.build_tool_impls(tool_mode),
            **run_agent_kwargs,
        )
    elif task == "return_policy":
        return run_agent(
            agent,
            model,
            return_policy.build_user_message(),
            **run_agent_kwargs,
        )
    else:
        raise ValueError(f"Unknown task {task!r}. Available: {list_tasks()}")
