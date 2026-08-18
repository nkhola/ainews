#!/usr/bin/env python3
"""FT-M1 analysis. Reads raw runs_*.jsonl, never mutates them."""
import glob, json, math, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - m), min(1.0, c + m))


def report_one(path, out):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    ok = [r for r in rows if r.get("ok")]
    usable = [r for r in ok if r.get("violations") is not None]
    cid = rows[0].get("constraint", "?")
    unpar = len(ok) - len(usable)

    by_rep, cells = defaultdict(list), defaultdict(list)
    for r in usable:
        by_rep[r["reps"]].append(r)
        cells[(r["task"], r["reps"])].append(r)

    print(f"\n### constraint={cid}  model={rows[0].get('model')}  runs={len(rows)}  "
          f"api_fail={len(rows)-len(ok)}  unparseable={unpar}")
    print(f"{'reps':>5} {'n':>4} {'ok':>4} {'rate':>7} {'95% CI':>16} {'flip':>6} {'viol/run':>9} {'out_tok':>8}")
    print("-" * 70)
    conds = {}
    for reps in sorted(by_rep):
        rs = by_rep[reps]
        n = len(rs)
        k = sum(1 for r in rs if r["violations"] == 0)
        p, lo, hi = wilson(k, n)
        rc = [v for (t, rp), v in cells.items() if rp == reps]
        flips = sum(1 for c in rc if 0 < sum(1 for r in c if r["violations"] == 0) < len(c))
        fr = flips / len(rc) if rc else 0
        mv = sum(r["violations"] for r in rs) / n if n else 0
        ot = [r["out_tokens"] for r in rs if r.get("out_tokens")]
        mo = sum(ot) / len(ot) if ot else 0
        conds[str(reps)] = {"n": n, "compliant": k, "rate": round(p, 4),
                            "ci_low": round(lo, 4), "ci_high": round(hi, 4),
                            "flip_rate": round(fr, 4), "viol_per_run": round(mv, 3),
                            "mean_out_tokens": round(mo, 1)}
        print(f"{reps:>5} {n:>4} {k:>4} {p:>6.1%} [{lo:>5.1%},{hi:>5.1%}] {fr:>6.0%} {mv:>9.2f} {mo:>8.0f}")

    tasks = sorted({t for t, _ in cells})
    reps_sorted = sorted(by_rep)
    if len(reps_sorted) > 1:
        print(f"\n{'task':<18}" + "".join(f"{r:>7}" for r in reps_sorted))
        for t in tasks:
            line = f"{t:<18}"
            for rp in reps_sorted:
                c = cells.get((t, rp), [])
                line += f"{(sum(1 for r in c if r['violations']==0)/len(c)):>6.0%} " if c else "     - "
            print(line)
    out[cid] = {"model": rows[0].get("model"), "total_runs": len(rows),
                "api_failures": len(rows) - len(ok), "unparseable": unpar,
                "conditions": conds}


def main():
    out = {}
    for p in sorted(glob.glob(os.path.join(HERE, "results", "runs_*.jsonl"))):
        report_one(p, out)
    with open(os.path.join(HERE, "results", "metrics.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print("\nwrote results/metrics.json")


if __name__ == "__main__":
    main()
