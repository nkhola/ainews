# The clustering correction

**Raised by a Hacker News commenter on the FT-01 post, 2026-08. The criticism is correct.**

> "Weighing six rocks a hundred times doesn't tell you the average weight of a mountain."

## What I did wrong

Every Field Test reported Wilson intervals computed over *runs*: 6 tasks x 30 trials = 180
runs, treated as 180 independent Bernoulli trials. They are not independent. Runs within a
task are correlated, so the effective sample size for any claim about "coding tasks in
general" is the number of TASKS (6 to 10), not the number of runs.

The consequence is that my published intervals are too narrow, and some non-overlap claims
do not survive once the task is treated as the unit of analysis.

## Recomputed, task as the unit (t-interval over per-task rates)

FT-01, published as "Say It Four Times":

| reps | naive over runs | clustered over tasks | per-task rates |
|---|---|---|---|
| 0 | 0% [0,2] | 0% [0,0] | 0,0,0,0,0,0 |
| 1 | 74% [68,80] | 74% **[40,100]** | 20,57,70,100,100,100 |
| 2 | 84% [78,89] | 84% [62,100] | 47,73,87,97,100,100 |
| 4 | 97% [93,98] | 97% [93,100] | 90,97,97,97,100,100 |
| 8 | 94% [89,97] | 94% [86,100] | 80,93,93,97,100,100 |
| 16 | 95% [91,97] | 95% [87,100] | 80,93,97,100,100,100 |

**The published claim does not survive.** I wrote that 1x (74%) and 4x (97%) were "far enough
apart that I'm comfortable calling it real." Clustered, those intervals are [40,100] and
[93,100]. They overlap. Three of six tasks were already at 100% with a single mention; one
was at 20%. The mean of 74% describes my task mix, not a property of the model.

## What survives and what doesn't

| Claim | Naive | Clustered | Verdict |
|---|---|---|---|
| FT-01 control: never complies unprompted | 0% [0,2] | 0% [0,0] | **holds**, 0/171 on every task |
| FT-01 one mention vs four | non-overlap | [40,100] vs [93,100] | **does not hold** |
| FT-02 4x clustered vs spread | 87 [81,91] vs 52 [44,59] | 87 [78,96] vs 52 [31,73] | **holds, barely** |
| FT-12 defended vs plain | 100 [98,100] vs 56 [49,62] | 100 [100,100] vs 54 [14,94] | **holds**; defended is 100% on all 8 tasks |
| FT-11 repetition beats position | 87 [81,91] vs 33 [26,41] | 87 [65,100] vs 33 [0,88] | **does not hold** at 95% |

## What to do about it

1. Publish a correction post. Lead with the criticism, quote it, show the recomputed table,
   and retract the FT-01 and FT-11 headline claims explicitly.
2. Add cluster-aware intervals to `_harness/metrics.py` so every future experiment reports
   both, with the clustered one as the headline.
3. Raise task counts. Six tasks is too few to say anything about "coding tasks." Twenty
   tasks with ten trials each beats six tasks with thirty, for the same call budget.
4. Keep reporting per-task tables. FT-01 already printed one showing 20% to 100% spread, and
   I still quoted the pooled mean as if it generalised. The table was right there.

The findings that survive are the ones where the effect held on *every task*, not the ones
with the biggest pooled difference. That is the lesson worth carrying forward.
