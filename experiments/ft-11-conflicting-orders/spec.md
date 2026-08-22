# FT-11 — Conflicting Orders

**Pre-registered 2026-08-22, before any run.** FT-01 asked whether repeating an instruction
helps. FT-02 asked whether its position matters. Both assumed the instruction set was
coherent. Real system prompts are not coherent — they are sediment, written by four people
over eighteen months, and they contradict themselves.

## The claim under test

When two rules in the same prompt cannot both be satisfied, something decides which one the
model follows. The candidates are:

- **Primacy** — the rule stated first wins.
- **Recency** — the rule nearest the end wins, which is the folk belief and the reason
  people append their real requirements to the bottom of a prompt.
- **Repetition** — the rule stated twice wins, which is what FT-01 would predict if
  repetition works the way it appeared to.

These make different predictions and only one arrangement can be right, so the experiment is
worth running.

## The bet

**Pre-registered bet: recency wins, and repetition beats position.** Concretely:

1. Across matched pairs, the rule stated **last** is obeyed more often than the rule stated
   first — at least a 15-point margin pooled across the three conflict types.
2. `a_twice_b_once` and `b_twice_a_once` move compliance further than any pure ordering arm,
   so the doubled rule wins by more than the last-placed rule does.
3. The split arms (`a_top_b_bottom`, `b_top_a_bottom`) show a **larger** ordering effect
   than the adjacent arms, because a pair sitting side by side reads as one visible
   contradiction the model resolves deliberately, while a split pair reads as two separate
   orders.

**What would surprise me:**

- Primacy winning. That would put every "and remember, the important part is…" footer in the
  bin.
- The adjacent arms producing a large `neither` or `both_impossible` rate — the model
  noticing the contradiction and refusing, or engineering its way around it. Any visible
  contradiction-detection at all would be the most interesting result available here.
- All six arms landing inside each other's intervals. Then which rule wins is a coin flip,
  which is a worse finding for anyone maintaining a long prompt than either position rule.

## Design

Three conflict pairs, two tasks each, six arrangements. Content inside a pair is fixed; only
arrangement moves.

| Pair | Rule A (`pass` = A obeyed) | Rule B |
|---|---|---|
| `quotes` | only single-quoted strings | only double-quoted strings |
| `comments` | no comments, no docstrings | comment each step, docstring every function |
| `length` | at most five lines of code | validate every argument, raise per failure mode |

**A is a labelling convention, not a verdict.** Neither rule is correct. `pass` means A was
obeyed, and the interesting column is `obeyed`.

- **Arms (6):** `ab_adjacent`, `ba_adjacent` (pair side by side at the top, order flipped);
  `a_top_b_bottom`, `b_top_a_bottom` (pair split across the block); `a_twice_b_once`,
  `b_twice_a_once` (one rule doubled, at top and bottom, other rule mid-block).
- Every arm emits exactly **10 instruction lines**. The adjacent and split arms are 2 rules
  plus 8 fixed neutral filler lines. The doubled arms trade one filler line for the extra
  copy: 3 rules plus 7 filler. The doubled arms are therefore repetition *and* bookending at
  once, which is why the split arms are the matched single-copy controls for them.
- **Tasks (6):** `status_label`, `slugify` (quotes); `binary_search`, `merge_intervals`
  (comments); `safe_divide`, `read_port` (length). 6 × 6 = **36 cells**.
- The quote tasks are worded so string literals are unavoidable, and the length tasks are
  worded so at least two failure modes exist. Otherwise a rule could be satisfied vacuously.
- **n:** 30 trials per cell, 1,080 calls.
- **Model:** `gemini-2.5-flash` on Vertex, thinking disabled, temperature at API default.

### Verifier (pre-declared, mechanical)

`tokenize` and `ast`, never a model's opinion.

- **quotes** — count STRING tokens by opening quote. A obeyed: at least one single-quoted
  string and zero double-quoted. B obeyed: the reverse. Triple-quoted strings are counted in
  `n_triple` and excluded from both, since docstring quoting is what the comments pair is
  for. This is a deliberate refinement of the FT-01/FT-02 verifier, which folded docstrings
  into the double-quote count; noted here so the numbers are not read as directly comparable.
- **comments** — COMMENT tokens plus `ast.get_docstring` on every module, function and
  class node. A obeyed: zero comments and zero docstrings. B obeyed: its full demand, at
  least two comments and at least one docstring. Half-compliance lands in `neither` on
  purpose.
- **length** — non-blank, non-comment-only lines of extracted code, and `ast.Raise` nodes.
  A obeyed: five lines or fewer. B obeyed: two or more raises.

`obeyed` is one of `A`, `B`, `neither`, or `both_impossible`. The last means the model
satisfied both rules, i.e. the conflict was escapable for that instance — five lines with two
raises is unlikely but not impossible, and if it happens it is data, not a bug. Output that
does not parse is recorded with `parsed: false` and `pass: null`, never counted either way.
Raw signals (`n_single`, `n_double`, `n_comments`, `n_docstrings`, `n_code_lines`,
`n_raises`) are written on every run so the pass/fail line can be moved after the fact
without re-running anything.

## Honest framing

Weekend scale. One model, `gemini-2.5-flash`, not state of the art. Three conflict types is
a thin sample of the space, and the three are not equally sharp: the quote conflict is
crisp and binary, while the length-versus-error-handling conflict has a middle the model can
try to occupy. Expect the three to disagree, and expect the pooled number to hide that. This
measures one model's arbitration on short Python tasks, not a general law about instruction
priority.

## Declared in advance

Every run reported, all six arms and all three conflict types, broken out separately as well
as pooled. Wilson intervals, never bare percentages. Truncation recorded via `finishReason`
and excluded. If the answer turns out to be "it depends on the conflict, with no consistent
ordering effect", that publishes at full length and the bet stands where it is.
