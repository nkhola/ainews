#!/usr/bin/env python3
"""FT-02 analysis. Reads raw runs.jsonl, never mutates it."""
import json, math, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "results", "runs.jsonl")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - m), min(1.0, c + m))


def block(rows, label, out):
    usable = [r for r in rows if r.get("violations") is not None and not r.get("truncated")]
    if not usable:
        return
    n = len(usable)
    k = sum(1 for r in usable if r["violations"] == 0)
    p, lo, hi = wilson(k, n)
    cells = defaultdict(list)
    for r in usable:
        cells[r["task"]].append(r)
    flips = sum(1 for c in cells.values()
                if 0 < sum(1 for r in c if r["violations"] == 0) < len(c))
    fr = flips / len(cells) if cells else 0
    ot = [r["out_tokens"] for r in usable if r.get("out_tokens")]
    it = [r["in_tokens"] for r in usable if r.get("in_tokens")]
    print(f"{label:<22} {n:>5} {k:>6} {p:>7.1%} [{lo:>5.1%},{hi:>5.1%}] {fr:>6.0%} "
          f"{(sum(it)/len(it) if it else 0):>8.0f} {(sum(ot)/len(ot) if ot else 0):>8.0f}")
    out[label] = {"n": n, "compliant": k, "rate": round(p, 4),
                  "ci_low": round(lo, 4), "ci_high": round(hi, 4),
                  "flip_rate": round(fr, 4),
                  "mean_in_tokens": round(sum(it)/len(it) if it else 0, 1),
                  "mean_out_tokens": round(sum(ot)/len(ot) if ot else 0, 1)}


def main():
    rows = [json.loads(l) for l in open(RUNS) if l.strip()]
    ok = [r for r in rows if r.get("ok")]
    trunc = sum(1 for r in ok if r.get("truncated"))
    unpar = sum(1 for r in ok if r.get("violations") is None and not r.get("truncated"))
    print(f"\nmodel={ok[0]['model'] if ok else '?'}  runs={len(rows)}  "
          f"api_fail={len(rows)-len(ok)}  truncated={trunc}  unparseable={unpar}\n")
    print(f"{'condition':<22} {'n':>5} {'ok':>6} {'rate':>7} {'95% CI':>16} {'flip':>6} "
          f"{'in_tok':>8} {'out_tok':>8}")
    print("-" * 88)

    out = {}
    block([r for r in ok if r["arrangement"] == "control"], "0  no constraint", out)
    block([r for r in ok if r["arrangement"] == "single"], "1  (no arrangement)", out)
    for reps in (2, 4, 8):
        print("-" * 88)
        for arr in ("clustered", "spread", "bookend"):
            block([r for r in ok if r["arrangement"] == arr and r["reps"] == reps],
                  f"{reps}x {arr}", out)

    with open(os.path.join(HERE, "results", "metrics.json"), "w") as fh:
        json.dump({"ft02": {"model": ok[0]["model"] if ok else None,
                            "total_runs": len(rows), "truncated": trunc,
                            "conditions": out}}, fh, indent=2)
    print("\nwrote results/metrics.json")


if __name__ == "__main__":
    main()
