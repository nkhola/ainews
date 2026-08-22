# FT-08 — Filler Tokens

**Pre-registered 2026-08-22, before any run.** FT-03 and FT-04 vary how the request is
*worded*. This one leaves the request alone and varies how much meaningless material sits in
front of it.

## The folk practice under test

Two beliefs that point in opposite directions, which is why this is worth a rig:

1. **"Junk in the context degrades the answer."** The practitioner instinct, and the reason
   people spend real effort pruning RAG chunks, trimming system prompts, and stripping
   boilerplate before it reaches the model. Mostly asserted, occasionally measured on
   retrieval tasks, rarely measured on the thing engineers actually do all day, which is ask
   for code.
2. **"Meaningless tokens are free computation."** The filler-token / pause-token line of
   work argues the opposite: that a model given extra tokens to emit or attend over — even
   semantically empty ones, famously strings of dots — can use the additional forward passes
   as scratch space, improving performance on some tasks. If that transfers here, padding
   should *help*, not hurt.

Both cannot be right in the same regime. Nobody I can find has run the crossing on a
production Flash model with mechanical grading and published every cell.

## The claim

**Pre-registered bet: filler is inert until it is large, and then it is the *kind* of filler
that hurts, not the amount.** Specifically:

- `none`, `dots_50`, `lorem_50`, `dots_200` and `lorem_200` all land **within 4 percentage
  points** of each other on pass rate. Small amounts of junk cost nothing but input tokens.
- **`dots_800` drops at least 5pp below `none`.** Eight hundred degenerate repeated tokens is
  a distribution the model has little reason to have seen in front of a coding request, and I
  expect it to cost something.
- **`lorem_800` stays within 4pp of `none`.** Grammatical, contentless English is a shape the
  model has seen constantly. I expect it to be almost free.
- Therefore: **at 800 units, kind matters more than amount** — the `dots_800` vs `lorem_800`
  gap exceeds the `lorem_800` vs `none` gap.
- No arm exceeds `none` by more than its interval. **I am betting against the free-computation
  effect showing up here**, because thinking is disabled and the filler sits in the input, not
  the output — the pause-token result is about tokens the model *emits*, and this is not that.

**What would surprise me:**

- **Any filler arm beating `none` outside its Wilson interval.** That would be the
  interesting result in the whole batch, and it gets the loudest possible write-up including
  an explicit note that I bet against it.
- `dots_50` being enough to degrade. If fifty tokens of noise measurably hurt, the practical
  advice about context hygiene gets much more aggressive than anyone currently practises.
- The model *commenting on* the filler — asking what the dots mean, or refusing. `fenced` and
  `chars` are recorded per run so this shows up as format drift rather than hiding inside the
  pass rate.
- `lorem_800` hurting more than `dots_800`, i.e. plausible-looking irrelevant prose being
  worse than obvious noise. That would be a genuinely useful finding for anyone assembling
  RAG context, and the opposite of my bet.

## Design

The real request is **byte-identical in every arm**, including the control. The filler is
prepended to the same user turn, separated by a blank line, with **no label and no
explanation** — because real padding does not come labelled, and labelling it would test
something else.

- **Conditions (7):** `none` (control) crossed with kind x amount —
  `dots_50`, `dots_200`, `dots_800`, `lorem_50`, `lorem_200`, `lorem_800`.
  - `dots` = *n* space-separated periods.
  - `lorem` = *n* words drawn deterministically from a fixed pool of twelve grammatical,
    contentless sentences that assert nothing, constrain nothing, and mention no task.
- **Tasks (6):** `merge_intervals`, `rle_encode`, `balanced_brackets` — shared verbatim with
  FT-04, same wording and same assertions, so the two experiments can be read against each
  other — plus `spiral_order`, `evaluate_rpn` and `longest_common_prefix`, added because the
  first three risk sitting near the ceiling and a ceiling cannot show degradation.
