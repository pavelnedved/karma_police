# tests/

External evaluation suites for the agents defined in `agents/` (via `runner.run_agent`).
This directory is deliberately separate from the agent implementation itself: nothing
here is imported by `api.py`, `run.py`, or `runner.py`, and nothing in here modifies
`agents/`. The one exception is `livebench/agents_ext.py`, which defines a *test-only*
agent variant (a fix for a scoring confound, not a first-class agent design decision) --
it imports from `agents/` but is never imported back.

## tests/livebench/

Scores `AGENT_BASE` / `AGENT_1` against real questions from the
[LiveBench](https://github.com/LiveBench/LiveBench) `reasoning` benchmark
(`web_of_lies_v2`, `spatial`, `zebra_puzzle` -- the only 3 of LiveBench's 8 reasoning
tasks with public ground truth). Scoring functions in `scorers.py` are copied verbatim
from LiveBench's own `process_results/` code, not reimplemented, so grading fidelity
matches the real benchmark.

- `scorers.py` -- LiveBench's scoring logic, copied as-is.
- `agents_ext.py` -- `AGENT_1_FORMATTED`: same bracket schema + system prompt as
  `agents.agent_1.AGENT_1`, plus one line telling the model to make `conclusion.text`
  follow the question's own requested output format verbatim. Without this, `AGENT_1`
  scores near-zero on LiveBench tasks for a *format* reason (prose vs. the exact
  `<solution>...</solution>` string the scorer expects), not a reasoning reason. See
  `RESULTS.md` for the details of that confound.
- `run_eval.py` -- the runner. `./.venv/bin/python tests/livebench/run_eval.py --version version_base --model claude-sonnet-5 --task zebra_puzzle`
- `data/questions.json` -- the 200 public reasoning questions, pulled once via the
  HuggingFace datasets-server API.
- `RESULTS.md` -- append-only log of every run: version, model, task, score, plus
  written analysis (the budget-matching correction, the multi-round/checker mismatch
  with `philosophy.md`'s actual thesis, etc.) -- read this before re-running anything,
  to avoid re-deriving conclusions already on record.

## tests/maze/

A from-scratch task (not from LiveBench) designed to separate *raw logical/spatial
reasoning ability* from *discipline* (does it use its own history correctly) from
*"thinking space"* (does it run out of per-turn budget) -- something no single-shot
puzzle benchmark can isolate, since it requires genuine multi-round tool use. Agent
navigates a blind grid maze (no visibility, no coordinates given back -- only
wall/obstacle/empty/goal per move) via karma_police's tool-use loop in `runner.py`.
Ground truth optimal path length computed via real BFS on the maze graph, which the
agent never sees.

Three separate, fully self-contained scripts (deliberately duplicated rather than
sharing library code) -- each one reproduces exactly as it was run, unaffected by
later edits to the others:

- `run_maze_eval.py` + `maze.py` -- the first pass: a small hand-placed 5x5 obstacle
  cluster. Found a clean, precise discipline signal: 100% task success, and
  ~100% of the "extra" moves over optimal were explained by *immediately repeating a
  move it had just been told fails*.
- `run_big_maze_eval.py` + `maze_gen.py` + `big_maze.py` -- 15x15, a real generated
  "perfect maze" (randomized recursive-backtracker: genuine corridors + dead ends,
  unique path between any two cells). Introduced the 4-way move-audit classification
  (`new_progress` / `backtrack` / `first_time_blocked` / `repeat_blocked` --
  see `big_maze.py:summarize_history`) that separates *necessary* blind-exploration
  cost from *genuinely avoidable* waste.
- `run_maze_20x20.py` -- fully self-contained (no shared imports at all, everything
  inlined) 20x20 version. First run to surface a real break: a `max_tokens` wall hit
  *mid-thinking*, not from repeated/wasted moves -- a resource-ceiling failure, not a
  logic or discipline one.

`RESULTS.md` in this directory is the full run log plus written analysis, including
the "why does BFS not pay an exploration cost" clarification and the credit-exhaustion
incident that cut short the last experiment (2026-08-29/30). Read it before re-running.
