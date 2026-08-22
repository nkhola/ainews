# FT-09 — When Pro Pays

**Pre-registered 2026-08-22, before any run.** The companion to FT-06 ("Thinking Budget").
FT-06 asks what you get for paying more *per call on the same model*. This asks what you
get for paying more *for a better model*, on the same tasks.

## The folk practice under test

"Use the cheap model for the easy stuff and the expensive one for the hard stuff." Everyone
says it. Nobody I have asked can tell me where the line is, and the price gap is not
subtle — on the Vertex list, `gemini-2.5-pro` output is **25x** `gemini-2.5-flash-lite`
output and **4x** `gemini-2.5-flash` output:

| model | $/M in | $/M out |
|---|---|---|
| `gemini-2.5-flash-lite` | 0.10 | 0.40 |
| `gemini-2.5-flash` | 0.30 | 2.50 |
| `gemini-2.5-pro` | 1.25 | 10.00 |

A 4x price difference that buys three points of accuracy is a bad trade dressed as
diligence. A 4x price difference that buys thirty points on the tasks that actually matter
is the cheapest thing in the budget. The question is which regime you are in, and the only
honest answer is per-difficulty.

## The claim

**Pre-registered bet:** Pro earns its price only in the hard band, and even there it has to
clear a second bar to be worth buying.

Precisely, four predictions, all falsifiable:

- **Easy tasks:** all three models land inside each other's Wilson intervals. Flash-lite is
  not merely competitive, it wins outright on cost per correct answer, by roughly an order
  of magnitude.
- **Medium tasks:** `gemini-2.5-flash` beats `gemini-2.5-flash-lite` by at least 10 points.
  Pro adds fewer than 5 points on top of Flash.
- **Hard tasks:** Pro beats Flash by at least 15 points.
- **The second bar:** even in the hard band, **cost per correct answer still favours
  Flash** unless Flash's hard-band pass rate falls below about 40%. Below that, retrying
  Flash stops being cheaper than buying Pro once, and the crossover is the actual finding.

Stated as one line for the post: **Pro is not a better model you should default to, it is a
floor you buy when the cheap model's pass rate gets too low to retry your way out of.**

**What would surprise me:**

- Flash-lite matching Flash on the medium band. That would say the medium tier is not
  actually discriminating, and the ladder needs rebuilding.
- Pro failing to separate on the hard band. Either the hard tasks are memorised at every
  price point (ceiling), or nothing at this price point can do them (floor). Both are
  reportable and both invalidate the crossover question.
- Pro losing anywhere. Non-monotonic price-to-accuracy would be the most interesting result
  available here, and the one I would least believe without a replication.

## Design

Same prompt, same tasks, same verifier, same output cap. **The model is the variable.**

- **Conditions:** exactly one no-op condition, `{"id": "default"}`. See "How the sweep
  works" below — the model cannot be a condition in this harness.
- **Tasks (10), graded in advance, not after seeing the results:**
  - *easy* (3): `reverse_words`, `dedupe_preserve_order`, `char_frequency`
  - *medium* (3): `merge_intervals`, `parse_duration`, `flatten_dict`
  - *hard* (4): `max_profit_k`, `evaluate_expression`, `min_window_substring`,
    `count_decodings`
  The first eight are **byte-identical to FT-06's task set**, so the two experiments read
  against each other directly. Two extra hard tasks are appended here because this
  experiment needs resolution at the top of the ladder, which is where the money is.
- **n:** 30 trials per cell. 10 tasks x 1 condition x 30 = **300 calls per model**, 900
  across the sweep. Projection: about $0.06 for Flash-lite, $0.33 for Flash, $1.32 for Pro,
  so roughly **$1.70 for the whole sweep**. The module caps each dispatch at $4.00.
- **Job order:** shuffled by the harness within each dispatch.

### Thinking is held down, not varied

Thinking is FT-06's subject, not this one's. It is pinned near zero here so that what is
being measured is base model capability at matched settings.

**One asymmetry has to be declared, because it cannot be designed away:** Pro-class models
reject `thinkingBudget: 0` and enforce a floor. The Flash arms therefore run at 0 and the
Pro arm runs at the 128-token floor. That is a genuine confound. It biases in Pro's favour,
which means a Pro *loss* is still a clean result and a Pro *win* carries an asterisk worth
about 128 tokens of thinking — and FT-06 measures exactly what 128 tokens of thinking is
worth, so the size of that asterisk is not a matter of opinion.

### How the sweep works

The harness runs **one model per invocation**: `core.run()` resolves the model as
`model argument -> LLM_MODEL_OVERRIDE -> mod.MODEL`, and `CONDITIONS` are prompt variations
*within* that one model. So the model genuinely cannot be a condition. This rig declares a
single no-op condition and the model is swept by dispatching the same experiment three
times with a different `model_override`.

**Exact model ids to sweep, in order:**

1. `gemini-2.5-flash-lite`
2. `gemini-2.5-flash`  (the default in `MODEL`)
3. `gemini-2.5-pro`  — the Pro-class arm

**The Pro id is confirmed by probe, not assumed.** `_harness/probe_models.py` prints which
ids actually answer in this project, and the Pro-class arm is whichever of `gemini-2.5-pro`,
`gemini-3.1-pro` or `gemini-3.1-pro-preview` comes back OK — preferring `gemini-2.5-pro`,
because keeping the sweep inside one model family means the ladder is a price ladder and
not a generation ladder. If it has to be a 3.x id, that is a family change and gets said
out loud in the post. The probe costs pennies and runs first, every time. The chosen id
goes into the dispatch, never into `MODEL`.

