#!/usr/bin/env python3
"""Build every prompt in every experiment matrix locally, without calling the API.

A label the prompt builder cannot render is a crash a thousand calls deep otherwise.
Run this before dispatching anything.
"""
import os, sys, glob, importlib.util

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(directory):
    path = os.path.join(HERE, directory, "exp.py")
    spec = importlib.util.spec_from_file_location(f"v_{directory}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    ids = [c["id"] for c in m.CONDITIONS]
    assert len(ids) == len(set(ids)), f"{directory}: duplicate condition ids"
    n = 0
    for t, task in m.TASKS.items():
        for c in m.CONDITIONS:
            body = m.build_request(t, task, c)
            assert isinstance(body, dict) and "contents" in body, \
                f"{directory}/{t}/{c['id']}: build_request must return a generateContent body"
            n += 1
    # verifier must survive junk without throwing
    for c in m.CONDITIONS[:1]:
        for t, task in list(m.TASKS.items())[:1]:
            v = m.verify("```python\ndef f():\n    return 1\n```", t, task, c)
            assert "pass" in v, f"{directory}: verify() must return a 'pass' key"
    cells = len(m.TASKS) * len(m.CONDITIONS)
    print(f"  OK  {directory:<30} {len(m.TASKS):>2} tasks x {len(m.CONDITIONS):>2} conditions "
          f"= {cells:>3} cells, model={m.MODEL}, budget=${getattr(m,'BUDGET_USD',5.0):.2f}")
    return True


if __name__ == "__main__":
    targets = sys.argv[1:] or sorted(
        os.path.basename(os.path.dirname(p))
        for p in glob.glob(os.path.join(HERE, "ft-*", "exp.py")))
    bad = 0
    print(f"validating {len(targets)} experiment(s)\n")
    for d in targets:
        try:
            check(d)
        except Exception as e:
            bad += 1
            print(f"  FAIL {d}: {type(e).__name__}: {e}")
    print(f"\n{len(targets)-bad} ok, {bad} failing")
    sys.exit(1 if bad else 0)
