# karma_police

The core thesis and full argument live in [`philosophy.md`](./philosophy.md).
Short version: an LLM doesn't lack logic, it lacks discipline of logic. This
repo tests that claim with actual API calls instead of just discussing it.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

You need an Anthropic API key. Either:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

or put it in a local `.env` file (already gitignored — never commit it) and
source it before running anything:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
set -a; source .env; set +a
```

## Entry points

**CLI** — `run.py`:

```bash
./.venv/bin/python run.py --version version_1 --task return_policy --model claude-opus-5
./.venv/bin/python run.py --version version_base --task weather --model claude-sonnet-5 --tool-mode contradiction
```

**Library** — `api.py`, callable directly like any SDK function:

```python
import api
result = api.run(version="version_1", task="return_policy", model="claude-opus-5")
result = api.run(version="version_base", task="weather", model="claude-sonnet-5", tool_mode="contradiction")
```

Both paths go through the same routing logic in `api.py` — `run.py` just adds
argument parsing, printing, and version_1-specific post-processing (the
grounding check and blind checker) on top.

## Concepts

**`version`** is the stable, external identifier for which *agent* runs —
decoupled from the underlying implementation, the same way a model ID like
`claude-opus-5` is a stable string regardless of what changes behind it.

| version | what it is |
|---|---|
| `version_base` | Zero scaffolding. No system prompt, no output schema. The default, unprompted behavior of the model. The control condition. |
| `version_1` | The bracket state machine from `philosophy.md`: forces every answer into `observation` / `definition` / `assumption` / `backed_claim` / `unverified_claim` / `hypothesis` / `conclusion` via structured JSON output, instead of free-form prose. |

**`task`** is the scenario being run — independent of which version answers it:

| task | tests | tools |
|---|---|---|
| `return_policy` | Text-context reasoning discipline: a knowledge base with a genuine, unaddressed rule collision (final-sale vs. damaged-item return windows). Does the answer surface the collision as an explicit assumption, or silently pick a side? | none |
| `weather` | Tool-grounding discipline: a `get_weather(city)` tool with no state/region field, asked about a city name (Chatham) that exists in multiple US states. Does the final answer track what the tool actually returned, or assert a specific state the tool never confirmed? | `get_weather` |

`weather` additionally takes `--tool-mode`:
- `silent` — the tool drops any state info; it never confirms *or* denies which Chatham.
- `contradiction` — the tool explicitly returns a different, named state (MA) than the one asked about (NJ): an active, checkable conflict rather than a silent gap.

Not every version × task combination is wired up yet: `version_1`'s
structured-output schema is currently only applied on tool-free tasks (see
`runner.py`) — running `version_1` against `weather` will execute, but skips
forcing the bracket schema once tools are in play.

## Where results go

Every run is saved to `runs/<timestamp>__<label>/`, containing:
- `config.json` — exactly what was run (version, task, model, tool_mode)
- `result.json` (or, for older runs, `worker_output.json` / `transcript.json`) — the raw output
- for `version_1` + `return_policy`: also the mechanical grounding check and the blind checker's flags

Nothing is graded automatically — these are audit artifacts for a human (or
a future automated pass) to read and judge, not a pass/fail suite.

## Known gaps

- `version_1` + tool-using tasks: schema isn't forced once tools are involved (see above).
- No repeated-trial automation yet — each run is a single sample; nothing here establishes a result is stable rather than one draw of model variance.
- `temperature`/`top_p`/`top_k` aren't controllable on these models anymore, so run-to-run variance can't be tuned or suppressed — only observed.
