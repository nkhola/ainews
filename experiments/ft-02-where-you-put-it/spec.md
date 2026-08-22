# FT-02 — Where You Put It

**Pre-registered 2026-08-19, before any run.** Follows FT-01 ("Say It Four Times"), which
found that stacking a constraint up to four times lifts compliance from 74% to 97% and then
plateaus.

## The folk practice under test

Two of them, actually, and they contradict each other:

1. "Put the important instruction at the top **and** the bottom." Extremely common advice.
2. Han-yu Wang, *When More Becomes Less* ([arXiv 2608.04021](https://arxiv.org/abs/2608.04021)),
   finds that **adjacent** copies climb and plateau while **displaced** copies produce an
   inverted-U. FT-01 tested the adjacent case and got the plateau. This tests the other half.

## The claim

**Pre-registered bet:** arrangement matters, and spreading copies apart is worse than
stacking them. Specifically I expect clustered >= bookend > spread at matched repetition
count, with the gap widening as repetition count rises.

**What would surprise me:** bookending beating clustered (folk practice vindicated), or all
three arrangements landing inside each other's intervals (arrangement is irrelevant and
FT-01's advice is the whole story).

## Design

Content is held constant so that **arrangement is the only variable**. Every prompt has a
fixed header plus exactly 16 instruction slots. N of those slots hold the constraint; the
remaining 16-N hold neutral filler drawn from a fixed list in a fixed order. Same tokens,
same filler, different order.

- **Constraint:** `Use only single-quoted strings. Never use double quotes.` (Same as FT-01,
  so results are comparable across experiments.)
- **Arrangements:**
  - `clustered` — all N copies consecutive, at the top. This is FT-01's shape.
  - `spread` — copies distributed evenly across the 16 slots.
  - `bookend` — half at the very top, half at the very bottom. The folk practice.
- **Repetition counts:** 2, 4, 8. Plus a shared `reps=1` baseline where arrangement has no
  meaning, and `reps=0` as the no-constraint control.
- **Tasks:** the same 6 Python functions as FT-01.
- **n:** 30 trials per cell.
- **Model:** `gemini-2.5-flash` on Vertex, thinking disabled, temperature at API default.
- **Verifier (pre-declared):** identical to FT-01. Tokenize the extracted code, count string
  tokens opening with a double quote. Zero means compliant. Truncated generations are
  recorded via `finishReason` and excluded, never counted as passes.

## Honest framing

This is a practical analog, not a replication. Wang's paper measures token-level readout
probability in a controlled probe. I am measuring whether a working engineer should stack or
spread a repeated instruction in a real system prompt. If the shapes agree that is
interesting; if they disagree, the probe and the prompt are different animals and the paper
is not wrong.

## Declared in advance

Every run reported. No arm dropped for looking bad. If arrangement turns out not to matter,
that publishes at full length and FT-01's advice stands unchanged.
