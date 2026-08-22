#!/usr/bin/env python3
"""FT-02 "Where You Put It" — does arrangement of a repeated constraint matter?

Content is held constant across arms: every prompt has a fixed header plus exactly
SLOTS instruction lines. N of them are the constraint, the rest are fixed neutral
filler. Only the ORDER differs between arms.
"""
import io, json, os, random, re, time, tokenize
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import google.auth
from google.auth.transport.requests import Request

CONSTRAINT = "Use only single-quoted strings. Never use double quotes."
SLOTS = 16
FILLER = [
    "You write Python for a general engineering audience.",
    "Prefer standard library solutions where they exist.",
    "Aim for readable variable names.",
    "Keep each function focused on a single responsibility.",
    "Assume the caller has already validated obvious input types.",
    "Favor iteration over recursion when both read naturally.",
    "Do not import third-party packages.",
    "Return values rather than printing them.",
    "Raise informative exceptions on invalid input.",
    "Avoid global mutable state.",
    "Keep nesting depth shallow where you can.",
    "Use early returns to reduce branching.",
    "Prefer explicit conditionals over clever expressions.",
    "Handle the empty input case.",
    "Avoid premature optimization.",
    "Write code that a reviewer can scan quickly.",
]
ARRANGEMENTS = ["clustered", "spread", "bookend"]
REPS = [2, 4, 8]
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
N = int(os.environ.get("N_TRIALS", "30"))
URL = (f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/global/"
       f"publishers/google/models/{MODEL}:generateContent")
_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])


def token():
    if not _creds.valid:
        _creds.refresh(Request())
    return _creds.token


def build_lines(reps, arrangement):
    """Identical content in every arm; only the order changes."""
    if reps == 0:
        return FILLER[:SLOTS]
    fill = FILLER[:SLOTS - reps]
    # "single" is the reps=1 baseline, where arrangement has no meaning.
    if arrangement in ("clustered", "single"):
        return [CONSTRAINT] * reps + fill
    if arrangement == "bookend":
        head = reps // 2
        return [CONSTRAINT] * head + fill + [CONSTRAINT] * (reps - head)
    if arrangement == "spread":
        out, step = [], SLOTS / reps
        c_at = {int(i * step) for i in range(reps)}
        fi = 0
        for i in range(SLOTS):
            if i in c_at:
                out.append(CONSTRAINT)
            else:
                out.append(fill[fi]); fi += 1
        return out
    raise ValueError(arrangement)


def system_prompt(reps, arrangement):
    return "You are a Python code generator.\n" + "\n".join(build_lines(reps, arrangement))


def extract_code(text):
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def violations(code):
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(code).readline))
        return sum(1 for t in toks if t.type == tokenize.STRING
                   and t.string.lstrip("rbfuRBFU").startswith('"'))
    except Exception:
        return None


def call(task_id, reps, arrangement, trial):
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt(reps, arrangement)}]},
        "contents": [{"role": "user", "parts": [{"text": TASKS[task_id]}]}],
        "generationConfig": {"maxOutputTokens": 2400, "thinkingConfig": {"thinkingBudget": 0}},
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
            cand = j["candidates"][0]
            finish = cand.get("finishReason")
            text = "".join(p.get("text", "") for p in cand["content"].get("parts", []))
            usage = j.get("usageMetadata", {})
            code = extract_code(text)
            v = violations(code)
            return {
                "task": task_id, "reps": reps, "arrangement": arrangement, "trial": trial,
                "model": MODEL, "ok": True, "violations": v,
                "truncated": finish not in ("STOP", None), "finish": finish,
                "text_head": text[:1200],
                "in_tokens": usage.get("promptTokenCount"),
                "out_tokens": usage.get("candidatesTokenCount"),
                "thought_tokens": usage.get("thoughtsTokenCount", 0),
                "ts": time.time(),
            }
        except Exception as e:
            last = str(e)[:200]
            time.sleep(2 * (attempt + 1) + random.random())
    return {"task": task_id, "reps": reps, "arrangement": arrangement, "trial": trial,
            "model": MODEL, "ok": False, "error": last, "ts": time.time()}


def validate(jobs):
    """Build every prompt in the matrix before spending a cent. A label this function
    cannot render is a crash 1,900 calls deep otherwise."""
    for t, reps, arr, _ in jobs:
        lines = build_lines(reps, arr)
        assert len(lines) == SLOTS, f"{arr} reps={reps}: {len(lines)} lines, expected {SLOTS}"
        got = sum(1 for l in lines if l == CONSTRAINT)
        assert got == reps, f"{arr} reps={reps}: {got} copies present"
    print(f"validated {len(jobs)} prompts, all {SLOTS} lines with correct copy counts", flush=True)


def main():
    jobs = []
    for t in TASKS:
        for i in range(N):
            jobs.append((t, 0, "control", i))          # no-constraint control
            jobs.append((t, 1, "single", i))           # arrangement-free baseline
            for a in ARRANGEMENTS:
                for r in REPS:
                    jobs.append((t, r, a, i))
    validate(jobs)
    random.shuffle(jobs)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "runs.jsonl")
    print(f"model={MODEL} jobs={len(jobs)}", flush=True)
    done = 0
    with open(out_path, "w") as fh, ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(call, *j) for j in jobs]
        for f in as_completed(futs):
            fh.write(json.dumps(f.result()) + "\n"); fh.flush()
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
