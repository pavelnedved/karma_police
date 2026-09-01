"""Standalone, self-contained 20x20 maze-agent eval. Deliberately duplicates
everything from the 15x15 version (maze generation, BFS, state tracker,
move-audit categorization, runner) rather than importing shared modules --
so this file reproduces exactly as run, immune to any later edits elsewhere.

Blind grid-maze navigation: karma_police's AGENT_BASE, no maze visibility.
move tool returns only wall/obstacle/empty/goal, nothing else. Ground truth
optimal path length computed via BFS over the fully-known maze graph (the
agent never sees this graph). Move-audit classifies every move into exactly
one of: new_progress, backtrack, first_time_blocked, repeat_blocked -- see
"Analysis" comment at the bottom for what each means.

Usage:
    ./.venv/bin/python run_maze_20x20.py --trials 3 --model claude-sonnet-5 --max-tokens 12000
"""

import argparse
import datetime
import json
import random
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
KARMA_POLICE = HERE.parent.parent  # tests/maze/ -> tests/ -> repo root
sys.path.insert(0, str(KARMA_POLICE))

from agents.agent_base import AGENT_BASE  # noqa: E402
from runner import run_agent  # noqa: E402

WIDTH, HEIGHT = 20, 20
SEED = 42
TARGET_DISTANCE = 35

MOVE_DELTAS = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}


# ---------------------------------------------------------------------------
# Maze generation (randomized recursive-backtracker -- a "perfect maze":
# exactly one simple path between any two cells, guaranteeing real corridors
# and genuine dead ends).
# ---------------------------------------------------------------------------

def neighbors(cell, w, h):
    x, y = cell
    for dx, dy in MOVE_DELTAS.values():
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            yield (nx, ny)


def generate_maze(width, height, seed):
    rng = random.Random(seed)
    start_cell = (0, 0)
    visited = {start_cell}
    open_edges = set()
    stack = [start_cell]
    while stack:
        cell = stack[-1]
        unvisited = [n for n in neighbors(cell, width, height) if n not in visited]
        if not unvisited:
            stack.pop()
            continue
        nxt = rng.choice(unvisited)
        open_edges.add(frozenset((cell, nxt)))
        visited.add(nxt)
        stack.append(nxt)
    return open_edges


def bfs_all_distances(open_edges, source, width, height):
    dist = {source: 0}
    q = deque([source])
    while q:
        cell = q.popleft()
        for n in neighbors(cell, width, height):
            if frozenset((cell, n)) in open_edges and n not in dist:
                dist[n] = dist[cell] + 1
                q.append(n)
    return dist


def dead_end_cells(open_edges, width, height, exclude):
    degree = {}
    for edge in open_edges:
        for cell in edge:
            degree[cell] = degree.get(cell, 0) + 1
    return {c for c, d in degree.items() if d == 1 and c not in exclude}


def pick_start_goal(open_edges, width, height, target_distance):
    start = (0, 0)
    dist = bfs_all_distances(open_edges, start, width, height)
    goal = min(dist, key=lambda c: (abs(dist[c] - target_distance), c))
    return start, goal, dist[goal]


# ---------------------------------------------------------------------------
# Stateful play tracker + move-audit classification.
# ---------------------------------------------------------------------------