**Every dispatch writes to the same file**, `results/runs.jsonl`. The operator renames it
to `results/runs_<model>.jsonl` before the next dispatch, or the next run overwrites it.

Via the workflow (this is the normal path — results are committed back to `main` by the
job, so pull between dispatches):

```bash
cd ~/github_website/ainews

gh workflow run field-test.yml -f experiment=probe -f n_trials=1        # confirm the Pro id

gh workflow run field-test.yml -f experiment=ft-09-when-pro-pays \
    -f n_trials=30 -f model_override=gemini-2.5-flash-lite
# wait for it to finish and push, then:
git pull
git mv experiments/ft-09-when-pro-pays/results/runs.jsonl \
       experiments/ft-09-when-pro-pays/results/runs_gemini-2.5-flash-lite.jsonl
git commit -qm "FT-09: keep flash-lite arm" && git push

gh workflow run field-test.yml -f experiment=ft-09-when-pro-pays \
    -f n_trials=30 -f model_override=gemini-2.5-flash
git pull
git mv experiments/ft-09-when-pro-pays/results/runs.jsonl \
       experiments/ft-09-when-pro-pays/results/runs_gemini-2.5-flash.jsonl
git commit -qm "FT-09: keep flash arm" && git push

gh workflow run field-test.yml -f experiment=ft-09-when-pro-pays \
    -f n_trials=30 -f model_override=gemini-2.5-pro
git pull
git mv experiments/ft-09-when-pro-pays/results/runs.jsonl \
       experiments/ft-09-when-pro-pays/results/runs_gemini-2.5-pro.jsonl
git commit -qm "FT-09: keep pro arm" && git push
```

Locally, if credentials are in the environment:

```bash
cd ~/github_website/ainews
python experiments/_harness/probe_models.py

R=experiments/ft-09-when-pro-pays/results
for M in gemini-2.5-flash-lite gemini-2.5-flash gemini-2.5-pro; do
  LLM_MODEL_OVERRIDE=$M N_TRIALS=30 python experiments/_harness/core.py ft-09-when-pro-pays
  mv "$R/runs.jsonl" "$R/runs_$M.jsonl"
done
```

**Analysis caveat, stated now rather than discovered later:** `_harness/metrics.py` groups
by *condition*, and every arm here carries the same condition id, so pointed at the finished
sweep it would merge all three models into one meaningless row. It is the wrong tool for the
final read. Every record already carries a `model` field written by the harness; the
analysis groups on `model` x `difficulty`. `metrics.py` is still useful one file at a time,
as a per-dispatch sanity check.

### Verifier, declared in advance

Byte-identical to FT-06's, so a pass in one rig means a pass in the other. Mechanical end to
end; no model grades anything.

1. Extract the fenced block defining the target function, by regex, matching fences at line
   start with any info string so a closing fence cannot be mistaken for an opener.
2. `exec()` it in a restricted namespace: fixed builtins allowlist, stdlib-only import
   allowlist, `print` neutered, `__name__` not `__main__` so an appended demo block does not
   run.
3. Call the function against a fixed list of assertions written before any run — 6 to 9 per
   task, including the empty case and the edge case the spec calls out.
4. Record `{"pass": bool, "n_passed": int, "n_asserts": int, "difficulty": str}`.

`eval`, `exec`, `compile` and `open` are absent from the sandbox builtins, which is what
mechanically enforces "implement the parsing yourself" on `evaluate_expression`. Execution
runs under a per-thread wall-clock guard (5s to define, 3s per assertion, 8s total) because
a wrong dynamic-programming answer is usually an infinite loop. `verify()` catches
everything and returns `{"pass": None, "error": ...}` rather than raising.

Every reference solution was run through the verifier before pre-registration and scores
full marks, so a failure in the data is the model's, not the assertion list's.

### What gets reported

Pass rate by model and difficulty band with Wilson intervals, never bare percentages. Then
the number the experiment exists for: **dollars per correct answer, by model and band**,
computed from the recorded token counts at the list prices in the table above. Treat those
as planning figures, not billing truth. Truncation counts and API failures reported
separately per model.

## Honest framing

Weekend scale. One model family, one language, ten problems, 900 calls. Not a benchmark,
not state of the art, and deliberately not a leaderboard — the interesting output is a
crossover point in a difficulty ladder, not a ranking. The hard tasks are hard for a
Flash-class model, not hard in any absolute sense, and at least two of them are recognisable
enough that memorisation is a live confound, which is why the bands are the unit of analysis
rather than a single headline number.

A price ladder inside one generation is the cleanest version of this question. If the probe
forces a 3.x Pro id, the ladder becomes part price and part generation, and every conclusion
gets that caveat attached in the post rather than buried here.

## Declared in advance

Every run reported. No model dropped for looking bad, including a Pro arm that fails to
justify itself. Truncated generations reported separately and never counted as passes. The
Pro thinking floor is disclosed in the post, not just in this file. If the crossover does
not exist — if Pro wins everywhere, or nowhere — that publishes at full length. The
predictions above stay standing with a post-hoc note if they are wrong; they are never
edited after seeing data.
