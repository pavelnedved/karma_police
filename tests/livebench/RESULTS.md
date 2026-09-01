# LiveBench reasoning eval results

Data source: `livebench/reasoning` on HuggingFace (public rows only: web_of_lies_v2, spatial, zebra_puzzle — the other 5 reasoning tasks have no public ground truth as of this writing). Scoring uses LiveBench's own scorer functions, copied verbatim in `scorers.py`.

| timestamp | version | model | task filter | n | overall mean score | errors | elapsed (s) | detail file |
|---|---|---|---|---|---|---|---|---|
| 20260829-133848 | version_base | claude-sonnet-5 | all | 6 | 0.500 | 0 | 40.2 | `results/20260829-133848__version_base__claude-sonnet-5.json` |
  - `spatial`: n=2, mean_score=0.000, exact_correct=0
  - `web_of_lies_v2`: n=2, mean_score=0.500, exact_correct=1
  - `zebra_puzzle`: n=2, mean_score=1.000, exact_correct=2
| 20260829-135140 | version_base | claude-sonnet-5 | all | 200 | 0.865 | 0 | 662.6 | `results/20260829-135140__version_base__claude-sonnet-5.json` |
  - `spatial`: n=50, mean_score=0.820, exact_correct=41
  - `web_of_lies_v2`: n=50, mean_score=1.000, exact_correct=50
  - `zebra_puzzle`: n=100, mean_score=0.820, exact_correct=82
| 20260829-145722 | version_1 | claude-sonnet-5 | zebra_puzzle | 3 | 0.333 | 0 | 20.8 | `results/20260829-145722__version_1__claude-sonnet-5.json` |
  - `zebra_puzzle`: n=3, mean_score=0.333, exact_correct=1
| 20260829-145905 | version_1_formatted | claude-sonnet-5 | zebra_puzzle | 3 | 1.000 | 0 | 13.2 | `results/20260829-145905__version_1_formatted__claude-sonnet-5.json` |
  - `zebra_puzzle`: n=3, mean_score=1.000, exact_correct=3
| 20260829-150956 | version_1_formatted | claude-sonnet-5 | zebra_puzzle | 100 | 0.880 | 8 | 639.2 | `results/20260829-150956__version_1_formatted__claude-sonnet-5.json` |
  - `zebra_puzzle`: n=100, mean_score=0.880, exact_correct=88
| 20260829-151846 | version_base | claude-sonnet-5 | all | 12 | 0.667 | 0 | 234.3 | `results/20260829-151846__version_base__claude-sonnet-5.json` |
  - `zebra_puzzle`: n=12, mean_score=0.667, exact_correct=8
  - rerun of exactly the 12 `zebra_puzzle` questions that came back empty in the 20260829-135140 run (max_tokens=8000 wasn't enough), rerun here at max_tokens=16000

## Analysis: version_base vs version_1 on zebra_puzzle, budget-matched (2026-08-29)

Model: `claude-sonnet-5` both sides. Full task: 100 `zebra_puzzle` questions.

**Do not compare the raw 0.820 (version_base, max_tokens=8000) against 0.880
(version_1_formatted, max_tokens=16000) directly — different token budgets,
not an apples-to-apples comparison.** `claude-sonnet-5` defaults into extended
thinking, and on harder puzzles the thinking block can consume the entire
budget before any answer is written — this is a truncation artifact (empty
output, scored 0 by the real LiveBench scorer), not a wrong answer.

Budget-matched comparison (both capped near max_tokens=16000 — version_base's
88 originally-non-truncated questions ran at 8000, which didn't affect their
outcome since they weren't truncated there either; its 12 originally-empty
questions were rerun at 16000):

| version | raw score / 100 (truncation counted as 0) | still truncated even at 16000 | accuracy among *completed* answers |
|---|---|---|---|
| `version_base` (no scaffolding) | **90/100 = 90.0%** | 4/100 (levels 16, 20, 20, 16) | 90/96 = 93.75% |
| `version_1_formatted` (bracket schema + explicit instruction to follow the question's own requested output format in `conclusion.text`) | 88/100 = 88.0% | 8/100 (levels 17, 16, 16, 20, 20, 16, 14, and one pre-2024-11-25 "None"-level puzzle) | 88/92 = 95.7% |

**Conclusion:** the bracket-discipline schema (`version_1`) is genuinely a
little *more accurate per puzzle it actually finishes* (95.7% vs 93.75%), but
it fails to finish twice as often at the same token budget (8% vs 4%),
because it must quote every observation verbatim plus an id, a derivation
list, and (for hypotheses) a falsification path for every item — verbosity
that scales with puzzle complexity in a way free-form prose doesn't. At a
fixed, real-world token budget, `version_base` wins on the number that
actually matters (90% vs 88%) purely by failing less often. Both versions'
truncations cluster on the same hardest puzzle levels (16/20), confirming
this is a genuine difficulty×verbosity interaction, not noise.

**Bigger caveat, from re-reading `philosophy.md` directly: this entire
accuracy-vs-token-cost comparison, however carefully budget-matched, is not
actually a test of what `version_1`/agent_1 claims to be.** Three specific
mismatches between what we tested and what the design describes:

1. The design is explicitly **multi-round** — each round's `conclusion`
   becomes the next round's input `claim`, building an incremental ledger.
   `agent_1`'s schema instead asks for one flat JSON blob (all observations/
   assumptions/claims for the whole puzzle) in a single call. We tested a
   single-round collapse of a multi-round mechanism.
2. The **checker** (`CHECKER_SCHEMA`) is described as "the other half of what
   discipline has to mean... not optional hardening" -- but it isn't wired
   into zebra_puzzle at all (only into `return_policy`, and only as an
   advisory audit, not a correction loop). We tested the half of the design
   the author explicitly says is insufficient alone.
3. Per `philosophy.md`, v1's stated goal is explicitly **not** "improve the
   answer" -- it's "improve honesty": surfacing assumptions even at the cost
   of "the same, or even a slightly worse, final answer" counts as a v1 win.
   Grading zebra_puzzle exact-match accuracy measures a metric the design
   doc disclaims as the v1 target.
4. The higher token cost is not incidental variance -- it's structurally
   deterministic. Every observation needs an id + verbatim quote; every
   backed_claim needs an id + derived_from list + falsification_path; every
   hypothesis needs its own falsification path. That's fixed per-item
   scaffolding cost that scales with puzzle size regardless of reasoning
   quality, so `version_1` costing more tokens than `version_base` was never
   actually in question.

A test that actually matches the stated thesis would look like a **canary
test**: plant a subtle, known-wrong deduction into an otherwise-correct
reasoning chain and measure whether agent_1's bracket output (or the
checker) correctly classifies/flags it -- not whether it gets the final
zebra_puzzle answer right. That test has not been built yet.

Also note: `version_1` (unmodified, no format-compliance addendum) scored
0.333 on a 3-question smoke test purely from a format mismatch — its
`conclusion.text` is natural-language prose ("the journalist's hobby is
filmmaking...") rather than the raw `<solution>a, b, c, d</solution>` string
LiveBench's scorer requires, even when the underlying values were all
correct. `version_1_formatted` (defined in `agents_ext.py`, not in
karma_police's own `agents/`) fixes this with one added sentence telling the
model `conclusion.text` must follow the question's own requested format
verbatim. Any future version_1 evaluation should use `version_1_formatted`,
not raw `version_1`, or the score will be dominated by this confound rather
than reasoning quality.

