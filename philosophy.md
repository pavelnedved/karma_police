# karma_police

## Origin

Named after the Radiohead song — a policing entity that shows up for specific,
almost petty infractions, sung with irony about how arbitrary and self-appointed
the police are. That irony is load-bearing, not decorative: the checker this
project builds is not an infallible judge either. It is a second rubber stamp,
just one that isn't complicit in finishing the task.

## The problem

LLM output, especially over a multi-step reasoning chain, is a compressed
rendering of some internal process. The chain-of-thought text is not the
process itself — it's a plausible narration of it, and the narration can
diverge from what actually produced the answer. This gets worse, not better,
as the reasoning becomes more fluent: the more logical an LLM's conclusion
*sounds*, the harder it becomes for a human to tell when it's wrong, even
when the error is, in principle, obvious. Fluency and correctness are
different axes, and humans systematically conflate them.

The standard human countermeasure is to add more conditions to the prompt —
"don't do this, do that instead." This is compressed knowledge (a human's
mental model, rendered as text) patching a different compressed
representation (the model's opaque internal process). It doesn't fix why the
model reached the wrong conclusion; it adds another surface constraint on top
of a process nobody can inspect.

This countermeasure also has a hidden structural ceiling. It only works if
the injected knowledge is unambiguous and current, which in practice requires
near-perfect, permanently up-to-date documentation — something not even the
best-resourced organizations actually have. And even granting perfect
documentation, docs answer "what do I do given a known scenario," not "what
do I do when I hit a combination of scenarios nobody wrote down" — which is
close to the actual problem statement behind most of Stack Overflow.

The deeper issue: prompt patches are additive, but failure modes compose
multiplicatively. Every new condition doesn't just cover one new edge case —
it creates an interaction term with every condition already in the prompt,
and nobody wrote down what happens when two patches fire at once, because
neither patch's author was thinking about the other's existence. This is why
patching a prompt indefinitely reads as *creating chaos* rather than
converging on correctness: the space of condition-conjunctions grows
combinatorially, the patch budget grows linearly. This is not a new failure —
it's the frame problem (1970s AI: you can't finitely specify everything that
does or doesn't change when a new fact is added) and it's why 1980s
rule-based expert systems went brittle and collapsed under their own rule
count. It's also just Michael Polanyi's tacit-knowledge problem in a prompt-
engineering costume: "we know more than we can tell," so a manual can only
ever encode the tellable part, and the gap between tellable and
needed-in-the-moment is where every real edge case lives.

## The reframe

Prompting is the only channel available (short of training/fine-tuning), and
that's not the mistake. The mistake is treating "feed it more compressed
knowledge to patch each mistake" as the *only strategy available over that
channel*. It's one strategy, and it's specifically the worst-scaling one,
because it's a priori: it tries to specify correctness before the failure
exists, for a process that is bad at revealing when it's about to fail.

Strategies that don't share that flaw all move the intervention from before
generation to after generation, but before commitment — a posteriori
checking instead of a priori specification:

- **Verification over specification.** Let the model reason freely, then
  check the conclusion against something checkable. Verifying is a different
  and usually easier operation than generating correctly in the first place.
- **Externalize onto a decidable substrate.** Move claims out of "does this
  sound right" prose into things with an actual truth value outside
  linguistic plausibility — code that runs, a citation that exists or
  doesn't.
- **Structural redundancy instead of rule density.** Independent reasoning
  attempts that don't share the same blind spot, cross-checked against each
  other, rather than one chain patched with more rules.
- **Adversarial framing over compliance framing.** "What would have to be
  true for this to be wrong" asks for a different cognitive operation than
  "don't do X, do Y" — the latter is just the human supplying the answer key
  in advance.

## The shrink

Shrink the problem to: how do we make a sound conclusion based on external
knowledge? One path is "build a framework for perfect documentation" — this
project explicitly does not take that path, because perfect, permanently
current documentation is not achievable and chasing it is asymptotic by
construction.

The path this project tests instead: assume the documentation is permanently
incomplete, ambiguous, and stale, and build a process that stays trustworthy
*given* that, rather than one that only works once the gap is closed. Success
isn't "coverage approaches 100%." Success is: the system knows which regime
a given query is in — inside coverage, at the edge of coverage, or outside it
entirely — and behaves differently in each, instead of blending all three
into equally fluent, equally confident prose. The actual mechanism of the
hallucination this project is aimed at is exactly that blending: interpolating
across a gap in the source and presenting the interpolation in the same voice
as a direct retrieval.

## The core bet

**The LLM doesn't lack logic. It lacks discipline of logic.** The project is
the discipline layer — nothing more claimed than that.

This isn't asserted from nothing — it's the same effect that already makes
chain-of-thought prompting outperform "just answer": the same weights produce
more accurate output when forced to externalize intermediate steps instead of
jumping straight to a conclusion. That's existing evidence the capability was
latent, not absent.

"Discipline" splits into two parts that need to be named separately:

1. **Format discipline** — actually stopping to externalize structure
   (observation / definition / assumption / claim) instead of skipping to a
   conclusion. Cheap to elicit: just require the structure every round.
2. **Classification honesty** — correctly sorting a given piece of
   information into the right bucket once forced to choose. This can fail
   even under perfect format compliance: a model can dutifully fill in every
   bracket every round while still confidently mislabeling an inference as an
   "observation."

Format discipline is the scaffold. Classification honesty is the residual gap
that scaffold alone doesn't close — which is why the design doesn't stop at
"make the model output the bracket list" and adds an independent, task-blind
checker. The checker isn't optional hardening bolted onto the thesis; it's
the other half of what "discipline" has to mean, since self-discipline alone
can still be dishonest while being perfectly well-formatted.

## The mechanism: a bracket state machine

Every round, the worker model is required to sort what it's working with into
explicit, typed buckets rather than producing undifferentiated prose.

**Inputs, per round:**

1. **Observation** — only what is literally seen. Must be precise. Two
   observations of "the same thing" are allowed to conflict, but the conflict
   must be resolved by making the descriptions precise enough to be
   distinguishable — not papered over.
2. **Definition** — a description of a word. A definition must not be
   directly actionable or able to derive a claim on its own; if it can, it
   was smuggling in a claim, not defining a term. Conflicting definitions
   require an explicit hard resolution, not silent pick-one.
3. **Assumption** — what lets reasoning move forward without evaluating
   everything in the world. Assumptions are not forbidden — they're required
   to be explicit. An assumption fills the gap between an action's result and
   its input, used only when observation + definition can't derive the next
   step directly but progress is still wanted.
4. **Backed claim** — derived from observation + definition + assumption via
   an explicit logic chain, and must carry an explicit falsification path:
   what would show this is wrong.
5. **Unverified claim** — a claim not yet verified, or verified false.

**Outputs, per round:**

1. **Hypothesis** — a forward-looking assumption: "we're moving ahead, but
   here are the cases." Every hypothesis carries a falsification path. If it
   can be falsified easily, it should be — and dumped or moved to unverified
   if it fails. If it can't be falsified easily and the reasoning wants to
   proceed anyway, it's promoted into the assumption bracket for the next
   round.
2. **Conclusion** — like a claim, but the output of a completed round of
   logic; also splits into backed / unverified. A conclusion converts
   directly into a claim as input to the next round.

This produces a persistent, inspectable ledger across a multi-round chain,
instead of an undifferentiated wall of fluent prose. That's the direct answer
to the opening complaint: a human (or a checker) no longer has to parse tone
and coherence to find the weak link — they can filter for `assumption`,
`hypothesis`, or `unverified claim` and go straight to the exact joints where
a leap happened.

## The checker

A second agent observes each round's new bucket items and the delta from the
previous round, and asks whether the addition is logically sound — is the tag
honest, does this follow from what's already there, is there a real
falsification path. Critically, **the checker does not know the overall
task.** It cannot rationalize toward finishing something it isn't aware
exists. This is what gives the falsification step an actual forcing
function: nothing in the checker's context rewards it for waving a shaky
assumption through to keep momentum toward a goal, because it has no
visibility into what the goal is.

This isn't a free win, and three problems stay open by design:

1. **Local validity is not global soundness.** A checker blind to the task
   can verify "does this follow" but not "is this chain heading anywhere
   relevant." That trade is deliberate for v1 — global-coherence checking
   would require task-awareness, which reintroduces the exact conflict of
   interest the blind checker exists to avoid. Left out of scope for now.
2. **A flag needs a defined effect.** If the worker can just re-argue past a
   flag, the checker adds a debate round, not a constraint. For v1 the
   checker's output does not need to be binding — see below.
3. **The checker itself needs calibration, not blind trust.** Removing the
   "finish the task" incentive removes one bias, not all bias — the checker
   could still drift toward over- or under-flagging. This needs a canary
   test: seed a bucket with a known-planted bad item (an assumption
   disguised as an observation, a claim with no real falsification path) and
   measure whether it's caught at a known rate, independent of any real task.

## What v1 actually optimizes for

The first-round goal is explicitly **not** "improve the answer." It's
**"improve honesty"**: for the same, or even a slightly worse, final answer,
surface the assumptions the model made during the session — even a majority,
not all, is already a win in v1 — so a human has a checklist to review
instead of having to re-derive the entire chain from scratch to find the
hidden leap.

This reframes the checker from a gate into an annotator: its verdicts don't
need to be binding, because it isn't blocking the worker's progress, it's
producing a byproduct artifact. That sidesteps the "does a flag actually stop
anything" problem for now — v1 doesn't need enforcement, it needs disclosure.

This also sets the actual metric, and it isn't plain accuracy:

- **Recall of true assumptions, weighted heavily against false negatives.**
  Missing a real assumption defeats the whole purpose — it's the same silent
  failure as today. Over-flagging costs a reviewer a few extra seconds per
  item, which is cheap by comparison.
- **But not recall at any cost.** If the checklist ends up as long as the
  original reasoning chain, nothing was saved — it's the same wall of text,
  reformatted. The real constraint is recall of true assumptions, subject to
  the checklist staying meaningfully shorter and faster to review than
  redoing the derivation by hand.

Evaluating this requires cases with a known ground-truth set of
assumptions/leaps ahead of time — either seeded synthetically (plant a known
assumption, check whether it surfaces) or established by doing the expensive
manual re-derivation once on real sessions and using that as the answer key.

## Open questions carried forward

- What is the actual "hard resolution" procedure for conflicting definitions
  or conflicting observations? This is where the original paradox (doc says
  1, 2, 3, and x — what do you do with 1-and-x together) concretely lives,
  and it isn't specified yet. Left unresolved risks just relabeling the
  original problem one level down the stack.
- Is a definition's "not directly actionable" property checkable
  mechanically — e.g., does the claim still survive if the definition is
  removed and everything else is held constant?
- Should "observation" require a mechanical, non-LLM-judged admission test
  (a literal traceable span in the provided source), rather than being
  accepted on the model's own say-so? Without this, "observation" risks
  becoming the least-scrutinized way to smuggle in a claim, since the label
  itself is a trust signal.
- Does a global, task-aware coherence pass get added later as a distinct,
  separately-scoped role, once the blind local checker is validated on its
  own terms?
