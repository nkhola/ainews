# FT-04 — Same Ticket, Five Ways

**Pre-registered 2026-08-22, before any run.** Sibling to FT-03, which asks what phrasing
costs. This one asks what phrasing *buys*: not whether the answer reads nicer, but whether
it runs.

## The folk practice under test

Every engineering team has a house belief about how to write a ticket, and every one of them
is enforced on vibes:

- "Write it as a user story." (Enforced by process.)
- "Write a proper spec, the model does better with structure." (Enforced by seniority.)
- "Just paste the Slack thread, it figures it out." (Enforced by deadline.)
- "Be precise and it'll be precise back." (Enforced by everybody, believed by everybody,
  measured by nobody.)

The prompt-engineering literature has a lot to say about *adding* information — few-shot
examples, chain of thought, constraints. It has much less to say about the case a working
engineer actually faces, which is **the same information in a different voice**. That is the
case here. Nothing is added between arms. Only the register changes.

## The claim

**Pre-registered bet:** register moves correctness, and the direction is the boring one.
Specifically:

- **`precise` is the best arm and `slack_chatty` is the worst**, with a gap of **at least 8
  percentage points** in overall pass rate.
- `formal_spec` lands within 3pp of `precise`. Structure is not the active ingredient;
  unambiguity is, and both arms have it.
- `user_story` and `terse_ticket` land in between.
- **The secondary bet, which is the one I actually care about:** even with a real gap between
  styles, the **flip rate exceeds 25%** — that is, in more than a quarter of task-by-style
  cells, the same prompt both passes and fails across its 30 trials. If that holds, then
  resampling the identical prompt moves your outcome more than rewriting it does, and the
  practical advice is "run it twice", not "write it better".

**What would surprise me:**

- All five styles inside 3pp of each other. That would say the model recovers the same intent
  from any competent English rendering of it, and every ticket-format argument your team has
  ever had was about human readers, not the model.
- `slack_chatty` winning. Casual register carries a lot of redundancy; it is not obviously
  worse and I might be wrong about it.
- A `signature_ok` split — a style that produces working logic behind the wrong interface.
  That is recorded separately from `pass` precisely so it can be seen. I expect it to be flat
  across arms; if it is not, register is affecting the contract, not the algorithm, which is
  a different and more alarming finding.
- A task-by-style interaction: one style that is best on the easy tasks and worst on the hard
  ones. n=30 per cell is thin for detecting this, and I will say so rather than over-read it.

## Design

Six base tasks. Five meaning-preserving rewrites of each, written by hand. **Every rewrite
names the same function with the same signature, describes the same behaviour, and states
the same edge cases.** Nothing is added or removed between arms; only register and structure
differ. This constraint is the whole experiment — if the `precise` arm quietly carried extra
information, the result would be "more information helps", which nobody needs a rig to learn.

- **Conditions (5):** `terse_ticket` (bug-report shorthand, fragments, no pleasantries),
  `formal_spec` (numbered shall-statements), `slack_chatty` (lowercase, filler words, "quick
  favour"), `user_story` (As a / I want / so that, plus acceptance criteria), `precise`
  (plain, unambiguous prose).
- **Tasks (6):** `merge_intervals`, `roman_to_int`, `chunk_list`, `parse_semver`,
  `rle_encode`, `balanced_brackets`. Chosen for a spread of difficulty and for having a
  single unambiguous correct behaviour that assertions can pin down. Three of them
  (`merge_intervals`, `rle_encode`, `balanced_brackets`) are shared verbatim with FT-08.
- **Matrix:** 6 tasks x 5 conditions = 30 cells, n = 30 trials per cell, 900 calls.
- **Model:** `gemini-2.5-flash` on Vertex, thinking disabled (`thinkingBudget: 0`),
  `maxOutputTokens` 2400, temperature at API default.
- **System instruction:** identical in every arm — "You are a Python code generator. Reply
  with a single fenced Python code block containing the complete function and nothing else."
  It fixes the output format so extraction is reliable. It is not part of the manipulation.
- **Budget:** $3.00 hard ceiling enforced in-process. Planning estimate ~$0.85.

### Verifier (pre-declared, mechanical)

No model grades anything. Correctness is decided by **running the code**:

1. **Extract.** Pull fenced blocks with a regex. Take the first block that `ast.parse`s and
   contains a `FunctionDef` with the target name; else the longest fenced block; else salvage
   an unfenced code region by starting at the first `def`/`class`/`import`/`from`/`@` line and
   trimming lines off the end until it parses; else the raw text.
2. **Execute.** Run the extracted code in a child interpreter (`python -I`) via `exec()` with
   a small builtins dictionary, an import denylist (filesystem, process, network,
   serialization; anything starting with `_`), and `__name__` set to `__sandbox__` so an
   `if __name__ == "__main__"` demo block never fires.
3. **Assert.** Call the function against a fixed, hand-checked assertion set — 6 or 7
   input/expected pairs per task, including the empty-input case. An expected value of
   `{"__raises__": "ValueError"}` passes only if that exact exception type is raised.
4. **Report** `{"pass": all assertions passed, "n_passed": int, "n_asserts": int,
   "signature_ok": bool}`, plus `chars` and `fenced`.

Details that matter and are therefore fixed in advance:

- `signature_ok` means a callable of the exact expected name exists and
  `inspect.signature(...).bind()` accepts the first assertion's arguments.
- Comparison normalises tuples to lists and materialises generators, so a correct algorithm
  returning the wrong container still passes. The experiment is about whether rewording
  breaks the *logic*; container pedantry would be noise.
- Booleans are compared strictly, so returning `1` for `True` fails.
- Each call gets a 2-second `SIGALRM`; the whole child gets a 25-second wall clock. **A
  candidate that never returns is scored `pass: False`** — an infinite loop is a wrong
  answer, not a broken measurement.
- Empty or non-string output returns `pass: None` and is excluded, not counted as a failure.
- Truncated generations (`finishReason` other than `STOP`) are recorded and excluded by the
  harness before `verify` is ever called.

Every assertion set was checked against a reference implementation before pre-registration,
so a wrong expected value cannot silently depress a whole task.

**The restricted builtins dictionary is hygiene, not a security boundary** — `getattr` alone
makes it escapable. The real containment is that this is a short-lived, isolated child
process running small benign functions. Stated plainly here so nobody later mistakes it for a
sandbox.

## Honest framing

Weekend-scale. One model, one provider, one day, six small Python functions, English only,
temperature at the API default, five rewrites written by one person who knew what the
experiment was testing. That last point is the sharpest limitation: **I wrote all five
wordings, and I have a prior about which should win.** I cannot rule out having written the
`precise` arm slightly better than the others in ways I did not intend. The mitigation is
that all five are committed here, before any run, so anyone can read them and judge whether
they really are meaning-preserving.

Power is thin, and pre-declaring that matters more than pretending otherwise. At n=180 per
condition, a Wilson interval around p≈0.85 is roughly ±5pp, so only gaps above about 10pp
will separate cleanly. **Decision rule, fixed in advance:** if the best and worst arms'
intervals overlap, the full matrix is re-run at n=40 and **both** runs are reported. The
first run is never replaced or dropped.

This does not generalise to other model families, to long-context tickets, to multi-file
work, or to tickets whose rewrites are not actually meaning-preserving — which, in real life,
most rewrites are not.

## Declared in advance

Every run reported. No arm dropped for looking bad. Wilson intervals, never bare percentages,
and the flip rate published alongside every pass rate. If all five styles land on top of each
other, that publishes at full length as "your ticket format is for the humans" — which is a
useful result, a short post, and it goes out anyway.
