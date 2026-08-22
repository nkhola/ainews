#!/usr/bin/env python3
"""Generic aggregation for any Field Test. Reads raw runs, never mutates them.

Usage: python _harness/metrics.py <experiment-dir>
"""
import json, math, os, sys, glob
from collections import defaultdict


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
    trunc = sum(1 for r in ok if r.get("truncated"))
    usable = [r for r in ok if r.get("pass") is not None and not r.get("truncated")]

    by = defaultdict(list)
    for r in usable:
        by[r["condition"]].append(r)

    print(f"\nexperiment={directory}  runs={len(rows)}  api_fail={len(rows)-len(ok)}  "
          f"truncated={trunc}  usable={len(usable)}")
    print(f"{'condition':<26} {'n':>5} {'pass':>6} {'rate':>7} {'95% CI':>16} {'flip':>6} "
          f"{'in':>7} {'out':>7}")
    print("-" * 92)
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
        print(f"{cid:<26} {n:>5} {k:>6} {p:>6.1%} [{lo:>5.1%},{hi:>5.1%}] {fr:>6.0%} "
              f"{sum(ti)/n:>7.0f} {sum(to)/n:>7.0f}")

    out = {directory: {"model": ok[0]["model"] if ok else None, "total_runs": len(rows),
                       "truncated": trunc, "conditions": conds}}
    with open(os.path.join(base, "metrics.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nwrote {os.path.join(base, 'metrics.json')}")
    return out


if __name__ == "__main__":
    summarize(sys.argv[1])
