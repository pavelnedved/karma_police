"""Stateful play tracker for the generated perfect-maze (see maze_gen.py).
Same move() contract as the original 5x5 MazeState (wall/obstacle/empty/goal,
hard move cap), plus richer waste tracking:

- attempted_actions: every (position, direction) pair ever tried in this
  trial, with the move-index it was first tried at -- lets us detect a
  *delayed* repeat (tried again much later, not just immediately after),
  which is the "re-entering the same dead end" signal specifically asked for.
- visited cells set, for a distinct-cells-visited redundancy ratio.
"""

from maze_gen import MOVE_DELTAS


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
        self.history = []  # per-move dicts, see below
        self.visited_cells = {start}
        self.attempted_actions = {}  # (position, direction) -> first move_index tried

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
            "repeat_of_move_index": repeat_of,  # None if first time trying this (position,direction)
            "category": category,
        })
        return result


def summarize_history(history, optimal_moves):
    """Audit summary: partitions every move into exactly one of 4 categories.
    new_progress + backtrack should sum to moves that changed position;
    first_time_blocked + repeat_blocked should sum to moves that didn't.
    repeat_blocked is the one genuine "avoidable waste" signal -- everything
    else is either real progress or an unavoidable cost of blind exploration."""
    counts = {"new_progress": 0, "backtrack": 0, "first_time_blocked": 0, "repeat_blocked": 0}
    repeat_gaps = []
    for m in history:
        counts[m["category"]] += 1
        if m["category"] == "repeat_blocked":
            repeat_gaps.append(m["move_index"] - m["repeat_of_move_index"])

    total = len(history)
    return {
        "total_moves": total,
        "optimal_moves": optimal_moves,
        "new_progress": counts["new_progress"],
        "backtrack": counts["backtrack"],
        "first_time_blocked": counts["first_time_blocked"],
        "repeat_blocked": counts["repeat_blocked"],
        "immediate_repeats": sum(1 for g in repeat_gaps if g == 1),
        "delayed_repeats": sum(1 for g in repeat_gaps if g > 1),
        # efficiency of the PATH actually taken vs optimal, ignoring exploration cost
        "path_efficiency": (optimal_moves / counts["new_progress"]) if counts["new_progress"] else None,
        # how much of the total cost was genuinely avoidable waste vs necessary blind-search cost
        "avoidable_waste_moves": counts["backtrack"] + counts["repeat_blocked"],
        "necessary_exploration_moves": counts["first_time_blocked"],
    }
