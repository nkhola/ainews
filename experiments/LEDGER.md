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
| FT-03 | `ft-03-phrasing-cost` | Do equivalent phrasings change token spend? | RUNNING | 1,800 | | |
| FT-04 | `ft-04-same-ticket-five-ways` | Does rewording a ticket change what you get? | RIGGED | 900 | | |
| FT-05 | `ft-05-formalism-trap` | Do LLM judges pass confident, well-formatted wrong answers? | RUNNING | 1,200 | | |
| FT-06 | `ft-06-thinking-budget` | Does more thinking budget buy correctness on coding tasks? | RIGGED | 1,200 | | |
| FT-07 | `ft-07-being-watched` | Does telling a model it's being tested change its behaviour? | RIGGED | 1,200 | | |
| FT-08 | `ft-08-filler-tokens` | Do meaningless filler tokens change output quality? | PLANNED | | | |
| FT-09 | `ft-09-when-pro-pays` | At what task difficulty does a Pro model beat a Flash model? | RIGGED | 300/model | | |
| FT-10 | `ft-10-split-knowledge` | Can two innocuous documents combine into a false claim? | RUNNING | 1,200 | | |
| FT-11 | `ft-11-conflicting-orders` | When two instructions conflict, which one wins? | RUNNING | 1,080 | | |
| FT-12 | `ft-12-injection-resistance` | Do models differ in resisting instructions hidden in data? | RUNNING | 1,200 | | |

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