class BigMazeState:
    def __init__(self, open_edges, start, goal, width, height, cap):
        self.open_edges = open_edges
        self.pos = start
        self.start = start
        self.goal = goal
        self.width = width
        self.height = height
        self.cap = cap
        self.move_count = 0
        self.done = False
        self.history = []
        self.visited_cells = {start}
        self.attempted_actions = {}

    def move(self, direction: str) -> str:
        if self.done:
            return "goal"
        if self.move_count >= self.cap:
            return "limit_reached"

        move_index = self.move_count
        self.move_count += 1

        action_key = (self.pos, direction)
        repeat_of = self.attempted_actions.get(action_key)
        if repeat_of is None:
            self.attempted_actions[action_key] = move_index

        dx, dy = MOVE_DELTAS[direction]
        nxt = (self.pos[0] + dx, self.pos[1] + dy)

        if not (0 <= nxt[0] < self.width and 0 <= nxt[1] < self.height):
            result = "wall"
            visited_before = None
        elif frozenset((self.pos, nxt)) not in self.open_edges:
            result = "obstacle"
            visited_before = None
        else:
            visited_before = nxt in self.visited_cells
            self.pos = nxt
            self.visited_cells.add(nxt)
            result = "goal" if self.pos == self.goal else "empty"
            if result == "goal":
                self.done = True

        if result in ("wall", "obstacle"):
            category = "repeat_blocked" if repeat_of is not None else "first_time_blocked"
        else:
            category = "backtrack" if visited_before else "new_progress"

        self.history.append({
            "move_index": move_index,
            "direction": direction,
            "position_before": action_key[0],
            "result": result,
            "position_after": self.pos,
            "repeat_of_move_index": repeat_of,
            "category": category,
        })
        return result


def summarize_history(history, optimal_moves):
    """new_progress = real forward progress into a new cell. backtrack = moved
    into an already-visited cell (redundant). first_time_blocked = wall/obstacle
    on an untried action -- necessary, unavoidable cost of blind exploration,
    NOT waste. repeat_blocked = wall/obstacle on an action already known to
    fail -- genuine avoidable waste, the real discipline signal."""
    counts = {"new_progress": 0, "backtrack": 0, "first_time_blocked": 0, "repeat_blocked": 0}
    repeat_gaps = []
    for m in history:
        counts[m["category"]] += 1
        if m["category"] == "repeat_blocked":
            repeat_gaps.append(m["move_index"] - m["repeat_of_move_index"])
    return {
        "total_moves": len(history),
        "optimal_moves": optimal_moves,
        "new_progress": counts["new_progress"],
        "backtrack": counts["backtrack"],
        "first_time_blocked": counts["first_time_blocked"],
        "repeat_blocked": counts["repeat_blocked"],
        "immediate_repeats": sum(1 for g in repeat_gaps if g == 1),
        "delayed_repeats": sum(1 for g in repeat_gaps if g > 1),
        "path_efficiency": (optimal_moves / counts["new_progress"]) if counts["new_progress"] else None,
        "avoidable_waste_moves": counts["backtrack"] + counts["repeat_blocked"],
        "necessary_exploration_moves": counts["first_time_blocked"],
    }


# ---------------------------------------------------------------------------
# Agent harness
# ---------------------------------------------------------------------------

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


def build_prompt(start, cap):
    return f"""You are in a {WIDTH}x{HEIGHT} grid maze. Valid coordinates range from \
(0,0) to ({WIDTH - 1},{HEIGHT - 1}). You start at position {start}. There is exactly \
one goal cell somewhere in the maze -- you do not know where it is or what the maze \
looks like. This is a real maze: there are corridors and dead ends, not just a \
simple open field. You have a `move` tool that moves you one step up, down, left, \
or right.

Each call to `move` returns one of:
- "wall": you tried to move outside the grid boundary; you did not move.
- "obstacle": you tried to move into a blocked cell; you did not move.
- "empty": you moved successfully into an open, non-goal cell.
- "goal": you moved successfully and found the goal. The maze is solved -- \
stop calling the tool and reply with a short text message reporting that you \
found the goal.

You have at most {cap} moves total. Try to find the goal in as few moves as \
possible. Keep track of where you believe you are, which directions you've \
already tried from each position, and which paths you've already fully \
explored (including dead ends you've already backed out of), so you don't \
waste moves repeating things you already know."""


