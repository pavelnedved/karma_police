"""Randomized recursive-backtracker maze generator -- produces a "perfect
maze": a spanning tree over the grid graph, so there's exactly one simple
path between any two cells, guaranteeing genuine corridors and real dead
ends (degree-1 nodes), unlike the earlier hand-placed obstacle-cluster maze.

Representation: a set of "open edges" (frozenset of two adjacent cells) --
you can move between two cells iff the edge between them is open. Anything
not in open_edges is an internal wall (reported as "obstacle" during play);
anything off the WxH grid is the boundary (reported as "wall").
"""

import random
from collections import deque

MOVE_DELTAS = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}


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


def bfs_shortest_path_length(open_edges, start, goal, width, height):
    dist = bfs_all_distances(open_edges, start, width, height)
    return dist.get(goal)


def dead_end_cells(open_edges, width, height, exclude):
    """Cells with exactly one open passage -- true dead ends of the maze."""
    degree = {}
    for edge in open_edges:
        for cell in edge:
            degree[cell] = degree.get(cell, 0) + 1
    return {c for c, d in degree.items() if d == 1 and c not in exclude}


def pick_start_goal(open_edges, width, height, target_distance):
    """Pick start=(0,0) and a goal whose BFS distance from start is as close
    as possible to target_distance (keeps the puzzle hard-but-tractable
    rather than using the full maze diameter, which can be impractically
    long for a real sequential API-driven run)."""
    start = (0, 0)
    dist = bfs_all_distances(open_edges, start, width, height)
    goal = min(dist, key=lambda c: (abs(dist[c] - target_distance), c))
    return start, goal, dist[goal]


if __name__ == "__main__":
    edges = generate_maze(15, 15, seed=42)
    start, goal, d = pick_start_goal(edges, 15, 15, target_distance=25)
    print("start", start, "goal", goal, "optimal distance", d)
    dead_ends = dead_end_cells(edges, 15, 15, exclude={start, goal})
    print("num dead ends:", len(dead_ends))
