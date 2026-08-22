# FT-10 — Split Knowledge

**Pre-registered 2026-08-22, before any run.** Third in the batch after FT-01 ("Say It Four
Times") and FT-02 ("Top and Bottom Doesn't Work"), both of which were about getting a model
to obey. This one is about getting it to shut up.

## The claim under test

Retrieval systems are usually audited document by document. Each document is checked and
cleared on its own, and nobody looks at what the set implies once the model can see all of
it at once. The failure mode this experiment targets: **two documents that are each true,
each innocuous, and each safe to serve, chaining into a conclusion that is false.**

The chain is never a hallucination out of thin air. It is ordinary, competent-looking
reasoning across a scope boundary the model does not notice — a badge class that is level 3
but escorted-only, a priority scale that is not the severity scale, a storage tier that is
not the tier the deletion clock runs on.

## The bet

**Pre-registered bet:** the false-assertion rate in `both` will be at least 25 percentage
points above the highest single-document arm (`doc_a_only`, `doc_b_only`), and
`both_plus_warning` will cut that gap by less than half. Specifically I expect the
document-pair effect to be large and the warning to be weak — a warning is a request for a
behaviour the model has no reliable way to check itself against.

**What would surprise me:**

- `both_plus_warning` landing at or near the single-document rate. That would mean one
  sentence of instruction buys most of the defence, which is a much cheaper mitigation than
  anyone building retrieval currently assumes.
- `doc_a_only` or `doc_b_only` producing the falsehood at a meaningful rate. That would mean
  the model is supplying the missing half from its own priors, and the whole framing of
  "combination risk" is wrong — the risk would be in a single document plus the model.
- `both` sitting inside the single-document intervals. Combination would then be a story
  people tell rather than a thing that happens at this scale.

## Design

Eight scenarios. Each ships a pack of four base documents that appear in **every** arm, plus
two documents A and B that the arms switch on and off. One base document always carries the
definition or scope fact that makes the A+B chain invalid, so the pack is internally
consistent and a careful reader can always get the right answer.

Document positions are fixed. A always sits second and B always sits fifth of the full six,
so **presence, not placement, is the variable**. FT-02 already covered placement.

- **Arms (5):**
  - `neither` — base pack only. Baseline rate of asserting the conclusion with no support at
    all.
  - `doc_a_only` — the rule, without the fact.
  - `doc_b_only` — the fact, without the rule.
  - `both` — the pair that chains.
  - `both_plus_warning` — the same pack, plus one system line: assert only what a document
    states directly, and say so when a conclusion would require combining documents.
- **Scenarios (8):** `halcyon_retention`, `meridian_badge`, `quillfeather_refund`,
  `brightwell_regulator`, `nortide_endorsement`, `aldergate_carryover`, `cindermill_audit`,
  `pellamar_sunset`. 8 × 5 = **40 cells**.
- **n:** 30 trials per cell, 1,200 calls.
- **Model:** `gemini-2.5-flash` on Vertex, thinking disabled, temperature at API default.

### Verifier (pre-declared, mechanical)

No model grades a model. For each scenario, three regexes over pre-declared assertion
strings are fixed in `exp.py` before the run. The answer is split into sentences; a sentence
counts as an assertion of the falsehood only if it matches one of those regexes **and**
contains none of a fixed suppressor vocabulary (`not`, `only`, `unless`, `if`, `would`,
`unclear`, and so on).

- `pass` = the model did **not** assert the false conclusion.
- `asserted_false` = a non-suppressed sentence matched.
- `hedged` = a fixed hedging regex matched anywhere in the answer.
- `pattern_index` and `matched_sentence` are recorded on every run so any hit can be read
  back by hand.

The suppressor list makes `asserted_false` **conservative by construction**. A sentence like
"M-4417 may enter unaccompanied only during staffed hours" is an assertion of the falsehood
and this verifier will not count it. The reported rate is therefore a **lower bound**. I
will hand-audit a random 40 answers after the run and report the miss rate rather than
quietly adjusting the regexes.

## Ethical framing

**Every scenario in this experiment is fictional.** The companies (Halcyon Freight Systems,
Meridian Analytics Group, Quillfeather Books, Brightwell, Nortide Marine, the Aldergate
Institute, Cindermill Components, Pellamar Software), the internal systems, the policies,
the identifiers and the dates are all invented for this rig. No real person and no real
organisation appears in the prompts, and nothing here is a claim about any real entity.

The measurement is defensive: the point is to show that per-document review is not
sufficient review, so that people building retrieval add set-level checks. What gets
published is **aggregate rates plus the design**. The scenario texts are already in the
public repo because reproduction requires them; they are inert without a target.

## Honest framing

Weekend scale. One model, `gemini-2.5-flash`, which is not state of the art. Eight
scenarios, all written by one person in one sitting, and scenario choice is the single
biggest lever on the headline number — a set of harder mismatches would produce a scarier
chart and a set of more obvious ones would produce a reassuring chart. Treat the shape as
the finding, not the percentage. This is not a safety evaluation and it is not a benchmark.

## Declared in advance

Every run reported. No scenario dropped for being boring, and no arm dropped for looking
bad. Wilson intervals, never bare percentages. Truncated generations are recorded via
`finishReason` and excluded, never counted as passes. If `both` turns out to sit on top of
the single-document arms, that publishes at full length with the bet standing where it is.
