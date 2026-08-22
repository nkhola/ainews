#!/usr/bin/env python3
"""FT-03 "Phrasing Cost" — do semantically equivalent phrasings change what you pay?

The request text is byte-identical in every arm. Only the wrapper around it changes:
terse, polite, verbose, step-by-step-requesting, role-framed, and so on. The dependent
variable is tokens, which the harness records on every call; this module only supplies
the shape of the prompt and a cheap mechanical check that a usable function came back.

Deliberately NO output-format instruction. Real requests do not carry one, and format
drift under a wrapper is part of what is being measured.
"""
import ast
import re

NAME = "ft-03-phrasing-cost"
MODEL = "gemini-2.5-flash"
BUDGET_USD = 3.0

# Held constant in every arm so the wrapper is the only variable. Neutral about
# length, format, and effort.
SYSTEM = "You are a helpful coding assistant."

# Ten wrappers around one identical request. "{req}" is substituted literally
# (str.replace, not str.format) so nothing in a task text can be read as a field.
CONDITIONS = [
    {
        "id": "bare",
        "family": "control",
        "template": "{req}",
    },
    {
        "id": "terse",
        "family": "short",
        "template": "{req}\nCode only.",
    },
    {
        "id": "be_concise",
        "family": "short",
        "template": "{req}\nBe concise.",
    },
    {
        "id": "polite",
        "family": "social",
        "template": (
            "Hi! Would you mind helping me with something? {req} "
            "Thank you so much, I really appreciate it."
        ),
    },
    {
        "id": "chatty",
        "family": "social",
        "template": (
            "hey so I've been going round in circles on this one for a while and I "
            "figured I'd just ask instead of banging my head against it any longer. "
            "{req} anyway thanks, this would save me a bunch of time"
        ),
    },
    {
        "id": "verbose",
        "family": "long",
        "template": (
            "I am working on a Python codebase and I have run into a piece of "
            "functionality that I need implemented. I would like to describe the "
            "requirement to you in full so that there is no ambiguity about what is "
            "being asked for, and then I would like you to provide an implementation "
            "of it. Here is the requirement, stated as clearly as I can state it. "
            "{req} That is the whole of the requirement. Please provide the "
            "implementation."
        ),
    },
    {
        "id": "stepwise",
        "family": "effort",
        "template": (
            "Work through this step by step before you answer, then give me the "
            "implementation.\n\n{req}"
        ),
    },
    {
        "id": "role",
        "family": "effort",
        "template": (
            "You are a senior Python engineer with fifteen years of production "
            "experience. {req}"
        ),
    },
    {
        "id": "urgent",
        "family": "effort",
        "template": (
            "IMPORTANT: this is going straight into production and it has to be "
            "right. {req}"
        ),
    },
    {
        "id": "spec_form",
        "family": "structured",
        "template": (
            "REQUIREMENT\n{req}\n\nDELIVERABLE\nA single Python function."
        ),
    },
]

# The same six functions as FT-01 and FT-02, so token counts are comparable across
# the series. Request strings are copied verbatim from FT-02.
TASKS = {
    "merge_intervals": {
        "func": "merge_intervals",
        "req": ("Write a Python function `merge_intervals(intervals)` that merges "
                "overlapping intervals."),
    },
    "retry_backoff": {
        "func": "retry_with_backoff",
        "req": ("Write a Python function `retry_with_backoff(fn, attempts)` that "
                "retries a callable with exponential backoff."),
    },
    "parse_semver": {
        "func": "parse_semver",
        "req": ("Write a Python function `parse_semver(version)` that parses a "
                "semantic version string into a (major, minor, patch) tuple."),
    },
    "chunk_iterable": {
        "func": "chunk_iterable",
        "req": ("Write a Python function `chunk_iterable(items, size)` that yields "
                "fixed-size chunks from an iterable."),
    },
    "lru_cache": {
        "func": "lru_cache_decorator",
        "req": ("Write a Python function `lru_cache_decorator(maxsize)` implementing "
                "a simple LRU cache decorator."),
    },
    "flatten_dict": {
        "func": "flatten_dict",
        "req": ("Write a Python function `flatten_dict(d, sep='.')` that flattens a "
                "nested dictionary."),
    },
}

_FENCE = re.compile(r"```(?:python|py|python3)?[ \t]*\r?\n(.*?)```", re.DOTALL)


def _fenced_blocks(text):
    """Every fenced block, longest first. Empty list when the model wrote no fence."""
    try:
        return sorted((m for m in _FENCE.findall(text) if m.strip()),
                      key=len, reverse=True)
    except Exception:
        return []


def _defines(code, func):
    try:
        tree = ast.parse(code)
    except Exception:
        return False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func:
            return True
    return False


def _extract_code(text, func):
    """Prefer the first fenced block that actually defines the target function;
    fall back to the longest fenced block; fall back to the raw text."""
    blocks = _fenced_blocks(text)
    for b in blocks:
        if _defines(b, func):
            return b
    if blocks:
        return blocks[0]
    return text or ""


def _code_lines(code):
    n = 0
    for raw in code.splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            n += 1
    return n


def build_request(task_id, task, cond):
    user = cond["template"].replace("{req}", task["req"])
    return {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": 2400,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }


def verify(text, task_id, task, cond):
    """Cheap mechanical check. Cost is the real dependent variable; this only
    establishes that the arm still produced a usable answer, and records how
    long that answer was."""
    try:
        if not isinstance(text, str) or not text.strip():
            return {"pass": None, "chars": 0, "lines": 0, "fenced": False,
                    "reason": "empty_output"}
        chars = len(text)
        blocks = _fenced_blocks(text)
        code = _extract_code(text, task["func"])
        lines = _code_lines(code)
        try:
            ast.parse(code)
        except SyntaxError:
            return {"pass": False, "chars": chars, "lines": lines,
                    "fenced": bool(blocks), "reason": "syntax_error"}
        except Exception:
            return {"pass": False, "chars": chars, "lines": lines,
                    "fenced": bool(blocks), "reason": "unparseable"}
        found = _defines(code, task["func"])
        return {"pass": bool(found), "chars": chars, "lines": lines,
                "fenced": bool(blocks), "reason": "" if found else "missing_func"}
    except Exception as e:
        return {"pass": None, "chars": 0, "lines": 0, "fenced": False,
                "reason": "verify:" + type(e).__name__}
