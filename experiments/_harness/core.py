#!/usr/bin/env python3
"""Field Test harness.

An experiment is a module declaring what to vary and how to check the answer.
Everything else (auth, matrix expansion, retries, token accounting, a hard budget
stop, raw JSONL output) lives here so experiments stay ~60 lines and stay uniform.

Experiment module contract
--------------------------
NAME        : str                       directory name, e.g. "ft-03-phrasing-cost"
MODEL       : str                       default model id (overridable by env LLM_MODEL_OVERRIDE)
BUDGET_USD  : float                     hard ceiling; the matrix aborts if exceeded
CONDITIONS  : list[dict]                each MUST have a unique "id"
TASKS       : dict[str, dict]           task payloads
build_request(task_id, task, cond) -> dict     a full generateContent body
verify(text, task_id, task, cond)  -> dict     MUST include {"pass": bool|None}

Anything verify() returns is written verbatim into the run record, so an experiment
can record whatever extra signal it wants.
"""
import json, os, random, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import google.auth
from google.auth.transport.requests import Request

# USD per 1M tokens (Vertex list, checked 2026-08-11). Used for the in-process
# budget guard; treat as planning figures, not billing truth.
PRICES = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash":      (0.30, 2.50),
    "gemini-3-flash":        (0.50, 3.00),
    "gemini-3.5-flash":      (1.50, 9.00),
    "gemini-3.6-flash":      (1.50, 7.50),
    "gemini-2.5-pro":        (1.25, 10.00),
    "gemini-3.1-pro":        (2.00, 12.00),
}
DEFAULT_PRICE = (1.50, 9.00)          # assume expensive when unknown

_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
_PROJECT = os.environ.get("VERTEX_PROJECT_ID")


def _token():
    if not _creds.valid:
        _creds.refresh(Request())
    return _creds.token


def _url(model):
    return (f"https://aiplatform.googleapis.com/v1/projects/{_PROJECT}/locations/global/"
            f"publishers/google/models/{model}:generateContent")


def price_of(model, tin, tout):
    pin, pout = next((v for k, v in PRICES.items() if model.startswith(k)), DEFAULT_PRICE)
    return tin / 1e6 * pin + tout / 1e6 * pout


class Budget:
    """Aborts a matrix mid-flight. GCP budget alerts only notify; this actually stops."""
    def __init__(self, cap):
        self.cap, self.spent, self.stopped = cap, 0.0, False

    def add(self, usd):
        self.spent += usd
        if self.spent > self.cap:
            self.stopped = True
        return self.stopped


def call_once(model, body, budget, timeout=180, attempts=5):
    last = None
    for i in range(attempts):
        if budget.stopped:
            return {"ok": False, "error": "budget stop"}
        try:
            r = requests.post(_url(model), json=body, timeout=timeout,
                              headers={"Authorization": f"Bearer {_token()}"})
            if r.status_code in (429, 503):
                raise RuntimeError(f"capacity {r.status_code}")
            r.raise_for_status()
            j = r.json()
            cand = (j.get("candidates") or [{}])[0]
            parts = (cand.get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts)
            u = j.get("usageMetadata", {})
            tin = u.get("promptTokenCount", 0) or 0
            tout = (u.get("candidatesTokenCount", 0) or 0) + (u.get("thoughtsTokenCount", 0) or 0)
            budget.add(price_of(model, tin, tout))
            return {"ok": True, "text": text, "finish": cand.get("finishReason"),
                    "in_tokens": tin, "out_tokens": u.get("candidatesTokenCount", 0),
                    "thought_tokens": u.get("thoughtsTokenCount", 0) or 0}
        except Exception as e:
            last = str(e)[:200]
            time.sleep(min(2 * (i + 1) + random.random(), 20))
    return {"ok": False, "error": last}


def run(mod, n_trials, out_path, max_workers=8, model=None):
    model = model or os.environ.get("LLM_MODEL_OVERRIDE") or mod.MODEL
    budget = Budget(getattr(mod, "BUDGET_USD", 5.0))
    ids = [c["id"] for c in mod.CONDITIONS]
    assert len(ids) == len(set(ids)), f"duplicate condition ids: {ids}"

    jobs = [(t, c, i) for t in mod.TASKS for c in mod.CONDITIONS for i in range(n_trials)]
    random.shuffle(jobs)                       # drift cannot align with a condition
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    print(f"experiment={mod.NAME} model={model} jobs={len(jobs)} "
          f"budget=${budget.cap:.2f}", flush=True)

    def one(task_id, cond, trial):
        task = mod.TASKS[task_id]
        rec = {"experiment": mod.NAME, "task": task_id, "condition": cond["id"],
               "trial": trial, "model": model, "ts": time.time()}
        try:
            body = mod.build_request(task_id, task, cond)
        except Exception as e:
            return {**rec, "ok": False, "error": f"build_request: {e}"[:200]}
        res = call_once(model, body, budget)
        if not res.get("ok"):
            return {**rec, "ok": False, "error": res.get("error")}
        truncated = res["finish"] not in ("STOP", None)
        out = {**rec, "ok": True, "truncated": truncated, "finish": res["finish"],
               "in_tokens": res["in_tokens"], "out_tokens": res["out_tokens"],
               "thought_tokens": res["thought_tokens"], "text_head": res["text"][:1200]}
        try:
            v = mod.verify(res["text"], task_id, task, cond) if not truncated else {"pass": None}
        except Exception as e:
            v = {"pass": None, "verify_error": str(e)[:200]}
        return {**out, **v}

    done = 0
    with open(out_path, "w") as fh, ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(one, *j) for j in jobs]
        for f in as_completed(futs):
            fh.write(json.dumps(f.result()) + "\n"); fh.flush()
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(jobs)}  spent≈${budget.spent:.2f}", flush=True)
    print(f"wrote {out_path}  runs={done}  spent≈${budget.spent:.2f}"
          f"{'  BUDGET STOP HIT' if budget.stopped else ''}", flush=True)
    return budget.spent


def load(directory):
    """Import an experiment module by directory name."""
    import importlib.util
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, directory, "exp.py")
    spec = importlib.util.spec_from_file_location(f"exp_{directory}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


if __name__ == "__main__":
    d = sys.argv[1]
    n = int(os.environ.get("N_TRIALS", "30"))
    m = load(d)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    run(m, n, os.path.join(here, d, "results", "runs.jsonl"))
