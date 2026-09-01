"""A small, hand-crafted 5x5 grid maze with a cluster of internal obstacles
that blocks the direct middle route but leaves a border route open --
designed so a real shortest path exists, but a naive agent that tries to
beeline diagonally through the middle will hit obstacles and need to
backtrack/detour to find it.

Coordinates: x in [0,4], y in [0,4]. up = y+1, down = y-1, right = x+1,
left = x-1. Agent has NO visibility into this layout -- it only learns
about a cell by trying to move into it.
"""

from collections import deque

GRID_SIZE = 5
START = (0, 0)
GOAL = (4, 4)

# Obstacle cluster roughly in the middle, leaving the border (and a couple
# of internal gaps) open.
OBSTACLES = {
    (1, 1), (1, 2), (1, 3),
    (2, 3),
    (3, 3), (3, 1), (3, 0),
}

MOVE_DELTAS = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}


def in_bounds(pos):
    x, y = pos
    return 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE


def bfs_shortest_path_length(start=START, goal=GOAL, obstacles=OBSTACLES):
    """True optimal move count, computed with full knowledge of the grid --
    this is the ground truth the agent (which has no visibility) is graded
    against."""
    if start == goal:
        return 0
    visited = {start}
    q = deque([(start, 0)])
    while q:
        pos, dist = q.popleft()
        for dx, dy in MOVE_DELTAS.values():
            nxt = (pos[0] + dx, pos[1] + dy)
            if not in_bounds(nxt) or nxt in obstacles or nxt in visited:
                continue
            if nxt == goal:
                return dist + 1
            visited.add(nxt)
            q.append((nxt, dist + 1))
    return None  # unreachable


class MazeState:
    """Tracks the agent's true (hidden) position and enforces a hard move
    cap. One fresh instance per trial."""

    def __init__(self, cap=40, start=START, goal=GOAL, obstacles=OBSTACLES):
        self.pos = start
        self.goal = goal
        self.obstacles = obstacles
        self.cap = cap
        self.move_count = 0
        self.done = False
        self.history = []  # list of (direction, result, position_after)

    def move(self, direction: str) -> str:
        if self.done:
            return "goal"  # already solved; further calls are no-ops
        if self.move_count >= self.cap:
            return "limit_reached"

        self.move_count += 1
        dx, dy = MOVE_DELTAS[direction]
        nxt = (self.pos[0] + dx, self.pos[1] + dy)

        if not in_bounds(nxt):
            result = "wall"
        elif nxt in self.obstacles:
            result = "obstacle"
        else:
            self.pos = nxt
            result = "goal" if self.pos == self.goal else "empty"
            if result == "goal":
                self.done = True

        self.history.append({"direction": direction, "result": result, "position_after": self.pos})
        return result


if __name__ == "__main__":
    print("optimal path length:", bfs_shortest_path_length())
