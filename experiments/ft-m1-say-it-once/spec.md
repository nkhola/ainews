# FT-M1 — Say It Once

**Pre-registered 2026-08-18, before any run.** Franchise rules: the bet is written down before data exists.

## The folk practice under test

Engineers repeat critical instructions in system prompts. "Say it twice so it listens." The practice is universal and, as far as I can tell, untested in public.

## The claim

**Pre-registered bet:** compliance rises with repetition and then flattens. If the arXiv 2608.04021 inverted-U result generalises from token-level targets to natural-language constraints, compliance should peak at a middling repetition count and then *decline*.

**What would surprise me:** a monotonic rise all the way to 16 (folk practice fully vindicated), or no effect at all.

## Design

- **Constraint:** `Do not include any comments in the code.` Chosen because models violate it constantly and compliance is exactly machine-checkable.
- **Conditions:** the constraint appears 0 (control, absent), 1, 2, 4, 8, or 16 times, consecutively, in the system prompt. Position held fixed so repetition *count* is the only variable. The 0 condition establishes the model prior, without which "repetition helps" is uninterpretable.
- **Tasks:** 6 Python functions, all the kind of thing a model likes to narrate with comments.
- **n:** 10 runs per (task, condition) = 300 calls.
- **Model:** Gemini via Vertex REST, temperature left at the API default (1.0) because that is how people actually run it.
- **Verifier (pre-declared):** extract the code block, run Python's `tokenize`, count `COMMENT` tokens. Zero comments = compliant. Unparseable output is recorded separately and excluded from the compliance denominator, never silently counted as a pass.
- **Docstrings are not comments** and are recorded separately rather than folded into the headline number.

## Metrics

Per the franchise framework: compliance rate with Wilson 95% intervals, flip rate (fraction of task-condition cells that are neither always-comply nor always-violate), output tokens per condition (does repetition inflate cost?), and unparseable rate.

## Declared in advance

Every run is reported. No condition gets dropped for looking wrong. If the result is "no effect," that publishes at full length.

## Amendments before the full run (logged, pre-data)

- **Constraint switched to `single_quotes`** after a calibration pass: `no_comments`, `no_docstring` and `no_type_hints` all sat at 98-100% compliance, a ceiling where repetition cannot show an effect in either direction. Calibration data is in `results/` and reported in the post.
- **Thinking disabled (`thinkingBudget: 0`).** Thinking tokens bill against `maxOutputTokens` but return separately; at a 900-token cap this truncated visible code mid-identifier and silently discarded up to 79% of runs, with a truncation rate that varied by condition. `finishReason` is now recorded and truncation is reported separately from parse failure.
- **Control condition added (reps=0).**
