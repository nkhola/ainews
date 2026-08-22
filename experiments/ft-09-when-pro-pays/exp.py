#!/usr/bin/env python3
"""FT-09 "When Pro Pays" — at what task difficulty does a pricier model earn its price?

HOW THE MODEL IS VARIED (read this before dispatching)
------------------------------------------------------
The harness runs exactly ONE model per invocation: `core.run()` resolves the model as
`model arg -> LLM_MODEL_OVERRIDE env -> mod.MODEL`, and CONDITIONS are prompt variations
within that one model. So the model cannot be a condition.

This rig therefore declares a single no-op condition, `{"id": "default"}`, and the model
is swept by dispatching the SAME experiment once per model with a different
`model_override`. The sweep, in order:

    gemini-2.5-flash-lite     $0.10 / $0.40 per M tokens
    gemini-2.5-flash          $0.30 / $2.50
    gemini-2.5-pro            $1.25 / $10.00      (Pro-class; confirm the id first)

Run `python experiments/_harness/probe_models.py` before the sweep. It prints which ids
actually answer in this project, and the Pro-class id is whichever of `gemini-2.5-pro`,
`gemini-3.1-pro` or `gemini-3.1-pro-preview` comes back OK. Swap the id below into the
dispatch, not into MODEL.

Every dispatch writes to the same file, `results/runs.jsonl`. The operator renames it to
`results/runs_<model>.jsonl` before the next dispatch or the next run overwrites it.
Every record already carries a `model` field, so the final analysis groups on that.
(Note: `_harness/metrics.py` groups by CONDITION, and every arm here has the same
condition id, so it would merge all three models into one row. It is the wrong tool for
the final read; group by `model` and `difficulty` instead.)

THINKING IS HELD DOWN, NOT VARIED
---------------------------------
Thinking is FT-06's subject, not this one's, so it is pinned near zero here to isolate
base model capability. One asymmetry has to be declared: Pro-class models reject
`thinkingBudget: 0` and enforce a floor, so the Pro arm runs at the 128-token floor while
the Flash arms run at 0. That is a real confound and it is named in spec.md rather than
hidden. It biases in Pro's favour, so a Pro loss is still a clean result.

Verification is mechanical: extract the fenced code, exec it in a restricted namespace,
call the function against fixed assertions, count passes. No model grades anything.
"""
import builtins as _builtins
import os
import re
import sys
import textwrap
import time

NAME = "ft-09-when-pro-pays"
MODEL = "gemini-2.5-flash"          # default arm; swept via LLM_MODEL_OVERRIDE
BUDGET_USD = 4.0                    # per dispatch, not for the whole sweep

MAX_OUTPUT_TOKENS = 8192            # generous headroom; thinking is billed against this
PRO_MIN_THINKING = 128              # Pro-class floor; 0 is rejected

# Single no-op condition. The model is the variable and it is swept across dispatches.
CONDITIONS = [{"id": "default"}]

PREAMBLE = (
    "You are a Python code generator. Return exactly one Python function in a single "
    "```python fenced block. Do not write anything outside the block. Use only the "
    "Python standard library."
)

