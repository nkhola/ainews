#!/usr/bin/env python3
"""FT-13 task calibration: find tasks where the single-quote rule is actually contested.

FT-01 used six tasks and three of them complied 100% of the time from a single
mention, which left the effect with nowhere to show. From the FT-01 raw data,
nearly every surviving violation was a triple-quoted docstring, so tasks that
invite more prose and more string literals should resist the rule harder.

This is a pilot, not a finding. One condition, the rule stated once. Keep the
tasks whose compliance lands between about 20% and 80%, because those are the
only ones where repetition has room to move the number in either direction.
"""
import io, re, tokenize

NAME = "ft-13-task-calibration"
MODEL = "gemini-2.5-flash"
BUDGET_USD = 4.0

CONSTRAINT = "Use only single-quoted strings. Never use double quotes."

# 22 candidates, deliberately biased toward string-heavy and prose-heavy work,
# since that is where FT-01's violations concentrated.
TASKS = {
    # error-message heavy
    "validate_config":   "Write a Python function `validate_config(cfg)` that checks a config dict for required keys and raises ValueError with a descriptive message naming the missing key.",
    "parse_duration":    "Write a Python function `parse_duration(text)` that parses strings like '2h30m' or '45s' into seconds, raising ValueError with a helpful message on bad input.",
    "check_password":    "Write a Python function `check_password(pw)` that returns a list of human-readable reasons a password is weak.",
    "http_status_name":  "Write a Python function `http_status_name(code)` that maps common HTTP status codes to their reason phrases.",
    # dict-with-string-keys heavy
    "group_by_extension":"Write a Python function `group_by_extension(paths)` that groups file paths into a dict keyed by lowercase extension.",
    "count_words":       "Write a Python function `count_words(text)` returning a dict of word to count, lowercased and stripped of punctuation.",
    "csv_to_dicts":      "Write a Python function `csv_to_dicts(lines)` that turns a list of CSV lines into a list of dicts using the first line as headers.",
    "env_to_dict":       "Write a Python function `env_to_dict(text)` that parses KEY=value lines into a dict, ignoring blanks and comments.",
    # formatting / f-string heavy
    "format_table":      "Write a Python function `format_table(rows)` that renders a list of dicts as an aligned plain-text table.",
    "humanize_bytes":    "Write a Python function `humanize_bytes(n)` that formats a byte count as a readable string like '1.5 MB'.",
    "pluralize":         "Write a Python function `pluralize(n, word)` that returns a phrase like '1 file' or '3 files'.",
    "render_greeting":   "Write a Python function `render_greeting(name, hour)` returning a greeting string appropriate to the time of day.",
    # text processing
    "slugify":           "Write a Python function `slugify(title)` that converts a title into a URL-safe slug.",
    "truncate_middle":   "Write a Python function `truncate_middle(s, width)` that shortens a string by replacing the middle with an ellipsis.",
    "strip_html":        "Write a Python function `strip_html(text)` that removes HTML tags and collapses whitespace.",
    "wrap_paragraph":    "Write a Python function `wrap_paragraph(text, width)` that hard-wraps a paragraph without breaking words.",
    # the FT-01 six, so the pilot is anchored to known values
    "merge_intervals":   "Write a Python function `merge_intervals(intervals)` that merges overlapping intervals.",
    "retry_backoff":     "Write a Python function `retry_with_backoff(fn, attempts)` that retries a callable with exponential backoff.",
    "parse_semver":      "Write a Python function `parse_semver(version)` that parses a semantic version string into a (major, minor, patch) tuple.",
    "chunk_iterable":    "Write a Python function `chunk_iterable(items, size)` that yields fixed-size chunks from an iterable.",
    "lru_cache":         "Write a Python function `lru_cache_decorator(maxsize)` implementing a simple LRU cache decorator.",
    "flatten_dict":      "Write a Python function `flatten_dict(d, sep='.')` that flattens a nested dictionary.",
}

CONDITIONS = [{"id": "stated_once"}]


def build_request(task_id, task, cond):
    return {
        "systemInstruction": {"parts": [{"text": "You are a Python code generator.\n" + CONSTRAINT}]},
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
