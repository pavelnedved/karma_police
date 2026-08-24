"""JSON schemas for the bracket state machine's structured output."""

WORKER_SCHEMA = {
    "type": "object",
    "properties": {
        "observations": {
            "type": "array",
            "description": (
                "Only what is literally present in the knowledge base. "
                "'text' must be an exact, verbatim substring of the knowledge base "
                "(quote it, do not paraphrase) so it can be mechanically checked."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string", "description": "Verbatim quote from the knowledge base."},
                },
                "required": ["id", "text"],
                "additionalProperties": False,
            },
        },
        "definitions": {
            "type": "array",
            "description": (
                "Descriptions of a term. Must NOT be directly actionable or derive a claim on "
                "their own — if removing this definition (keeping everything else) would still "
                "block the claim it's used for, it's a legitimate definition, not a smuggled claim."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "term": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["id", "term", "text"],
                "additionalProperties": False,
            },
        },
        "assumptions": {
            "type": "array",
            "description": (
                "What fills the gap between the input (observations+definitions) and a claim "
                "you want to reach, when the input doesn't directly derive it. Must be explicit."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "why_needed": {
                        "type": "string",
                        "description": "What gap this assumption fills and why it's needed to proceed.",
                    },
                },
                "required": ["id", "text", "why_needed"],
                "additionalProperties": False,
            },
        },
        "backed_claims": {
            "type": "array",
            "description": (
                "Claims derived from observations+definitions+assumptions via an explicit "
                "logic chain. Must carry a real falsification path."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "derived_from": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of observations/definitions/assumptions this claim relies on.",
                    },
                    "falsification_path": {
                        "type": "string",
                        "description": "What would show this claim is wrong.",
                    },
                },
                "required": ["id", "text", "derived_from", "falsification_path"],
                "additionalProperties": False,
            },
        },
        "unverified_claims": {
            "type": "array",
            "description": "Claims that are unverified, or that were checked and found false.",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "status": {"type": "string", "enum": ["unverified", "false"]},
                },
                "required": ["id", "text", "status"],
                "additionalProperties": False,
            },
        },
        "hypotheses": {
            "type": "array",
            "description": (
                "Forward-looking assumptions: 'we're moving ahead, but here's a case that could "
                "break this.' Every hypothesis must carry a falsification path."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "falsification_path": {"type": "string"},
                    "easily_falsifiable": {
                        "type": "boolean",
                        "description": "True if this could be checked cheaply right now (and should be, rather than assumed).",
                    },
                },
                "required": ["id", "text", "falsification_path", "easily_falsifiable"],
                "additionalProperties": False,
            },
        },
        "conclusion": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The final answer to the question."},
                "backed": {
                    "type": "boolean",
                    "description": "True only if the conclusion follows entirely from backed_claims with no unlabeled leap.",
                },
                "supporting_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IDs of backed_claims/assumptions/hypotheses the conclusion rests on.",
                },
            },
            "required": ["text", "backed", "supporting_ids"],
            "additionalProperties": False,
        },
    },
    "required": [
        "observations",
        "definitions",
        "assumptions",
        "backed_claims",
        "unverified_claims",
        "hypotheses",
        "conclusion",
    ],
    "additionalProperties": False,
}

CHECKER_SCHEMA = {
    "type": "object",
    "properties": {
        "flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "The id of the flagged item."},
                    "category": {
                        "type": "string",
                        "enum": [
                            "misclassified_observation",
                            "smuggled_claim_in_definition",
                            "weak_or_missing_falsification_path",
                            "unlabeled_leap",
                            "other",
                        ],
                    },
                    "reasoning": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["item_id", "category", "reasoning", "severity"],
                "additionalProperties": False,
            },
        },
        "assumption_recall_note": {
            "type": "string",
            "description": (
                "One sentence: does the set of assumptions+hypotheses look complete for the "
                "reasoning shown, or is there an obvious gap the worker didn't flag as an "
                "assumption at all (i.e. it just asserted something without labeling it)?"
            ),
        },
    },
    "required": ["flags", "assumption_recall_note"],
    "additionalProperties": False,
}