def run_one_trial(trial_id, model, open_edges, start, goal, optimal, cap, max_tool_rounds, max_tokens):
    state = BigMazeState(open_edges, start, goal, WIDTH, HEIGHT, cap)
    tool_impls = {"move": lambda inp, s=state: s.move(inp["direction"])}
    prompt = build_prompt(start, cap)

    t0 = time.time()
    try:
        out = run_agent(
            AGENT_BASE, model=model, user_message=prompt,
            tools=[MOVE_TOOL], tool_impls=tool_impls,
            max_tool_rounds=max_tool_rounds, max_tokens=max_tokens,
        )
        error = None
        final_text = out["final_text"]
        hit_round_cap = out["hit_round_cap"]
        last_round_stop_reason = out["rounds"][-1]["stop_reason"] if out["rounds"] else None
        last_round_block_types = [b["type"] for b in out["rounds"][-1]["content"]] if out["rounds"] else None
        round_texts = [
            b["text"] for rnd in out["rounds"] for b in rnd["content"] if b["type"] == "text" and b["text"].strip()
        ]
        round_thinking = [
            b["thinking"] for rnd in out["rounds"] for b in rnd["content"]
            if b["type"] == "thinking" and b.get("thinking", "").strip()
        ]
        round_block_type_counts = {}
        for rnd in out["rounds"]:
            for b in rnd["content"]:
                round_block_type_counts[b["type"]] = round_block_type_counts.get(b["type"], 0) + 1
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        final_text = None
        hit_round_cap = None
        last_round_stop_reason = None
        last_round_block_types = None
        round_texts = []
        round_thinking = []
        round_block_type_counts = {}
    elapsed = time.time() - t0

    audit = summarize_history(state.history, optimal)
    distinct_cells = len(state.visited_cells)
    repeat_examples = [
        {
            "position": list(m["position_before"]), "direction": m["direction"],
            "first_tried_at_move": m["repeat_of_move_index"], "repeated_at_move": m["move_index"],
            "gap": m["move_index"] - m["repeat_of_move_index"],
        }
        for m in state.history if m["category"] == "repeat_blocked"
    ][:10]

    return {
        "trial_id": trial_id, "success": state.done, "moves_used": state.move_count,
        "hit_move_cap": state.move_count >= cap and not state.done,
        "hit_api_round_cap": hit_round_cap, "elapsed_seconds": elapsed,
        "final_text": final_text, "last_round_stop_reason": last_round_stop_reason,
        "last_round_block_types": last_round_block_types, "round_texts": round_texts,
        "round_thinking": round_thinking, "round_block_type_counts": round_block_type_counts,
        "error": error, "distinct_cells_visited": distinct_cells, "audit": audit,
        "repeat_examples": repeat_examples, "move_history": state.history,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--cap", type=int, default=250)
    ap.add_argument("--max-tool-rounds", type=int, default=260)
    ap.add_argument("--max-tokens", type=int, default=12000)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    open_edges = generate_maze(WIDTH, HEIGHT, seed=SEED)
    start, goal, optimal = pick_start_goal(open_edges, WIDTH, HEIGHT, TARGET_DISTANCE)
    n_dead_ends = len(dead_end_cells(open_edges, WIDTH, HEIGHT, exclude={start, goal}))

    print(f"Maze: {WIDTH}x{HEIGHT}, seed={SEED}, start={start}, goal={goal}, "
          f"optimal={optimal}, dead_ends={n_dead_ends}")
    print(f"Running {args.trials} trials, model={args.model}, cap={args.cap} moves...")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(run_one_trial, i, args.model, open_edges, start, goal, optimal,
                      args.cap, args.max_tool_rounds, args.max_tokens): i
            for i in range(args.trials)
        }
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            a = r["audit"]
            status = "SUCCESS" if r["success"] else ("ERROR" if r["error"] else "FAILED (cap hit)")
            print(f"  trial {r['trial_id']}: {status}, moves={a['total_moves']} "
                  f"[new_progress={a['new_progress']}, backtrack={a['backtrack']}, "
                  f"first_time_blocked={a['first_time_blocked']}, repeat_blocked={a['repeat_blocked']} "
                  f"(imm={a['immediate_repeats']}/delayed={a['delayed_repeats']})], "
                  f"elapsed={r['elapsed_seconds']:.1f}s")

    results.sort(key=lambda r: r["trial_id"])
    successes = [r for r in results if r["success"]]
    success_rate = len(successes) / len(results)

    print(f"\n=== Summary ===")
    print(f"success rate: {len(successes)}/{len(results)} = {success_rate:.1%}")
    if successes:
        n = len(successes)
        avg_moves = sum(r["moves_used"] for r in successes) / n
        avg_new_progress = sum(r["audit"]["new_progress"] for r in successes) / n
        avg_backtrack = sum(r["audit"]["backtrack"] for r in successes) / n
        avg_first_blocked = sum(r["audit"]["first_time_blocked"] for r in successes) / n
        avg_repeat_blocked = sum(r["audit"]["repeat_blocked"] for r in successes) / n
        avg_avoidable_waste = sum(r["audit"]["avoidable_waste_moves"] for r in successes) / n
        avg_necessary = sum(r["audit"]["necessary_exploration_moves"] for r in successes) / n
        print(f"avg moves used: {avg_moves:.1f} (optimal: {optimal})")
        print(f"  new_progress={avg_new_progress:.1f}  backtrack={avg_backtrack:.1f}  "
              f"first_time_blocked={avg_first_blocked:.1f}  repeat_blocked={avg_repeat_blocked:.1f}")
        print(f"avg NECESSARY exploration cost (first_time_blocked): {avg_necessary:.1f}")
        print(f"avg AVOIDABLE waste (backtrack + repeat_blocked): {avg_avoidable_waste:.1f}")
    else:
        avg_moves = avg_new_progress = avg_backtrack = avg_first_blocked = None
        avg_repeat_blocked = avg_avoidable_waste = avg_necessary = None

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"{timestamp}__maze20x20__agent_base__{args.model}.json"
    out_path.write_text(json.dumps({
        "timestamp": timestamp, "model": args.model, "trials": args.trials, "cap": args.cap,
        "maze": {"width": WIDTH, "height": HEIGHT, "seed": SEED, "start": start, "goal": goal,
                 "optimal_moves": optimal, "num_dead_ends": n_dead_ends},
        "success_rate": success_rate, "avg_moves": avg_moves,
        "avg_new_progress": avg_new_progress, "avg_backtrack": avg_backtrack,
        "avg_first_time_blocked": avg_first_blocked, "avg_repeat_blocked": avg_repeat_blocked,
        "avg_necessary_exploration_moves": avg_necessary, "avg_avoidable_waste_moves": avg_avoidable_waste,
        "results": results,
    }, indent=2))
    print(f"\nDetail written to {out_path}")

    md_path = HERE / "RESULTS.md"

    def f(x, fmt="{:.1f}"):
        return fmt.format(x) if x is not None else "-"

    row = (
        f"| {timestamp} | {args.model} | {args.trials} | {args.cap} | {WIDTH}x{HEIGHT} ({n_dead_ends} dead ends) | "
        f"{optimal} | {success_rate:.1%} | {f(avg_moves)} | {f(avg_new_progress)} | {f(avg_backtrack)} | "
        f"{f(avg_first_blocked)} | {f(avg_repeat_blocked)} | {f(avg_necessary)} | {f(avg_avoidable_waste)} | "
        f"`results/{out_path.name}` |\n"
    )
    content = md_path.read_text() if md_path.exists() else ""
    if "## Big maze" not in content:
        content += (
            "\n## Big maze (real corridors + dead ends) results\n\n"
            "Move audit categories: new_progress (real forward progress, new cell), "
            "backtrack (moved into an already-visited cell -- redundant), "
            "first_time_blocked (wall/obstacle on an untried action -- necessary, "
            "unavoidable cost of blind exploration, NOT waste), repeat_blocked "
            "(wall/obstacle on an action already known to fail -- genuine avoidable "
            "waste, the real discipline signal). Each maze size uses its own "
            "standalone, self-contained script (run_big_maze_eval.py for 15x15, "
            "run_maze_20x20.py for 20x20, etc.) rather than shared imports, so each "
            "past run reproduces exactly regardless of later edits.\n\n"
            "| timestamp | model | trials | cap | maze | optimal | success rate | avg moves | "
            "avg new_progress | avg backtrack | avg first_time_blocked | avg repeat_blocked | "
            "avg necessary cost | avg avoidable waste | detail file |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        )
    content += row
    md_path.write_text(content)
    print(f"Summary appended to {md_path}")


if __name__ == "__main__":
    main()
