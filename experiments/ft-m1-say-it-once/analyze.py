#!/usr/bin/env python3
"""FT-M1 analysis. Reads raw runs.jsonl, never mutates it. Emits metrics.json + a table."""
import json, math, os
from collections import defaultdict

HERE = os.path.dirname(__file__)
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
RUNS = os.path.join(HERE, "results", "runs.jsonl")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - m), min(1.0, c + m))


def main():
    rows = [json.loads(l) for l in open(RUNS) if l.strip()]
    ok = [r for r in rows if r.get("ok")]
    failed = len(rows) - len(ok)
    usable = [r for r in ok if not r.get("unparseable")]

    by_rep = defaultdict(list)
    for r in usable:
        by_rep[r["reps"]].append(r)

    cells = defaultdict(list)
    for r in usable:
        cells[(r["task"], r["reps"])].append(r)

    report = {
        "model": ok[0]["model"] if ok else None,
        "total_runs": len(rows), "api_failures": failed,
        "unparseable": sum(1 for r in ok if r.get("unparseable")),
        "conditions": {},
    }

    print(f"\nmodel={report['model']}  runs={len(rows)}  api_fail={failed}  "
          f"unparseable={report['unparseable']}\n")
    print(f"{'reps':>5} {'n':>4} {'compliant':>10} {'rate':>7} {'95% CI':>16} "
          f"{'flip':>6} {'out_tok':>8} {'docstr':>7}")
    print("-" * 72)

    for reps in sorted(by_rep):
        rs = by_rep[reps]
        n = len(rs)
        k = sum(1 for r in rs if r["compliant"])
        p, lo, hi = wilson(k, n)
        rep_cells = [v for (t, rp), v in cells.items() if rp == reps]
        flips = sum(1 for c in rep_cells
                    if 0 < sum(1 for r in c if r["compliant"]) < len(c))
        flip_rate = flips / len(rep_cells) if rep_cells else 0
        out = [r["out_tokens"] for r in rs if r.get("out_tokens")]
        mean_out = sum(out) / len(out) if out else 0
        doc = sum(1 for r in rs if r.get("docstring")) / n if n else 0
        report["conditions"][str(reps)] = {
            "n": n, "compliant": k, "rate": round(p, 4),
            "ci_low": round(lo, 4), "ci_high": round(hi, 4),
            "flip_rate": round(flip_rate, 4), "mean_out_tokens": round(mean_out, 1),
            "docstring_rate": round(doc, 4),
        }
        print(f"{reps:>5} {n:>4} {k:>10} {p:>6.1%} "
              f"[{lo:>5.1%},{hi:>5.1%}] {flip_rate:>6.0%} {mean_out:>8.0f} {doc:>6.0%}")

    print("\nper-task compliance by repetition")
    tasks = sorted({t for t, _ in cells})
    reps_sorted = sorted(by_rep)
    print(f"{'task':<18}" + "".join(f"{r:>7}" for r in reps_sorted))
    for t in tasks:
        line = f"{t:<18}"
        for rp in reps_sorted:
            c = cells.get((t, rp), [])
            line += f"{(sum(1 for r in c if r['compliant']) / len(c)):>6.0%} " if c else "     - "
        print(line)

    with open(os.path.join(HERE, "results", "metrics.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print("\nwrote results/metrics.json")


if __name__ == "__main__":
    main()
