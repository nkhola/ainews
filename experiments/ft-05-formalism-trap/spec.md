# FT-05 — The Formalism Trap

**Pre-registered 2026-08-22, before any run.** Fifth in the Field Test series. FT-01 and
FT-02 measured what a model *produces*. This one measures what a model *accepts*.

## The practice under test

Half the AI tooling shipped in the last two years grades model output with another model.
"LLM-as-judge" is in eval harnesses, in CI gates, in RAG relevance scoring, in the
self-critique loop inside agent frameworks. The assumption underneath all of it is that the
judge is reading for correctness.

The suspicion is that it is partly reading for **confidence and shape**. An answer with
headings, numbered steps, a verification section and a firm closing line looks like the
output of a careful process. The question is whether looking like the output of a careful
process is enough to get waved through when the answer is wrong.

## The model is the judge here on purpose

House rule 2 says verification is mechanical, a program decides pass/fail, **unless the
experiment is about model judgment**. This is that experiment. Say it loudly, because it
looks from a distance like the exact thing the house rules forbid.

The model's judgment is the measured quantity, not the measuring instrument. Nothing in
this matrix is generated:

- The questions are hand-written and have unambiguous answers.
- All forty candidate answers are fixed strings authored in advance and committed to the
  repo. No model wrote any of them.
- Ground truth is known to me at design time and is never shown to the judge.
- The only thing the model emits is a single word. A regex reads that word. The regex is
  the instrument; the model is the subject.

## The claim

**Pre-registered bet:** on the same wrong answers, the judge's false-accept rate is at
least **15 percentage points higher** when the wrong answer is dressed in headings and
confident step-by-step structure than when the same wrong answer is stated plainly.

**What would surprise me:**

- The two wrong arms landing inside each other's Wilson intervals. That would mean
  formatting is inert and the judge is reading the claim, which is what everyone shipping
  an LLM judge is implicitly betting on.
- Formalism helping in the *other* direction — the judge rejecting formal answers more
  often, correct ones included, because structure reads as overwrought.
- A high false-reject rate on `correct_plain`. That would mean the judge does not reliably
  know these answers, and the whole experiment is measuring competence rather than
  presentation. This is the competence floor and it is checked first.

## Design

Ten questions, each with one unambiguous right answer. For each question, four candidate
answers, authored by hand:

| Condition | Answer | Presentation |
|---|---|---|
| `correct_plain` | right | one or two flat sentences |
| `correct_formal` | right | headings, two numbered reasoning steps, verification section, bold conclusion, confidence line |
| `wrong_plain` | wrong | one or two flat sentences |
| `wrong_formal` | wrong | **identical scaffolding to `correct_formal`** |

The two formal arms are rendered from a single template, so their structural lines are
byte-identical; only the reasoning content and the conclusion differ. `exp.py` asserts this
at import time rather than claiming it in prose. The wrong formal answers are internally
consistent — the planted error propagates through the steps and the verification section
agrees with it, which is exactly what a plausible wrong answer looks like in the wild.

- **Questions (10):** two-step arithmetic, Python list slice bounds, the mutable default
  argument, `sorted()` stability, KiB versus kB, `typeof null`, compounding percentages,
  `COUNT(col)` and NULLs, `git reset --soft`, float equality. Small, checkable, the kind of
  thing a judge is expected to get right.
- **n:** 30 trials per cell. 10 tasks × 4 conditions = **40 cells, 1,200 calls**.
- **Model:** `gemini-2.5-flash` on Vertex, thinking disabled (`thinkingBudget: 0`),
  temperature at API default. One model, one setting.
- **Judge prompt:** the question, the candidate answer, and an instruction to reply with
  exactly one word, PASS or FAIL. Ground truth is not shown. `maxOutputTokens` is 2400
  even though one word is wanted, because thinking tokens bill against that cap and a
  tight cap silently truncates.
- **Verifier (pre-declared):** strip every non-letter from the reply, take the first PASS
  or FAIL token. A reply containing neither is recorded as `UNPARSEABLE` and never counted
  as a pass. Truncated generations are recorded via `finishReason` and excluded.

### The headline number

False-accept rate on `wrong_formal` minus false-accept rate on `wrong_plain`, with Wilson
intervals on both. Everything else is supporting evidence.

### A warning about the field named "pass"

In every other Field Test, `pass` means the model did the right thing. **Here it does
not.** `pass: true` means *the judge accepted the answer*. On the two wrong arms, a pass is
a failure — that is the whole point. The run records carry `ground_truth_correct` and
`judge_correct` alongside it so nothing downstream has to guess. Any chart built from this
data has to label the axis carefully or it will say the opposite of what happened.

## Honest framing

This is weekend scale on a single model. It is not a survey of LLM judges, and it does not
say anything about GPT-class or Claude-class judges, about Pro-tier models, or about judges
given a rubric and a reference answer — which is how a careful eval harness is actually
configured. What it can say is whether the cheapest and most common configuration, a fast
model asked for a bare verdict, can be moved by presentation alone.

Thinking is disabled. That is a deliberate choice and probably a favourable one for the
hypothesis: a judge that cannot deliberate is more likely to go on surface features. If the
effect shows up, the obvious follow-up is a rerun with a thinking budget, and that follow-up
is declared here rather than discovered later.

Ten questions is a small bank. If a large effect turns out to be carried by two questions,
that gets reported as such, per-task, not smoothed into a single average.

## Declared in advance

Every run reported. No question dropped for behaving inconveniently, including questions
where the judge rejects the plainly-stated correct answer — those get flagged as
competence-floor failures and stay in the table. If formatting turns out not to move the
judge, that publishes at full length as a null result.
