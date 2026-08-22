# FT-03 — Phrasing Cost

**Pre-registered 2026-08-22, before any run.** Third in the series after FT-01 ("Say It Four
Times") and FT-02 ("Top and Bottom Doesn't Work"). Those two asked whether prompt structure
changes *compliance*. This one asks whether it changes *the bill*.

## The folk practice under test

Two claims that circulate constantly and are almost never measured:

1. **"Being polite to the model costs you money."** The version that goes viral is the
   estimate that pleasantries cost OpenAI tens of millions of dollars a year. That is an
   input-token argument and it is arithmetically boring: longer prompt, more input tokens,
   trivially true. The interesting question is whether the wrapper changes the *output*,
   which on `gemini-2.5-flash` is priced 8.3x higher than input ($2.50/M vs $0.30/M).
2. **"Say 'be concise' and you'll get a shorter answer."** Also everywhere. Also usually
   asserted rather than measured.

The thing nobody publishes is the cross-product: ten ways of asking for the same code, same
model, same day, with the token counts printed.

## The claim

**Pre-registered bet:** the wrapper moves output tokens by more than the input tokens it
adds, and the movement is not symmetric. Specifically, at matched request text:

- `be_concise` and `terse` produce **at least 20% fewer output tokens** than `bare`.
- `stepwise` produces **at least 40% more** output tokens than `bare` — this is the arm I
  expect to dominate the bill, because asking for reasoning buys visible prose even with
  thinking disabled.
- `polite`, `chatty`, `verbose`, `role`, and `urgent` land **within 10% of `bare` on output
  tokens**. My bet is that social register is nearly free on the expensive side of the meter
  and only costs you the input tokens you typed, which are cheap.
- Pass rate (parseable code with the right function name) stays **above 90% in every arm**,
  because these are easy tasks and the wrapper should not break code generation.

Put in one line: **politeness is cheap, asking for reasoning is expensive, and "be concise"
actually works.**

**What would surprise me:**

- Politeness costing real output tokens — `polite` or `chatty` more than 15% above `bare`.
  That would make the viral claim right for a reason its authors did not give.
- `be_concise` not working, or backfiring by making the model write a paragraph explaining
  how concise it is being.
- Format collapse: an arm where the model stops fencing its code. `fenced` is recorded per
  run precisely so this shows up rather than hiding inside the pass rate.
- Any arm dropping below 90% pass. If phrasing breaks correctness on tasks this easy, FT-04
  gets much more interesting than I expect it to be.

## Design

The request text is **byte-identical in every arm**. Only the wrapper around it changes. The
system instruction is a single neutral sentence ("You are a helpful coding assistant."),
identical in every arm, and it deliberately says **nothing about output format**. Real
requests do not carry a format contract, and format drift under a wrapper is part of what is
being measured.

- **Conditions (10):**
  | id | family | shape |
  |---|---|---|
  | `bare` | control | the request, nothing else |
  | `terse` | short | request + "Code only." |
  | `be_concise` | short | request + "Be concise." |
  | `polite` | social | greeting, "would you mind", thanks |
  | `chatty` | social | rambling Slack-style preamble |
  | `verbose` | long | ~70 words of throat-clearing around the same request |
  | `stepwise` | effort | "Work through this step by step before you answer" |
  | `role` | effort | "You are a senior Python engineer with fifteen years..." |
  | `urgent` | effort | "IMPORTANT: this is going straight into production" |
  | `spec_form` | structured | REQUIREMENT / DELIVERABLE headings |
- **Tasks (6):** `merge_intervals`, `retry_with_backoff`, `parse_semver`, `chunk_iterable`,
  `lru_cache_decorator`, `flatten_dict` — the same six functions, with the same request
  strings, as FT-01 and FT-02. Reused deliberately so token counts are comparable across the
  whole series.
- **Matrix:** 6 tasks x 10 conditions = 60 cells, n = 30 trials per cell, 1,800 calls.
- **Model:** `gemini-2.5-flash` on Vertex, thinking disabled (`thinkingBudget: 0`),
  `maxOutputTokens` 2400, temperature at API default.
- **Budget:** $3.00 hard ceiling enforced in-process. Planning estimate ~$1.85.

### Verifier (pre-declared, mechanical)

No model grades anything. `verify()` does exactly this:

1. Pull every fenced block with the regex ```` ```(?:python|py|python3)?\n(.*?)``` ````.
2. Choose the first block that `ast.parse`s **and** contains a `FunctionDef` with the target
   name. Failing that, the longest fenced block. Failing that, the raw response text.
3. `pass` = the chosen code parses and defines a function with the exact expected name.
4. Also recorded per run: `chars` (length of the full response), `lines` (non-blank,
   non-comment-only lines of the extracted code), `fenced` (did the model use a code fence at
   all), and `reason` when it failed.

The harness records `promptTokenCount` and `candidatesTokenCount` on every call. **Those are
the real dependent variable.** `chars` and `lines` are the human-legible cross-check: if
output tokens move but `lines` does not, the model is writing more prose, not more code.

Truncated generations (`finishReason` other than `STOP`) are recorded and excluded, never
counted as passes.

## Honest framing

This is weekend-scale. One model, one provider, one day, six easy Python functions, English
only, temperature left at the API default. It measures what a working engineer's phrasing
habits cost on `gemini-2.5-flash` in August 2026. It does not measure what politeness costs
at OpenAI's scale, it does not generalise to other model families, and it says nothing about
prompts that are not "write me a small function."

The input-token half of the result is arithmetic and I am not going to pretend it is a
finding — a longer wrapper is longer, and you can count that yourself without spending a
cent. The output-token half is the part I do not know the answer to.

One known confound, declared up front: the wrappers differ in length *and* in content, so
`verbose` versus `bare` is not a clean length manipulation. `bare` versus `polite` versus
`chatty` is closer to matched, and the `short` family is the cleanest contrast in the set.

## Declared in advance

Every run reported. No arm dropped for looking bad. Wilson intervals on pass rates, never
bare percentages. If all ten wrappers land inside each other's intervals on output tokens,
that publishes at full length as "phrasing does not move the bill, stop worrying about it" —
which is a useful result and a boring post, and it goes out anyway.
