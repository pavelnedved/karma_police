"""The one check that must not be LLM-judged: is a claimed 'observation'
actually traceable to the source, or is it smuggling in an inference under the
least-scrutinized label?"""


def check_observation_grounding(knowledge_base: str, observations: list[dict]) -> list[dict]:
    """Returns a list of {id, text, grounded} — grounded is a literal substring check."""
    results = []
    for obs in observations:
        grounded = obs["text"].strip() in knowledge_base
        results.append({"id": obs["id"], "text": obs["text"], "grounded": grounded})
    return results
