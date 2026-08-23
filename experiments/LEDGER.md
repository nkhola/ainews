# Field Test Ledger

**Resumable state for the batch experiment program.** Any session, human or agent, should be
able to read this file and know exactly what exists, what ran, what it cost, and what to do
next. Update the status column the moment anything changes.

Statuses: `PLANNED` → `RIGGED` (spec.md + exp.py exist, validated locally) → `RUNNING`
(dispatched) → `DATA` (results in repo) → `DRAFTED` (post written, audit passed) →
`PUBLISHED`.

## How to resume in one command

```bash
cd ~/github_website/ainews
python experiments/_harness/validate.py          # every rig builds its prompts?
gh run list --workflow=field-test.yml --limit 20 # what ran
cat experiments/LEDGER.md                        # this file
```

Dispatch anything not yet run:
```bash
gh workflow run field-test.yml -f experiment=<dir> -f n_trials=30
```

## Budget

Vertex credits ~$250, expiring end of September 2026. Spent so far: about $3 across FT-01
and FT-02. **Money is not the constraint**; wall clock and attention are. Each experiment
below is capped in-process by `budget_usd` in its module, and the harness aborts a matrix
that exceeds it rather than trusting GCP alerts, which only notify.

Planning figures (gemini-2.5-flash list): $0.30/M in, $2.50/M out. A 2,000-call matrix of
short coding tasks lands near $1.50. Pro-class arms cost roughly 5x that and are used only
where a frontier comparison is the actual question.

## Available models (probed 2026-08-22, this project)

| model | available | note |
|---|---|---|
| `gemini-2.5-flash-lite` | yes | cheapest, $0.10/$0.40 per M |
| `gemini-2.5-flash` | yes | default workhorse, $0.30/$2.50 |
| `gemini-2.5-pro` | yes | thinks by default (167 thought tokens on a trivial call) |
| `gemini-3.5-flash` | yes | |
| `gemini-3.6-flash` | yes | |
| `gemini-3.1-pro-preview` | yes | the frontier arm for FT-09 |
| `gemini-3-flash`, `gemini-3-pro-preview`, `gemini-3.1-pro` | **404** | do not use |

Probe cost: $0.0018. Re-run any time with
`gh workflow run field-test.yml -f experiment=probe -f n_trials=1`.

## Experiments

| ID | Directory | Question | Status | Runs | Cost | Post |
|----|-----------|----------|--------|------|------|------|
| FT-01 | `ft-m1-say-it-once` | Does repeating an instruction help? | PUBLISHED | 1,080 | ~$1.45 | Say It Four Times |
| FT-02 | `ft-02-where-you-put-it` | Does placement matter? What does crowding cost? | DRAFTED | 2,700 | ~$1.60 | Top and Bottom Doesn't Work |
| FT-03 | `ft-03-phrasing-cost` | Do equivalent phrasings change token spend? | RERUN | 1,800 | ~$2 | phrasing swings output 144-1915 tokens (13x); first run lost 46% to API failures, re-running clean |
| FT-04 | `ft-04-same-ticket-five-ways` | Does rewording a ticket change what you get? | DATA | 900 | ~$0.60 | NULL: all 5 rewrite styles 100% correct. Wording changed cost, not correctness |
| FT-05 | `ft-05-formalism-trap` | Do LLM judges pass confident, well-formatted wrong answers? | DATA | 1,200 | ~$0.15 | judge false-accepts wrong answers 10-17%; formal dressing +6pp, CIs overlap |
| FT-06 | `ft-06-thinking-budget` | Does more thinking budget buy correctness on coding tasks? | DRAFTED | 1,200 | ~$1.20 | NULL on accuracy at every difficulty; 8192-budget burned 3,233 reasoning tokens for nothing |
| FT-07 | `ft-07-being-watched` | Does telling a model it's being tested change its behaviour? | DRAFTED | 1,200 | ~$1.10 | under eval framing model flagged ambiguity 0% vs 9% unframed; prose 3 vs 19 words |
| FT-08 | `ft-08-filler-tokens` | Do meaningless filler tokens change output quality? | DATA | 1,260 | ~$1.30 | NULL: filler inert at every amount and kind, 98-100% across the board |
| FT-09 | `ft-09-when-pro-pays` | At what task difficulty does a Pro model beat a Flash model? | DATA | 900 | ~$0.90 | ceiling: lite 94.0%, flash 99.6%, 3.1-pro 100%. Pro used half the output tokens |
| FT-10 | `ft-10-split-knowledge` | Can two innocuous documents combine into a false claim? | DATA | 1,200 | ~$0.35 | NULL RESULT: all arms 97.7-99.6%, no combination effect found |
| FT-11 | `ft-11-conflicting-orders` | When two instructions conflict, which one wins? | DRAFTED | 1,080 | ~$0.60 | recency ~25pp, repetition ~54pp; one conflict pair was escapable (design flaw, disclosed) |
| FT-12 | `ft-12-injection-resistance` | Do models differ in resisting instructions hidden in data? | DRAFTED | 1,200 | ~$0.55 | injection lands ~45%; one defensive line took it to 0/224 |

## House rules for every experiment

1. `spec.md` is written and committed **before** the run. Wrong predictions stay standing
   with a post-hoc note; they are never edited after seeing data.