# ---------------------------------------------------------------------------------
# Task set. The first eight are IDENTICAL to FT-06 ("thinking-budget"), verbatim, so the
# two experiments read against each other: FT-06's `think_0` arm on gemini-2.5-flash is
# the same cell as this rig's gemini-2.5-flash arm, which doubles as a replication check.
# Two extra hard tasks are appended here because this experiment needs resolution at the
# top of the difficulty ladder, which is where Pro is supposed to earn its money.
# Duplicated on purpose: no shared import, so neither rig can be broken by editing the
# other one.
# ---------------------------------------------------------------------------------
TASKS = {
    # ---- easy: string and list manipulation, no algorithm required ----
    "reverse_words": {
        "difficulty": "easy",
        "func": "reverse_words",
        "prompt": (
            "Write a Python function `reverse_words(s)` that returns the "
            "whitespace-separated words of `s` in reverse order, joined by single "
            "spaces. Collapse any run of whitespace to one space and strip leading and "
            "trailing whitespace. An empty or whitespace-only string returns an empty "
            "string."
        ),
        "asserts": [
            "reverse_words('the sky is blue') == 'blue is sky the'",
            "reverse_words('  hello   world  ') == 'world hello'",
            "reverse_words('one') == 'one'",
            "reverse_words('') == ''",
            "reverse_words('   ') == ''",
            "reverse_words('a b  c   d') == 'd c b a'",
        ],
    },
    "dedupe_preserve_order": {
        "difficulty": "easy",
        "func": "dedupe_preserve_order",
        "prompt": (
            "Write a Python function `dedupe_preserve_order(items)` that returns a new "
            "list containing the elements of `items` with duplicates removed, keeping "
            "the first occurrence of each and preserving the original order. All "
            "elements are hashable. Do not modify the input list."
        ),
        "asserts": [
            "dedupe_preserve_order([1, 2, 1, 3, 2, 4]) == [1, 2, 3, 4]",
            "dedupe_preserve_order([]) == []",
            "dedupe_preserve_order(['a', 'b', 'a', 'a', 'c']) == ['a', 'b', 'c']",
            "dedupe_preserve_order([3, 3, 3]) == [3]",
            "dedupe_preserve_order([1, '1', 1]) == [1, '1']",
            "(lambda src: [dedupe_preserve_order(src), src][1] == [1, 1, 2])([1, 1, 2])",
        ],
    },
    "char_frequency": {
        "difficulty": "easy",
        "func": "char_frequency",
        "prompt": (
            "Write a Python function `char_frequency(s)` that returns a dict mapping "
            "each character in `s` to the number of times it appears. Ignore all "
            "whitespace characters. Treat uppercase and lowercase as the same character "
            "and use the lowercase form as the key. Characters that do not appear must "
            "not be keys."
        ),
        "asserts": [
            "char_frequency('aA b') == {'a': 2, 'b': 1}",
            "char_frequency('') == {}",
            "char_frequency('   ') == {}",
            "char_frequency('Hello') == {'h': 1, 'e': 1, 'l': 2, 'o': 1}",
            "char_frequency('aaa') == {'a': 3}",
            "char_frequency('Mississippi') == {'m': 1, 'i': 4, 's': 4, 'p': 2}",
        ],
    },

    # ---- medium: needs an algorithm or careful edge cases ----
    "merge_intervals": {
        "difficulty": "medium",
        "func": "merge_intervals",
        "prompt": (
            "Write a Python function `merge_intervals(intervals)` that merges "
            "overlapping intervals. `intervals` is a list of `[start, end]` pairs in "
            "arbitrary order with start <= end. Return a new list of merged "
            "`[start, end]` pairs sorted by start. Intervals that only touch at an "
            "endpoint, such as [1, 2] and [2, 3], count as overlapping and must be "
            "merged. Do not modify the input."
        ),
        "asserts": [
            "[list(x) for x in merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]])] == [[1, 6], [8, 10], [15, 18]]",
            "[list(x) for x in merge_intervals([[1, 4], [4, 5]])] == [[1, 5]]",
            "[list(x) for x in merge_intervals([])] == []",
            "[list(x) for x in merge_intervals([[5, 6], [1, 2]])] == [[1, 2], [5, 6]]",
            "[list(x) for x in merge_intervals([[1, 10], [2, 3], [4, 5]])] == [[1, 10]]",
            "[list(x) for x in merge_intervals([[1, 4], [0, 4]])] == [[0, 4]]",
        ],
    },
    "parse_duration": {
        "difficulty": "medium",
        "func": "parse_duration",
        "prompt": (
            "Write a Python function `parse_duration(s)` that parses a duration string "
            "into an integer number of seconds. The string is a sequence of one or more "
            "`<digits><unit>` groups where unit is `h`, `m`, or `s`; each unit appears "
            "at most once and units always appear in the order h, m, s. For example "
            "'1h30m' is 5400, '45s' is 45, '2h' is 7200, '1h2m3s' is 3723. Return None "
            "for any string that does not match this form, including the empty string."
        ),
        "asserts": [
            "parse_duration('1h30m') == 5400",
            "parse_duration('45s') == 45",
            "parse_duration('2h') == 7200",
            "parse_duration('1h2m3s') == 3723",
            "parse_duration('90m') == 5400",
            "parse_duration('') is None",
            "parse_duration('30x') is None",
            "parse_duration('1m2h') is None",
        ],
    },
    "flatten_dict": {
        "difficulty": "medium",
        "func": "flatten_dict",
        "prompt": (
            "Write a Python function `flatten_dict(d, sep='.')` that flattens a nested "
            "dictionary. Each nested key path becomes a single key with the path "
            "components joined by `sep`. Values that are not dicts are kept unchanged. "
            "A value that is an empty dict contributes no key at all. All keys are "
            "strings. Do not modify the input."
        ),
        "asserts": [
            "flatten_dict({'a': 1, 'b': {'c': 2, 'd': {'e': 3}}}) == {'a': 1, 'b.c': 2, 'b.d.e': 3}",
            "flatten_dict({}) == {}",
            "flatten_dict({'a': {}}) == {}",
            "flatten_dict({'a': {'b': 1}}, sep='/') == {'a/b': 1}",
            "flatten_dict({'a': [1, 2]}) == {'a': [1, 2]}",
            "flatten_dict({'x': {'y': {'z': {}}}}) == {}",
            "flatten_dict({'a': 1, 'b': {}}) == {'a': 1}",
        ],
    },

    # ---- hard ----
    "max_profit_k": {
        "difficulty": "hard",
        "func": "max_profit_k",
        "prompt": (
            "Write a Python function `max_profit_k(prices, k)` that returns the maximum "
            "total profit obtainable from at most `k` buy-sell transactions on the daily "
            "price list `prices`. You must sell before buying again, so transactions may "
            "not overlap, and you may hold at most one share at a time. Return 0 when no "
            "profitable set of transactions exists, when `prices` is empty, or when `k` "
            "is 0."
        ),
        "asserts": [
            "max_profit_k([2, 4, 1], 2) == 2",
            "max_profit_k([3, 2, 6, 5, 0, 3], 2) == 7",
            "max_profit_k([], 2) == 0",
            "max_profit_k([1, 2, 3, 4, 5], 1) == 4",
            "max_profit_k([7, 6, 4, 3, 1], 3) == 0",
            "max_profit_k([1, 2, 3, 4, 5], 0) == 0",
            "max_profit_k([1, 2, 4, 2, 5, 7, 2, 4, 9, 0], 4) == 15",
            "max_profit_k([5], 3) == 0",
        ],
    },
    "evaluate_expression": {
        "difficulty": "hard",
        "func": "evaluate_expression",
        "prompt": (
            "Write a Python function `evaluate_expression(expr)` that evaluates a string "
            "arithmetic expression and returns an integer. The expression contains "
            "non-negative integers, the operators + - * /, parentheses, and optional "
            "whitespace anywhere. Multiplication and division bind tighter than addition "
            "and subtraction. Division is integer division that truncates toward zero, "
            "so '(0-7)/2' is -3, not -4. You may assume the expression is well formed "
            "and that no division by zero occurs. Implement the parsing yourself."
        ),
        "asserts": [
            "evaluate_expression('1 + 2 * 3') == 7",
            "evaluate_expression('(1+2)*3') == 9",
            "evaluate_expression('14/3') == 4",
            "evaluate_expression('(0-7)/2') == -3",
            "evaluate_expression('2*(3+(4-1))') == 12",
            "evaluate_expression('42') == 42",
            "evaluate_expression(' 10 - 2 - 3 ') == 5",
            "evaluate_expression('((2+3)*(4-1))/4') == 3",
        ],
    },

    # ---- hard, FT-09 only: extra resolution at the top of the ladder ----
    "min_window_substring": {
        "difficulty": "hard",
        "func": "min_window_substring",
        "prompt": (
            "Write a Python function `min_window_substring(s, t)` that returns the "
            "shortest contiguous substring of `s` containing every character of `t`, "
            "counting duplicates. If no such substring exists return the empty string. "
            "If several substrings tie for shortest, return the leftmost one. If `t` is "
            "empty return the empty string. Comparison is case sensitive."
        ),
        "asserts": [
            "min_window_substring('ADOBECODEBANC', 'ABC') == 'BANC'",
            "min_window_substring('a', 'a') == 'a'",
            "min_window_substring('a', 'aa') == ''",
            "min_window_substring('', 'a') == ''",
            "min_window_substring('ab', 'b') == 'b'",
            "min_window_substring('bba', 'ab') == 'ba'",
            "min_window_substring('aa', 'aa') == 'aa'",
            "min_window_substring('abc', '') == ''",
        ],
    },
    "count_decodings": {
        "difficulty": "hard",
        "func": "count_decodings",
        "prompt": (
            "Write a Python function `count_decodings(s)` that counts the ways to decode "
            "a digit string into letters, where '1' maps to A through '26' maps to Z. A "
            "'0' can never stand alone and never starts a two-digit code. Return 0 if "
            "the string cannot be decoded at all, and return 0 for the empty string. "
            "`s` contains only digits."
        ),
        "asserts": [
            "count_decodings('12') == 2",
            "count_decodings('226') == 3",
            "count_decodings('06') == 0",
            "count_decodings('') == 0",
            "count_decodings('10') == 1",
            "count_decodings('100') == 0",
            "count_decodings('2101') == 1",
            "count_decodings('11106') == 2",
            "count_decodings('27') == 1",
        ],
    },
}


