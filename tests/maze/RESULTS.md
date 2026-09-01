# Maze agent eval results

Blind grid-maze navigation: agent_base (karma_police), no maze visibility, move tool returns only wall/obstacle/empty/goal. Ground truth optimal path length computed via BFS in maze.py (agent never sees this). See maze.py for the fixed 5x5 layout used across all runs.

| timestamp | model | trials | cap | optimal | success rate | avg moves (successful) | avg excess | detail file |
|---|---|---|---|---|---|---|---|---|
| 20260829-211652 | claude-sonnet-5 | 1 | 40 | 8 | 100.0% | 10.0 | 2.0 | `results/20260829-211652__agent_base__claude-sonnet-5.json` |
| 20260829-211726 | claude-sonnet-5 | 5 | 40 | 8 | 100.0% | 12.0 | 4.0 | `results/20260829-211726__agent_base__claude-sonnet-5.json` |

## Analysis: what causes the excess moves? (5-trial run, 20260829-211726)

Motivation: distinguish three possible causes of any failure/inefficiency --
(1) lacks logical/spatial reasoning ability, (2) lacks discipline (doesn't
properly use its own history/tool feedback), (3) lacks "thinking space"
(runs out of token budget mid-reasoning). This task was designed so #3 is
essentially ruled out by construction (each turn is short, cheap, no
truncation risk) and #1 is testable directly (grid navigation logic is
trivial), isolating whatever's left as evidence about #2.

Result: **5/5 trials succeeded** (rules out #1 -- it always eventually finds
and executes the correct border route around the obstacle cluster). But
efficiency varied 10-16 moves against an optimal of 8. Counting "immediate
repeat of a move that was *just* told to fail (wall/obstacle) on the
previous turn, with no direction change in between":

| trial | moves used | excess over optimal | immediate-repeat-of-failed-move count |
|---|---|---|---|
| 1 | 10 | 2 | 0 |
| 4 | 10 | 2 | 0 |
| 0 | 12 | 4 | 2 |
| 2 | 12 | 4 | 2 |
| 3 | 16 | 8 | 5 |

The repeat count tracks the excess almost exactly. Concrete example from
trial 3: at position (4,3) it tried `left` (-> obstacle), then tried `left`
again, and again, and again -- four identical attempts at a move it had just
been told was blocked, before finally trying `up` (which succeeded). Same
pattern (try, get "obstacle", immediately retry the identical direction once
more) recurs at two other points in the same trial and in trials 0 and 2.

**Conclusion:** for this task, essentially all observed inefficiency reduces
to one narrow, precisely-identifiable discipline gap -- failing to
incorporate the immediately-preceding tool result before choosing the next
action -- rather than any deficit in spatial/logical reasoning (#1, ruled
out by the 100% success rate) or token/context budget (#3, not applicable to
short per-turn tool decisions). This is a much cleaner #1-vs-#2-vs-#3 signal
than the zebra_puzzle test could give, precisely because this task was
designed to make the raw logic trivial and the per-turn cost negligible.

## Big maze (real corridors + dead ends) results

| timestamp | model | trials | cap | maze | optimal | success rate | avg moves | avg redundancy ratio | avg repeats (delayed) | detail file |
|---|---|---|---|---|---|---|---|---|---|---|
| 20260829-212957 | claude-sonnet-5 | 1 | 150 | 15x15 (25 dead ends) | 25 | 0.0% | - | - | - | `results/20260829-212957__bigmaze__agent_base__claude-sonnet-5.json` |
| 20260829-213302 | claude-sonnet-5 | 1 | 150 | 15x15 (25 dead ends) | 25 | 100.0% | 45.0 | 1.73 | 1.0 (0.0 delayed) | `results/20260829-213302__bigmaze__agent_base__claude-sonnet-5.json` |
| 20260829-213414 | claude-sonnet-5 | 1 | 150 | 15x15 (25 dead ends) | 25 | 100.0% | 43.0 | 1.65 | 0.0 (0.0 delayed) | `results/20260829-213414__bigmaze__agent_base__claude-sonnet-5.json` |
| 20260829-213629 | claude-sonnet-5 | 5 | 150 | 15x15 (25 dead ends) | 25 | 100.0% | 44.2 | 1.70 | 0.6 (0.0 delayed) | `results/20260829-213629__bigmaze__agent_base__claude-sonnet-5.json` |
| 20260829-214015 | claude-sonnet-5 | 1 | 150 | 15x15 (25 dead ends) | 25 | 100.0% | 42.0 | 1.62 | 0.0 (0.0 delayed) | `results/20260829-214015__bigmaze__agent_base__claude-sonnet-5.json` |
| 20260829-214203 | claude-sonnet-5 | 1 | 150 | 15x15 (25 dead ends) | 25 | 100.0% | 42.0 | 1.62 | 0.0 (0.0 delayed) | `results/20260829-214203__bigmaze__agent_base__claude-sonnet-5.json` |
| 20260829-220901 | claude-sonnet-5 | 1 | 250 | 20x20 (48 dead ends) | 35 | 100.0% | 59.0 | 35.0 | 0.0 | 23.0 | 1.0 | 23.0 | 1.0 | `results/20260829-220901__maze20x20__agent_base__claude-sonnet-5.json` |
| 20260829-221150 | claude-sonnet-5 | 3 | 250 | 20x20 (48 dead ends) | 35 | 66.7% | 64.5 | 35.0 | 1.0 | 28.0 | 0.5 | 28.0 | 1.5 | `results/20260829-221150__maze20x20__agent_base__claude-sonnet-5.json` |
| 20260829-221452 | claude-sonnet-5 | 3 | 250 | 20x20 (48 dead ends) | 35 | 0.0% | - | - | - | - | - | - | - | `results/20260829-221452__maze20x20__agent_base__claude-sonnet-5.json` |
| 20260829-221642 | claude-sonnet-5 | 1 | 250 | 20x20 (48 dead ends) | 35 | 100.0% | 68.0 | 35.0 | 0.0 | 26.0 | 7.0 | 26.0 | 7.0 | `results/20260829-221642__maze20x20__agent_base__claude-sonnet-5.json` |
| 20260829-222254 | claude-sonnet-5 | 5 | 250 | 20x20 (48 dead ends) | 35 | 60.0% | 65.7 | 35.0 | 0.7 | 29.0 | 1.0 | 29.0 | 1.7 | `results/20260829-222254__maze20x20__agent_base__claude-sonnet-5.json` |