- **Matrix:** 6 tasks x 7 conditions = 42 cells, n = 30 trials per cell, 1,260 calls.
- **Model:** `gemini-2.5-flash` on Vertex, thinking disabled (`thinkingBudget: 0`),
  `maxOutputTokens` 2400, temperature at API default.
- **System instruction:** identical in every arm — "You are a Python code generator. Reply
  with a single fenced Python code block containing the complete function and nothing else."
- **Budget:** $3.00 hard ceiling enforced in-process. Planning estimate ~$1.30.

**Filler amounts are nominal units, not exact token counts.** A space-separated dot and an
English word do not tokenise identically, so `dots_200` and `lorem_200` are not matched on
tokens by construction. The harness records the real `promptTokenCount` on every call, so the
actual input size of each arm is **measured and published**, not assumed. Any claim about
"amount" in the write-up will be made against measured tokens, not against the label in the
condition id. The condition ids are handles, not data.

### Verifier (pre-declared, mechanical)

Identical to FT-04's, byte-for-byte in the sandbox block, and duplicated into this directory
rather than shared because the harness contract says an `exp.py` imports nothing from the
harness. No model grades anything:

1. **Extract.** First fenced block that `ast.parse`s and defines the target function; else
   the longest fenced block; else salvage an unfenced code region by starting at the first
   `def`/`class`/`import`/`from`/`@` line and trimming lines off the end until it parses;
   else the raw text.
2. **Execute.** `exec()` in a child interpreter (`python -I`) with a small builtins
   dictionary, an import denylist (filesystem, process, network, serialization; anything
   starting with `_`), and `__name__` set to `__sandbox__`.
3. **Assert.** 6 or 7 hand-checked input/expected pairs per task, including the empty-input
   case. Tuples normalise to lists and generators are materialised, so a correct algorithm in
   the wrong container still passes; booleans are compared strictly.
4. **Report** `{"pass": all assertions passed, "n_passed": int, "n_asserts": int,
   "signature_ok": bool}`, plus `chars` and `fenced`.

Each call gets a 2-second `SIGALRM`; the whole child gets a 25-second wall clock, and a
candidate that never returns is scored `pass: False` — an infinite loop is a wrong answer.
Empty or non-string output returns `pass: None` and is excluded rather than counted as a
failure. Truncated generations are excluded by the harness before `verify` runs.

Every assertion set was checked against a reference implementation before pre-registration.
**The restricted builtins dictionary is hygiene, not a security boundary** — `getattr` alone
makes it escapable; the real containment is a short-lived isolated child process running
small benign functions.

## Honest framing

Weekend-scale. One model, one provider, one day, six small Python functions, English only,
temperature at the API default, filler at the front of the user turn only. It does not test
filler in the system prompt, filler *after* the request, filler interleaved with real
content, or the long-context regime where 800 tokens is a rounding error — 800 units in front
of a 60-word request is roughly a 10x prompt, which is the regime where an effect is most
likely to be visible at all, and that choice is a thumb on the scale in favour of finding one.

This is also not a test of the filler-token literature. That work is about tokens the model
**generates** as scratch space, on tasks chosen to need serial computation, usually with
trained models. This is about tokens sitting in the input of a production model on ordinary
coding requests with thinking switched off. If the results disagree, the paper is not wrong;
they are different experiments, and the write-up will say so rather than claiming a
refutation.

Two known confounds, declared up front: `dots` and `lorem` differ in tokens per unit as
described above, and the two filler kinds differ in more than "meaninglessness" — one is
degenerate repetition, the other is fluent English. The comparison that is clean is each
kind against `none` at matched kind; the cross-kind comparison is suggestive at best.

## Declared in advance

Every run reported. No arm dropped for looking bad. Wilson intervals, never bare percentages,
flip rate published alongside every pass rate, and measured input tokens published per arm
next to the nominal unit counts. If filler turns out to be completely inert — which is the
single most likely outcome — that publishes at full length as "stop pruning your prompts for
quality; prune them for cost", and the cost numbers will be right there to prune against.