def _effective_model():
    """Whatever core.run() will actually call. Env only; no network at import time."""
    return os.environ.get("LLM_MODEL_OVERRIDE") or MODEL


def _thinking_budget(model):
    """0 everywhere it is accepted; Pro-class models enforce a floor and reject 0."""
    return PRO_MIN_THINKING if "pro" in (model or "").lower() else 0


def build_request(task_id, task, cond):
    """Identical body for every model except the thinking floor Pro forces on us."""
    return {
        "contents": [{"role": "user",
                      "parts": [{"text": PREAMBLE + "\n\n" + task["prompt"]}]}],
        "generationConfig": {
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "thinkingConfig": {"thinkingBudget": _thinking_budget(_effective_model())},
        },
    }


# =================================================================================
# Mechanical verification. Nothing below asks a model anything.
# Byte-identical to FT-06's verifier so a pass in one rig means a pass in the other.
# =================================================================================

# `eval`, `exec`, `compile`, `open` and `input` are deliberately absent, which is what
# mechanically enforces "implement the parsing yourself" on evaluate_expression: a
# solution that reaches for eval() raises NameError and scores zero.
_SAFE_BUILTINS = (
    "abs all any ascii bin bool bytearray bytes callable chr classmethod complex dict "
    "divmod enumerate filter float format frozenset getattr hasattr hash hex id int "
    "isinstance issubclass iter len list map max min next object oct ord pow property "
    "range repr reversed round set setattr slice sorted staticmethod str sum super "
    "tuple type zip Ellipsis NotImplemented"
).split() + (
    "ArithmeticError AssertionError AttributeError BaseException EOFError Exception "
    "FloatingPointError GeneratorExit ImportError IndentationError IndexError KeyError "
    "LookupError MemoryError NameError NotImplementedError OverflowError RecursionError "
    "ReferenceError RuntimeError StopAsyncIteration StopIteration SyntaxError "
    "TypeError UnboundLocalError UnicodeError ValueError ZeroDivisionError"
).split()

