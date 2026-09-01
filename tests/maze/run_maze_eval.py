"""Run karma_police's AGENT_BASE through a blind grid-maze navigation task,
N independent trials, and measure: (1) does it find the goal at all, (2) how
many moves does it take vs. the true BFS-optimal path length.

No visibility into the maze is given -- only grid size, start position, and
move-cap are disclosed up front. Each move returns one of
wall/obstacle/empty/goal, nothing else (no coordinates). The agent has to
track its own position from its own conversation history.

Usage:
    ./.venv/bin/python run_maze_eval.py --trials 5 --model claude-sonnet-5
"""

import argparse
import datetime
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
KARMA_POLICE = HERE.parent.parent  # tests/maze/ -> tests/ -> repo root
sys.path.insert(0, str(KARMA_POLICE))

from agents.agent_base import AGENT_BASE  # noqa: E402
from runner import run_agent  # noqa: E402

from maze import GRID_SIZE, START, MazeState, bfs_shortest_path_length  # noqa: E402

MOVE_TOOL = {
    "name": "move",
    "description": (
        "Attempt to move one step in the maze in the given direction. Returns: "
        "'wall' (hit the maze boundary, you did not move), 'obstacle' (hit an "
        "internal blocked cell, you did not move), 'empty' (moved successfully "
        "into an open, non-goal cell), or 'goal' (moved successfully and found "
        "the goal -- the maze is solved)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["up", "down", "left", "right"],
                "description": "up increases y, down decreases y, right increases x, left decreases x.",
            }
        },
        "required": ["direction"],
    },
}

PROMPT = f"""You are in a {GRID_SIZE}x{GRID_SIZE} grid maze. Valid coordinates range from \
(0,0) to ({GRID_SIZE - 1},{GRID_SIZE - 1}). You start at position {START}. There is exactly \
one goal cell somewhere in the maze -- you do not know where it is or what the maze looks \
like. You have a `move` tool that moves you one step up, down, left, or right.

Each call to `move` returns one of:
- "wall": you tried to move outside the grid boundary; you did not move.
- "obstacle": you tried to move into a blocked cell; you did not move.
- "empty": you moved successfully into an open, non-goal cell.
- "goal": you moved successfully and found the goal. The maze is solved -- \
stop calling the tool and reply with a short text message reporting that you \
found the goal.

You have at most 40 moves total. Try to find the goal in as few moves as \
possible. Keep track of where you believe you are and which directions \
you've already tried from each position, so you don't waste moves repeating \
things you already know don't work."""


def run_one_trial(trial_id, model, cap, max_tool_rounds):
    state = MazeState(cap=cap)
    tool_impls = {"move": lambda inp, s=state: s.move(inp["direction"])}

    t0 = time.time()
    try:
        out = run_agent(
            AGENT_BASE,
            model=model,
            user_message=PROMPT,
            tools=[MOVE_TOOL],
            tool_impls=tool_impls,
            max_tool_rounds=max_tool_rounds,
            max_tokens=2048,
        )
        error = None
        final_text = out["final_text"]
        num_rounds = len(out["rounds"])
        hit_round_cap = out["hit_round_cap"]
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        final_text = None
        num_rounds = None
        hit_round_cap = None
    elapsed = time.time() - t0

    optimal = bfs_shortest_path_length()
    return {
        "trial_id": trial_id,
        "success": state.done,
        "moves_used": state.move_count,
        "optimal_moves": optimal,
        "excess_moves": (state.move_count - optimal) if state.done else None,
        "hit_move_cap": state.move_count >= cap and not state.done,
        "num_api_rounds": num_rounds,
        "hit_api_round_cap": hit_round_cap,
        "elapsed_seconds": elapsed,
        "final_text": final_text,
        "move_history": state.history,
        "error": error,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--cap", type=int, default=40, help="max moves per trial")
    ap.add_argument("--max-tool-rounds", type=int, default=50, help="max API round-trips per trial")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()

    optimal = bfs_shortest_path_length()
    print(f"Optimal path length (BFS ground truth): {optimal}")
    print(f"Running {args.trials} trials, model={args.model}, cap={args.cap} moves...")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(run_one_trial, i, args.model, args.cap, args.max_tool_rounds): i
            for i in range(args.trials)
        }
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            status = "SUCCESS" if r["success"] else ("ERROR" if r["error"] else "FAILED (cap hit)")
            print(f"  trial {r['trial_id']}: {status}, moves_used={r['moves_used']}, "
                  f"excess={r['excess_moves']}, elapsed={r['elapsed_seconds']:.1f}s")

    results.sort(key=lambda r: r["trial_id"])
    successes = [r for r in results if r["success"]]
    success_rate = len(successes) / len(results)
    avg_moves_successful = sum(r["moves_used"] for r in successes) / len(successes) if successes else None
    avg_excess_successful = sum(r["excess_moves"] for r in successes) / len(successes) if successes else None

    print(f"\n=== Summary ===")
    print(f"success rate: {len(successes)}/{len(results)} = {success_rate:.1%}")
    if successes:
        print(f"avg moves used (successful trials): {avg_moves_successful:.1f} (optimal: {optimal})")
        print(f"avg excess moves over optimal: {avg_excess_successful:.1f}")

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"{timestamp}__agent_base__{args.model}.json"
    out_path.write_text(json.dumps({
        "timestamp": timestamp,
        "model": args.model,
        "trials": args.trials,
        "cap": args.cap,
        "optimal_moves": optimal,
        "success_rate": success_rate,
        "avg_moves_successful": avg_moves_successful,
        "avg_excess_successful": avg_excess_successful,
        "results": results,
    }, indent=2))
    print(f"\nDetail written to {out_path}")
    append_results_md(timestamp, args, optimal, success_rate, avg_moves_successful, avg_excess_successful, out_path)


def append_results_md(timestamp, args, optimal, success_rate, avg_moves, avg_excess, out_path):
    md_path = HERE / "RESULTS.md"
    header = (
        "# Maze agent eval results\n\n"
        "Blind grid-maze navigation: agent_base (karma_police), no maze "
        "visibility, move tool returns only wall/obstacle/empty/goal. Ground "
        "truth optimal path length computed via BFS in maze.py (agent never "
        "sees this). See maze.py for the fixed 5x5 layout used across all runs.\n\n"
        "| timestamp | model | trials | cap | optimal | success rate | avg moves (successful) | avg excess | detail file |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    row = (
        f"| {timestamp} | {args.model} | {args.trials} | {args.cap} | {optimal} | "
        f"{success_rate:.1%} | {f'{avg_moves:.1f}' if avg_moves else '-'} | "
        f"{f'{avg_excess:.1f}' if avg_excess is not None else '-'} | "
        f"`results/{out_path.name}` |\n"
    )
    if not md_path.exists():
        md_path.write_text(header)
    with md_path.open("a") as f:
        f.write(row)
    print(f"Summary appended to {md_path}")


if __name__ == "__main__":
    main()
