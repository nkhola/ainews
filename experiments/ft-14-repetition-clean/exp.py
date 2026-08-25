#!/usr/bin/env python3
"""FT-14: repetition, on tasks that are actually contested.

FT-01 ran six tasks and three of them complied 100% from a single mention, so the
effect had nowhere to show. The FT-13 pilot measured 22 candidates at one mention
and found compliance tracks one thing almost exactly: whether the model writes a
docstring, since a triple-quoted docstring is the only place double quotes survive.

These 11 tasks all landed between 17% and 83% in the pilot. Every one has room to
move in both directions, which is the whole point of choosing them this way rather
than by intuition.

Pre-registered: compliance rises with repetition on these tasks and the rise is
steeper than FT-01's, because none of the ceiling tasks are here to flatten it.
The per-task curves are the result; the average across tasks is a summary, not a
claim about tasks in general.
"""
import io, re, tokenize

NAME = "ft-14-repetition-clean"
MODEL = "gemini-2.5-flash"
BUDGET_USD = 6.0

CONSTRAINT = "Use only single-quoted strings. Never use double quotes."
REPS = [0, 1, 2, 4, 8, 16]

TASKS = {
    "validate_config":   "Write a Python function `validate_config(cfg)` that checks a config dict for required keys and raises ValueError with a descriptive message naming the missing key.",
    "parse_duration":    "Write a Python function `parse_duration(text)` that parses strings like '2h30m' or '45s' into seconds, raising ValueError with a helpful message on bad input.",
    "http_status_name":  "Write a Python function `http_status_name(code)` that maps common HTTP status codes to their reason phrases.",
    "group_by_extension":"Write a Python function `group_by_extension(paths)` that groups file paths into a dict keyed by lowercase extension.",
    "env_to_dict":       "Write a Python function `env_to_dict(text)` that parses KEY=value lines into a dict, ignoring blanks and comments.",
    "format_table":      "Write a Python function `format_table(rows)` that renders a list of dicts as an aligned plain-text table.",
    "humanize_bytes":    "Write a Python function `humanize_bytes(n)` that formats a byte count as a readable string like '1.5 MB'.",
    "slugify":           "Write a Python function `slugify(title)` that converts a title into a URL-safe slug.",
    "strip_html":        "Write a Python function `strip_html(text)` that removes HTML tags and collapses whitespace.",
    "parse_semver":      "Write a Python function `parse_semver(version)` that parses a semantic version string into a (major, minor, patch) tuple.",
    "lru_cache":         "Write a Python function `lru_cache_decorator(maxsize)` implementing a simple LRU cache decorator.",
}

CONDITIONS = [{"id": f"reps_{r:02d}", "reps": r} for r in REPS]


def build_request(task_id, task, cond):
    n = cond["reps"]
    sys_txt = "You are a Python code generator."
    if n:
        sys_txt += "\n" + "\n".join([CONSTRAINT] * n)
    return {
        "systemInstruction": {"parts": [{"text": sys_txt}]},
        "contents": [{"role": "user", "parts": [{"text": task}]}],
        "generationConfig": {"maxOutputTokens": 2400, "thinkingConfig": {"thinkingBudget": 0}},
    }


def _code(text):
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def verify(text, task_id, task, cond):
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(_code(text)).readline))
    except Exception:
        return {"pass": None}
    dq = [t.string for t in toks if t.type == tokenize.STRING
          and t.string.lstrip("rbfuRBFU").startswith('"')]
    triple = sum(1 for x in dq if x.lstrip('rbfuRBFU').startswith('"""'))
    return {"pass": len(dq) == 0, "violations": len(dq),
            "triple_quoted": triple, "single_line_dq": len(dq) - triple}