_ALLOWED_MODULES = {
    "__future__", "abc", "array", "bisect", "collections", "copy", "dataclasses",
    "decimal", "enum", "fractions", "functools", "heapq", "itertools", "json", "math",
    "numbers", "operator", "random", "re", "statistics", "string", "textwrap", "types",
    "typing", "unicodedata",
}

_EXEC_SECONDS = 5.0     # wall clock allowed for defining the module
_CALL_SECONDS = 3.0     # wall clock allowed per assertion
_TOTAL_SECONDS = 8.0    # wall clock allowed for the whole assertion run

# Fences are matched at line start with any info string, so that the CLOSING fence of a
# non-python block cannot be mistaken for the OPENING fence of the next one.
_FENCED = re.compile(r"^[ \t]*```([A-Za-z0-9_.+-]*)[ \t]*\r?\n(.*?)^[ \t]*```",
                     re.DOTALL | re.M)
_UNCLOSED = re.compile(r"^[ \t]*```([A-Za-z0-9_.+-]*)[ \t]*\r?\n(.*)", re.DOTALL | re.M)
_PY_LANGS = ("", "python", "py", "python3")


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] not in _ALLOWED_MODULES:
        raise ImportError("import of %r is not allowed in the sandbox" % name)
    return __import__(name, globals, locals, fromlist, level)


