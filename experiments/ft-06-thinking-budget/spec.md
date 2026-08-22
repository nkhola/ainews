# FT-06 — Thinking Budget

**Pre-registered 2026-08-22, before any run.** Follows FT-01 ("Say It Four Times") and
FT-02 ("Top and Bottom Doesn't Work"), which both varied the prompt. This one leaves the
prompt alone and varies the one knob everybody now reaches for instead.

## The folk practice under test

"Give it more thinking budget." Reasoning tokens are the current default answer to a wrong
answer, and the budget dial is the easiest thing in the API to turn up. It is also the
most expensive: thinking tokens are billed at the output rate, so a 8,192-token budget on
`gemini-2.5-flash` costs up to 2 cents a call against a visible answer worth a fifth of a
cent. Nobody I have asked can say what they get back for that.

The two competing stories:

1. **Thinking is compute, and compute is capability.** More budget, better answers, across
   the board.
2. **Thinking is search, and search only helps when there is something to search for.**
   On a task the model already solves in one pass, the budget is burned and nothing
   changes. It only pays where the model would otherwise have to guess.

## The claim

**Pre-registered bet:** thinking budget buys nothing below the hard band.

Precisely, three predictions, all falsifiable:

- **Easy tasks:** all five arms land inside each other's Wilson intervals. No arm beats
  `think_0` by more than 5 percentage points.
- **Medium tasks:** `think_2048` beats `think_0` by somewhere between 0 and 10 points —
  a real but small gain, and probably not worth 8x the token bill.
- **Hard tasks:** `think_2048` beats `think_0` by at least 15 points, and the curve
  plateaus after it — `think_8192` does not beat `think_2048` by more than 5 points on any
  difficulty band.

Stated as one line for the post: **below the hard band, the budget is a tax, not an
investment.**

**What would surprise me:**

- Thinking helping on the easy tasks. That would mean the model is not actually solving
  three-line string problems in one pass, which is a more interesting finding than the
  experiment I set out to run.
- Thinking *hurting* anywhere — a real inverted U, where `think_8192` scores below
  `think_512` because the model talks itself out of a correct first answer. I would report
  it loudly, and I would want it replicated before believing it.
- No separation even on the hard tasks. That would mean the hard tasks are either too hard
  (floor effect, everything fails) or too memorised (ceiling effect, everything passes),
  and the difficulty ladder needs rebuilding before the question can be asked at all.

## Design

The prompt is byte-identical in every arm. The task set is identical. The model, the
sampling settings and the output cap are identical. `thinkingBudget` is the only thing that
moves.

- **Conditions (5):** `think_0`, `think_128`, `think_512`, `think_2048`, `think_8192` —
  `thinkingConfig.thinkingBudget` set to 0, 128, 512, 2,048 and 8,192.
- **Tasks (8), graded in advance, not after seeing the results:**
  - *easy* (string and list manipulation, no algorithm): `reverse_words`,
    `dedupe_preserve_order`, `char_frequency`
  - *medium* (needs an algorithm or careful edge cases): `merge_intervals`,
    `parse_duration`, `flatten_dict`
  - *hard* (dynamic programming; a recursive-descent parser with a sign edge case):
    `max_profit_k`, `evaluate_expression`
- **n:** 25 trials per cell. 8 x 5 x 25 = **1,000 calls**. Projection is about $3.80; the
  module caps at $6.00 and the harness aborts the matrix rather than trusting a GCP alert.
  The `think_8192` arm alone is roughly two thirds of the bill, which is the whole point.
- **Model:** `gemini-2.5-flash` on Vertex, temperature at API default.
- **Job order:** shuffled by the harness, so provider-side drift cannot align with an arm.

### The trap this rig is built to avoid

**Thinking tokens are billed against `maxOutputTokens`.** Set the cap to 8,192 and the
budget to 8,192 and the visible answer has no room left; the generation truncates and the
arm scores zero. That reads as "big budgets are worse" when it is really "the cap was too
small", and it is the single easiest way to publish a wrong number here.

So: **`maxOutputTokens` is 16,384**, the largest budget plus 8,192 tokens of headroom for
an answer that needs about 300. Belt and braces, `finishReason` is recorded on every call
and truncated generations are excluded rather than counted as failures. If the truncation
count is not near zero in the `think_8192` arm, the result is void and the cap goes up.

### Verifier, declared in advance

Mechanical end to end. No model grades anything.

1. Extract the fenced block that defines the target function, by regex. Fences are matched
   at line start with any info string, so a closing fence cannot be mistaken for an opener.
2. `exec()` it in a restricted namespace: a fixed builtins allowlist, an import allowlist
   of pure-stdlib modules, `print` neutered, and `__name__` set to something other than
   `__main__` so an appended demo block does not run.
3. Call the function against a fixed list of assertions written before any run — 6 to 8
   per task, including the empty case and the edge case the spec calls out.
4. Record `{"pass": all assertions passed, "n_passed", "n_asserts", "difficulty"}`.

`eval`, `exec`, `compile` and `open` are absent from the sandbox builtins. That is not
security theatre; it is what mechanically enforces "implement the parsing yourself" on
`evaluate_expression`, where a solution that reaches for `eval()` raises `NameError` and
scores zero.

A wrong dynamic-programming answer is very often an infinite loop, so execution runs under
a per-thread wall-clock guard: 5s to define the module, 3s per assertion, 8s for the whole
assertion run. `verify()` catches everything and returns `{"pass": None, "error": ...}`
rather than raising; a crashed verifier must never be silently scored as a failure.

Every reference solution was run through the verifier before pre-registration and scores
full marks, so a failure in the data is the model's, not the assertion list's.

### What gets reported

Pass rate by arm and by difficulty band, with Wilson intervals, never bare percentages.
Plus the number this experiment exists for: **mean `thought_tokens` per call and dollars
per correct answer, by arm and band.** The harness records `thought_tokens` separately from
`out_tokens`, so cost per correct answer falls straight out of the raw records. An arm that
wins on pass rate and loses on cost per correct answer is a loss, and will be written up
that way.

## Honest framing

Weekend scale. One model family, one model, one language, eight problems, 1,000 calls. This
is not a benchmark and it is not state of the art. The hard tasks are hard for a Flash-class
model, not hard in any absolute sense, and two of them are recognisable enough that
memorisation is a live confound — which is exactly why the easy/medium/hard split is the
unit of analysis rather than a single headline number.

FT-09 ("When Pro Pays") runs the same eight tasks across a price ladder of models with
thinking pinned near zero. Between them the two experiments factorise the two axes people
actually trade off: pay for thinking, or pay for a better model. FT-06's `think_0` arm and
FT-09's `gemini-2.5-flash` arm are the same cell run on different days, which is a free
replication check and will be reported whether or not it agrees.

## Declared in advance

Every run reported. No arm dropped for looking bad. Truncated generations reported
separately and never counted as passes. If the budget turns out to buy nothing anywhere,
including on the hard tasks, that publishes at full length under its own headline. The
predictions above stay standing with a post-hoc note if they are wrong; they are never
edited after seeing data.