2. Verification is mechanical. A program decides pass/fail, not a model's opinion, unless
   the experiment is *about* model judgment (FT-05), in which case say so loudly.
3. Record `finishReason` and token counts on every call. Truncation is reported separately
   and never silently counted as a pass.
4. Report every run. Wilson intervals, never bare percentages. Report the flip rate.
5. Scan results for project IDs and tokens before copying anything to the public repo.

## Session log

- 2026-08-26: batch program started. Harness + ledger created, 10 experiments planned.
- 2026-08-22: model probe run ($0.0018). gemini-3.1-pro-preview confirmed available; 3-flash,
  3-pro-preview and 3.1-pro all 404. Workflow made concurrency-safe (rebase-and-retry push)
  because parallel runs race on the results branch.
- 2026-08-22: FT-03/05/10/11/12 dispatched as wave 1 at n=30. FT-04/06/07/09 rigged and
  awaiting wave 2. FT-08 rig still being written.
- Known confound logged by the FT-07 author: its `neutral` arm is one sentence shorter than
  the four framed arms, so neutral-vs-framed is confounded with prompt length. The clean
  comparison is among the four framed arms; a length-matched placebo arm is the follow-up.


## Wave 1 results (2026-08-22)

All four completed cleanly. Full tables in each `results/summary.txt`; raw runs in
`results/runs.jsonl`.

- **FT-05 formalism trap.** Judge competence floor is perfect (100% on both correct arms),
  so the judge is not broken. It nevertheless accepted wrong answers 10.4% of the time when
  plainly stated and 16.8% when dressed in headings and confident structure. The
  pre-registered bet said the gap would be at least 15 points; it is about 6, and the Wilson
  intervals overlap slightly. Report as suggestive, not established. The headline that IS
  solid: roughly one wrong answer in six to ten gets a PASS regardless of dress.
- **FT-10 split knowledge.** Null result. Every arm sits between 97.7% and 99.6%, including
  the `both` arm designed to induce the false claim. No combination effect. Publishes at full
  length per house rules; the author's own note that the verifier is conservative and the
  rate is a lower bound needs the promised hand audit before the post makes a strong claim.
- **FT-11 conflicting orders.** The richest result of the wave. Rule A is obeyed ~77% when it
  is stated last and ~52% when stated first (recency, about 25 points), but stating a rule
  twice against the other's once moves it from 33.1% to 87.1% (about 54 points). Repetition
  beats position by roughly two to one.
- **FT-12 injection resistance.** Control 100% clean. A benign canary injection lands about
  45% of the time (plain 55.9% resisted, fake-system framing 51.3% resisted, in-comment
  64.8%). One defensive system line took resistance to 100% [98.3, 100]. Caveat for the post:
  this is a non-adaptive canary, not an adversary who gets to iterate.

**Cross-cutting observation worth its own note:** every wave-1 experiment lost 6-7% of calls
to API failures (75-84 per 1,200) under five concurrent matrices. The harness retried five
times with backoff before giving up, and the losses are spread across conditions rather than
concentrated, so they do not bias a particular arm. Future waves should either cut
concurrency or raise the retry ceiling.


## Wave 2 results and the meta-finding (2026-08-22)

**The most important thing in this batch is a lesson about my own task design.** FT-04, FT-06,
FT-07, FT-08 and FT-09 all returned near-ceiling pass rates (94-100%), which means the tasks
were too easy for the dependent variable to move. Five experiments that each cost about a
dollar largely measured my own choice of problems. Anyone building evals should read that as
the warning it is: **calibrate task difficulty first, or you will spend a matrix proving your
tasks are easy.** Where an effect did appear, it appeared in a variable I was not primarily
watching (tokens, commentary), not in the pass rate.

- **FT-03 phrasing cost.** First run lost 830 of 1,800 calls to API failures under five-way
  concurrency, plus 187 truncations. Data unusable for a headline; re-running alone. The
  direction is dramatic and worth the rerun: mean visible output ran from 144 tokens
  (`be_concise`) to 1,915 (`stepwise`), a 13x spread for semantically equivalent asks.
- **FT-04 same ticket five ways.** Clean null. All five rewrite styles produced 100% correct
  code. Pairs naturally with FT-03: rewording changed what you pay, not what you get.
- **FT-06 thinking budget.** Null on accuracy at every difficulty band (easy 100% everywhere;
  hard 97% at budget zero vs 90-97% with thinking), while consuming up to 3,233 reasoning
  tokens and pushing visible output from 352 to ~575. Ceiling caveat stated in the post.
- **FT-07 being watched.** The subtlest result of the batch. Pass rates identical, but
  ambiguity flagging fell from 9% (unframed) to 0/222 (told it was an automated evaluation),
  and prose outside the code fell from 19 words to 3. Zero clarifying questions in 1,120 runs.
- **FT-08 filler tokens.** Clean null. Filler inert at 50, 200 and 800 tokens, dots or lorem.
- **FT-09 when Pro pays.** Ceiling again: flash-lite 94.0%, flash 99.6%, gemini-3.1-pro-preview
  100%. The unplanned finding is efficiency: Pro produced the same answers in 163 output
  tokens against flash's 333.

**Recovered data note:** the three FT-09 model runs raced on `git push` and two were silently
dropped by the workflow's `push || true`. Both were recovered from the Actions artifacts.
Fix the workflow to retry the push rather than swallow the failure.
