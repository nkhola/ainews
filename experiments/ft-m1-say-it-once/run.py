#!/usr/bin/env python3
"""FT-M1 "Say It Once" — does repeating a system-prompt constraint improve compliance?

Runs a (task x repetition x trial) matrix against Gemini on Vertex and writes
one JSON line per run. Raw output is append-only; analysis is a separate step.
"""
import io, json, os, re, sys, time, tokenize, random
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import google.auth
from google.auth.transport.requests import Request

CONSTRAINTS = {
    "no_comments": "Do not include any comments in the code.",
    "single_quotes": "Use only single-quoted strings. Never use double quotes.",
    "no_docstring": "Do not include a docstring.",
    "no_type_hints": "Do not use type hints or annotations.",
}
CONSTRAINT_ID = os.environ.get("CONSTRAINT_ID", "no_comments")
CONSTRAINT = CONSTRAINTS[CONSTRAINT_ID]
REPETITIONS = [1, 2, 4, 8, 16]
TASKS = {
    "merge_intervals": "Write a Python function `merge_intervals(intervals)` that merges overlapping intervals.",
    "retry_backoff": "Write a Python function `retry_with_backoff(fn, attempts)` that retries a callable with exponential backoff.",
    "parse_semver": "Write a Python function `parse_semver(version)` that parses a semantic version string into a (major, minor, patch) tuple.",
    "chunk_iterable": "Write a Python function `chunk_iterable(items, size)` that yields fixed-size chunks from an iterable.",
    "lru_cache": "Write a Python function `lru_cache_decorator(maxsize)` implementing a simple LRU cache decorator.",
    "flatten_dict": "Write a Python function `flatten_dict(d, sep='.')` that flattens a nested dictionary.",
}

PROJECT = os.environ["VERTEX_PROJECT_ID"]
MODEL = (os.environ.get("LLM_MODEL") or "google/gemini-2.5-flash").split("/")[-1]
N = int(os.environ.get("N_TRIALS", "10"))
MAX_TOKENS = 900
URL = (f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/global/"
       f"publishers/google/models/{MODEL}:generateContent")

_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])


def token():
    if not _creds.valid:
        _creds.refresh(Request())
    return _creds.token


def system_prompt(reps):
    return "You are a Python code generator.\n" + "\n".join([CONSTRAINT] * reps)


def extract_code(text):
    """Prefer a fenced block; fall back to the whole response."""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def count_comments(code):
    """Exact comment count via Python's own tokenizer. None = unparseable."""
    try:
        toks = tokenize.generate_tokens(io.StringIO(code).readline)
        return sum(1 for t in toks if t.type == tokenize.COMMENT)
    except Exception:
        return None


def has_docstring(code):
    try:
        import ast as _ast
        tree = _ast.parse(code)
        return any(_ast.get_docstring(n) for n in _ast.walk(tree)
                   if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)))
    except Exception:
        return None


def violations(code, cid):
    """Exact, pre-declared checker per constraint. None = unparseable."""
    try:
        if cid == "no_comments":
            toks = tokenize.generate_tokens(io.StringIO(code).readline)
            return sum(1 for t in toks if t.type == tokenize.COMMENT)
        if cid == "single_quotes":
            toks = list(tokenize.generate_tokens(io.StringIO(code).readline))
            return sum(1 for t in toks if t.type == tokenize.STRING
                       and t.string.lstrip("rbfuRBFU").startswith('"'))
        import ast as _ast
        tree = _ast.parse(code)
        if cid == "no_docstring":
            return sum(1 for n in _ast.walk(tree)
                       if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))
                       and _ast.get_docstring(n))
        if cid == "no_type_hints":
            c = 0
            for n in _ast.walk(tree):
                if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    c += sum(1 for a in n.args.args if a.annotation is not None)
                    c += 1 if n.returns is not None else 0
                if isinstance(n, _ast.AnnAssign):
                    c += 1
            return c
    except Exception:
        return None
    return None


def call(task_id, reps, trial):
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt(reps)}]},
        "contents": [{"role": "user", "parts": [{"text": TASKS[task_id]}]}],
        "generationConfig": {"maxOutputTokens": MAX_TOKENS},
    }
    last = None
    for attempt in range(5):
        try:
            r = requests.post(URL, json=body, timeout=120,
                              headers={"Authorization": f"Bearer {token()}"})
            if r.status_code in (429, 503):
                raise RuntimeError(f"capacity {r.status_code}")
            r.raise_for_status()
            j = r.json()
            parts = j["candidates"][0]["content"].get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            usage = j.get("usageMetadata", {})
            code = extract_code(text)
            ncom = violations(code, CONSTRAINT_ID)
            return {
                "task": task_id, "reps": reps, "trial": trial, "model": MODEL,
                "constraint": CONSTRAINT_ID, "ok": True, "violations": ncom,
                "text_head": text[:500],
                "compliant": (ncom == 0) if ncom is not None else None,
                "unparseable": ncom is None,
                "docstring": has_docstring(code),
                "in_tokens": usage.get("promptTokenCount"),
                "out_tokens": usage.get("candidatesTokenCount"),
                "chars": len(text), "ts": time.time(),
            }
        except Exception as e:
            last = str(e)[:200]
            time.sleep(2 * (attempt + 1) + random.random())
    return {"task": task_id, "reps": reps, "trial": trial, "model": MODEL,
            "constraint": CONSTRAINT_ID, "ok": False, "error": last, "ts": time.time()}


def main():
    jobs = [(t, r, i) for t in TASKS for r in REPETITIONS for i in range(N)]
    random.shuffle(jobs)  # order randomised so drift cannot align with a condition
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"runs_{CONSTRAINT_ID}.jsonl")
    print(f"model={MODEL} constraint={CONSTRAINT_ID} jobs={len(jobs)}", flush=True)
    done = 0
    with open(out_path, "w") as fh, ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(call, *j): j for j in jobs}
        for f in as_completed(futs):
            rec = f.result()
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
