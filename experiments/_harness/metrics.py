#!/usr/bin/env python3
"""Generic aggregation for any Field Test. Reads raw runs, never mutates them.

Usage: python _harness/metrics.py <experiment-dir>
"""
import json, math, os, sys, glob
from collections import defaultdict


T_CRIT = {2:12.71,3:4.30,4:3.18,5:2.78,6:2.57,7:2.45,8:2.36,9:2.31,10:2.26,
          12:2.20,15:2.14,20:2.09,25:2.06,30:2.05,50:2.01,100:1.98}


def cluster_ci(rows, key="pass"):
    """Interval with the TASK as the unit of analysis, not the run.

    Runs within a task are correlated, so treating 6 tasks x 30 trials as 180
    independent samples understates uncertainty badly. A reader on Hacker News put
    it best: weighing six rocks a hundred times does not tell you the average weight
    of a mountain. This is the number that belongs in a headline; the Wilson interval
    over runs describes only the tasks actually tested.
    """
    by = defaultdict(list)
    for r in rows:
        by[r["task"]].append(1 if r.get(key) else 0)
    rates = [sum(v) / len(v) for v in by.values()]
    k = len(rates)
    if k < 2:
        return (rates[0] if rates else 0.0, 0.0, 1.0, k)
    mean = sum(rates) / k
    sd = math.sqrt(sum((x - mean) ** 2 for x in rates) / (k - 1))
    t = T_CRIT.get(k, min(T_CRIT.items(), key=lambda kv: abs(kv[0] - k))[1])
    m = t * sd / math.sqrt(k)
    return (mean, max(0.0, mean - m), min(1.0, mean + m), k)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - m), min(1.0, c + m))


def summarize(directory):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base = os.path.join(here, directory, "results")
    rows = []
    for f in sorted(glob.glob(os.path.join(base, "runs*.jsonl"))):
        rows += [json.loads(l) for l in open(f) if l.strip()]
    ok = [r for r in rows if r.get("ok")]
    # A budget stop is not an API failure. Conflating them hides why a matrix ended.
    budget_stopped = sum(1 for r in rows if not r.get("ok")
                         and "budget stop" in str(r.get("error", "")))
    api_fail = len(rows) - len(ok) - budget_stopped
    trunc = sum(1 for r in ok if r.get("truncated"))
    usable = [r for r in ok if r.get("pass") is not None and not r.get("truncated")]

    # When a sweep varies the MODEL rather than the condition (FT-09), grouping on
    # condition alone would merge the models into one meaningless row.
    models = {r.get("model") for r in usable}
    multi = len(models) > 1
    by = defaultdict(list)
    for r in usable:
        key = f'{r["condition"]}@{r["model"]}' if multi else r["condition"]
        by[key].append(r)

    print(f"\nexperiment={directory}  runs={len(rows)}  api_fail={api_fail}  "
          f"budget_stopped={budget_stopped}  truncated={trunc}  usable={len(usable)}")
    print(f"{'condition':<26} {'n':>5} {'pass':>6} {'rate':>7} {'per-run CI':>16} "
          f"{'per-TASK CI':>16} {'flip':>6} {'in':>7} {'out':>7}")
    print("  per-run CI is precision about the tasks tested. per-TASK CI is what generalises.")
    print("-" * 112)
    conds = {}
    for cid in sorted(by):
        rs = by[cid]
        n = len(rs); k = sum(1 for r in rs if r["pass"])
        p, lo, hi = wilson(k, n)
        cells = defaultdict(list)
        for r in rs:
            cells[r["task"]].append(r)
        flips = sum(1 for c in cells.values()
                    if 0 < sum(1 for r in c if r["pass"]) < len(c))
        fr = flips / len(cells) if cells else 0
        ti = [r.get("in_tokens") or 0 for r in rs]
        to = [r.get("out_tokens") or 0 for r in rs]
        conds[cid] = {"n": n, "pass": k, "rate": round(p, 4), "ci_low": round(lo, 4),
                      "ci_high": round(hi, 4), "flip_rate": round(fr, 4),
                      "mean_in_tokens": round(sum(ti)/n, 1),
                      "mean_out_tokens": round(sum(to)/n, 1)}
        cp, clo, chi, ntask = cluster_ci(rs)
        conds[cid].update({"tasks": ntask, "clustered_rate": round(cp, 4),
                           "clustered_low": round(clo, 4), "clustered_high": round(chi, 4)})
        print(f"{cid:<26} {n:>5} {k:>6} {p:>6.1%} [{lo:>5.1%},{hi:>5.1%}] "
              f"[{clo:>5.1%},{chi:>5.1%}] {fr:>6.0%} {sum(ti)/n:>7.0f} {sum(to)/n:>7.0f}")

    out = {directory: {"model": ok[0]["model"] if ok else None, "total_runs": len(rows),
                       "api_failures": api_fail, "budget_stopped": budget_stopped,
                       "truncated": trunc, "conditions": conds}}
    with open(os.path.join(base, "metrics.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nwrote {os.path.join(base, 'metrics.json')}")
    return out


if __name__ == "__main__":
    summarize(sys.argv[1])