def _sandbox():
    """A fresh namespace per verification. __name__ is not '__main__', so any demo
    block the model appended under `if __name__ == '__main__':` does not execute."""
    bi = {n: getattr(_builtins, n) for n in _SAFE_BUILTINS if hasattr(_builtins, n)}
    bi["__import__"] = _guarded_import
    bi["__build_class__"] = _builtins.__build_class__
    bi["print"] = lambda *a, **k: None
    return {"__builtins__": bi, "__name__": "ft_sandbox", "__doc__": None}


def _guarded(fn, seconds):
    """Run fn() under a wall-clock guard. Returns (ok, value_or_error_text).

    sys.settrace is per-thread, and the harness calls verify() from a worker thread, so
    this only slows the verification it is guarding. It exists because a wrong DP answer
    is often an infinite loop, and one hung worker would stall the whole matrix.
    """
    deadline = time.monotonic() + seconds
    def trace(frame, event, arg):
        if time.monotonic() > deadline:
            raise TimeoutError("sandbox wall-clock limit exceeded")
        return trace
    try:
        sys.settrace(trace)
        return True, fn()
    except BaseException as e:                      # noqa: BLE001 - must never escape
        return False, ("%s: %s" % (type(e).__name__, e))[:200]
    finally:
        sys.settrace(None)


def _extract_code(text, func):
    """Prefer the python block that actually defines the target function."""
    text = text or ""
    blocks = [(lang.lower(), body) for lang, body in _FENCED.findall(text)]
    if not blocks:
        m = _UNCLOSED.search(text)          # truncated mid-block
        if m:
            blocks = [(m.group(1).lower(), m.group(2))]
        elif "def " in text:                # unfenced code
            blocks = [("", text)]
    want = re.compile(r"^[ \t]*def[ \t]+%s[ \t]*\(" % re.escape(func), re.M)
    py = [b for lang, b in blocks if lang in _PY_LANGS]
    for b in py:                            # python block defining the target
        if want.search(b):
            return b
    for _, b in blocks:                     # any block defining the target
        if want.search(b):
            return b
    if py:
        return py[0]
    return blocks[0][1] if blocks else ""


def verify(text, task_id, task, cond):
    """Execute the generated function against fixed assertions. Never raises."""
    asserts = []
    try:
        asserts = list(task.get("asserts") or [])
        n = len(asserts)
        diff = task.get("difficulty")
        base = {"n_passed": 0, "n_asserts": n, "difficulty": diff}

        # dedent, so a fence indented under a markdown bullet still compiles
        code = textwrap.dedent(_extract_code(text, task["func"]))
        if not code.strip():
            return {"pass": False, **base, "error": "no code block found"}

        ns = _sandbox()
        ok, err = _guarded(lambda: exec(code, ns), _EXEC_SECONDS)
        if not ok:
            return {"pass": False, **base, "error": "exec: %s" % err}

        fn = ns.get(task["func"])
        if not callable(fn):
            return {"pass": False, **base,
                    "error": "%s not defined" % task["func"]}

        n_passed = 0
        first_err = None
        exhausted = False
        started = time.monotonic()
        for expr in asserts:
            if time.monotonic() - started > _TOTAL_SECONDS:
                # A wrong DP answer is usually an infinite loop. Stop re-proving it.
                exhausted = True
                break
            ok, res = _guarded(lambda e=expr: eval(e, ns), _CALL_SECONDS)
            if ok and res is True:
                n_passed += 1
            elif first_err is None:
                first_err = expr if ok else "%s -> %s" % (expr, res)
        out = {"pass": n_passed == n and n > 0, "n_passed": n_passed,
               "n_asserts": n, "difficulty": diff}
        if first_err:
            out["first_failure"] = first_err[:200]
        if exhausted:
            out["error"] = "assertion time budget exhausted"
        return out
    except BaseException as e:                      # noqa: BLE001 - contract: no raise
        return {"pass": None, "n_passed": 0, "n_asserts": len(asserts),
                "difficulty": (task or {}).get("difficulty"),
                "error": ("verify: %s: %s" % (type(e).__name__, e))[:200]}
