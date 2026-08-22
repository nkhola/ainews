#!/usr/bin/env python3
"""FT-11 "Conflicting Orders" — when two instructions genuinely conflict, which wins?

Every prompt carries two rules that cannot both be satisfied. Content is held constant
inside a conflict pair; the arms move the rules around. What varies is which rule comes
first, whether the pair is adjacent or split top-to-bottom, and which rule gets a second
copy. The question is whether recency, primacy, or repetition decides.

Rule A is arbitrary but fixed per conflict pair, and `pass` means rule A was obeyed.
That is a labelling convention, not a value judgment: neither rule is "correct".
"""
import ast, io, re, tokenize

NAME = "ft-11-conflicting-orders"
MODEL = "gemini-2.5-flash"
BUDGET_USD = 3.0

SLOTS = 10          # every arm emits exactly 10 instruction lines

FILLER = [
    "You write Python for a general engineering audience.",
    "Prefer the standard library where it does the job.",
    "Use descriptive variable names.",
    "Return values rather than printing them.",
    "Keep each function focused on a single responsibility.",
    "Avoid global mutable state.",
    "Do not import third-party packages.",
    "Assume the caller passes the documented types.",
]

# ---------------------------------------------------------------- conflict pairs
PAIRS = {
    "quotes": {
        "a": "Use only single-quoted strings. Never use a double quote.",
        "b": "Use only double-quoted strings. Never use a single quote.",
    },
    "comments": {
        "a": "Write no comments at all: no inline comments and no docstrings.",
        "b": "Explain each step with an inline comment, and give every function a docstring.",
    },
    "length": {
        "a": "The complete code you output must be at most five lines, counting the def line.",
        "b": ("Add full error handling: validate every argument and raise a specific exception "
              "for each distinct failure mode."),
    },
}

# ---------------------------------------------------------------- arms
# layout names describe position only. `ab_top` / `ba_top` are the adjacent pair;
# `a_top_b_bot` / `b_top_a_bot` are the split pair; `a_twice` / `b_twice` add a second
# copy of one rule, trading away one filler line so the block stays 10 lines long.
CONDITIONS = [
    {"id": "ab_adjacent",   "layout": "ab_top",      "first": "A", "reps_a": 1, "reps_b": 1},
    {"id": "ba_adjacent",   "layout": "ba_top",      "first": "B", "reps_a": 1, "reps_b": 1},
    {"id": "a_top_b_bottom", "layout": "a_top_b_bot", "first": "A", "reps_a": 1, "reps_b": 1},
    {"id": "b_top_a_bottom", "layout": "b_top_a_bot", "first": "B", "reps_a": 1, "reps_b": 1},
    {"id": "a_twice_b_once", "layout": "a_twice",     "first": "A", "reps_a": 2, "reps_b": 1},
    {"id": "b_twice_a_once", "layout": "b_twice",     "first": "B", "reps_a": 1, "reps_b": 2},
]

# ---------------------------------------------------------------- tasks
# Two tasks per conflict pair. The quote tasks are worded so that string literals are
# unavoidable; the length tasks are worded so that at least two failure modes exist.
TASKS = {
    "status_label": {
        "conflict": "quotes",
        "prompt": ("Write a Python function `status_label(code)` that maps the HTTP status "
                   "codes 200, 404 and 500 to the labels ok, not found and server error, "
                   "returning the label as a string and returning unknown for anything else."),
    },
    "slugify": {
        "conflict": "quotes",
        "prompt": ("Write a Python function `slugify(title)` that lowercases a title, replaces "
                   "runs of whitespace with a single hyphen, drops any character outside a-z, "
                   "0-9 and hyphen, and returns the string untitled when nothing is left."),
    },
    "binary_search": {
        "conflict": "comments",
        "prompt": ("Write a Python function `binary_search(items, target)` that returns the "
                   "index of target in a sorted list, or -1 when it is absent."),
    },
    "merge_intervals": {
        "conflict": "comments",
        "prompt": ("Write a Python function `merge_intervals(intervals)` that merges "
                   "overlapping intervals and returns the merged list."),
    },
    "safe_divide": {
        "conflict": "length",
        "prompt": ("Write a Python function `safe_divide(a, b)` that returns a divided by b."),
    },
    "read_port": {
        "conflict": "length",
        "prompt": ("Write a Python function `read_port(config)` that reads config['port'] and "
                   "returns it as an int."),
    },
}


# ---------------------------------------------------------------- prompt build
def build_lines(cond, a_rule, b_rule):
    f = FILLER
    layout = cond["layout"]
    if layout == "ab_top":
        lines = [a_rule, b_rule] + f[:8]
    elif layout == "ba_top":
        lines = [b_rule, a_rule] + f[:8]
    elif layout == "a_top_b_bot":
        lines = [a_rule] + f[:8] + [b_rule]
    elif layout == "b_top_a_bot":
        lines = [b_rule] + f[:8] + [a_rule]
    elif layout == "a_twice":
        lines = [a_rule] + f[:3] + [b_rule] + f[3:7] + [a_rule]
    elif layout == "b_twice":
        lines = [b_rule] + f[:3] + [a_rule] + f[3:7] + [b_rule]
    else:
        raise ValueError(layout)
    assert len(lines) == SLOTS, f"{layout}: {len(lines)} lines"
    assert lines.count(a_rule) == cond["reps_a"] and lines.count(b_rule) == cond["reps_b"]
    return lines


def build_request(task_id, task, cond):
    pair = PAIRS[task["conflict"]]
    system = ("You are a Python code generator. Follow every rule below.\n"
              + "\n".join(build_lines(cond, pair["a"], pair["b"])))
    return {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": task["prompt"]}]}],
        "generationConfig": {"maxOutputTokens": 2400,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }


# ---------------------------------------------------------------- verification
def extract_code(text):
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text or "", re.DOTALL)
    return m.group(1) if m else (text or "")


def _tokens(code):
    return list(tokenize.generate_tokens(io.StringIO(code).readline))


def _quotes(code):
    """Single vs double string literals. Triple-quoted strings are counted separately and
    excluded from both, because docstring quoting belongs to the comments pair."""
    toks = _tokens(code)
    n_single = n_double = n_triple = 0
    for t in toks:
        if t.type != tokenize.STRING:
            continue
        s = t.string.lstrip("rbfuRBFU")
        if s.startswith('"""') or s.startswith("'''"):
            n_triple += 1
        elif s.startswith("'"):
            n_single += 1
        elif s.startswith('"'):
            n_double += 1
    a_ok = n_single > 0 and n_double == 0
    b_ok = n_double > 0 and n_single == 0
    return a_ok, b_ok, {"n_single": n_single, "n_double": n_double, "n_triple": n_triple}


def _comments(code):
    """A obeyed: nothing at all. B obeyed: its full demand, at least one docstring and at
    least two inline comments. Partial compliance lands in `neither` on purpose."""
    n_comments = sum(1 for t in _tokens(code) if t.type == tokenize.COMMENT)
    tree = ast.parse(code)
    n_doc = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if ast.get_docstring(node):
                n_doc += 1
    a_ok = n_comments == 0 and n_doc == 0
    b_ok = n_comments >= 2 and n_doc >= 1
    return a_ok, b_ok, {"n_comments": n_comments, "n_docstrings": n_doc}


def _length(code):
    """A obeyed: at most five non-blank, non-comment-only lines. B obeyed: at least two
    distinct raise statements."""
    lines = [l for l in code.splitlines()
             if l.strip() and not l.strip().startswith("#")]
    tree = ast.parse(code)
    n_raises = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Raise))
    a_ok = len(lines) <= 5
    b_ok = n_raises >= 2
    return a_ok, b_ok, {"n_code_lines": len(lines), "n_raises": n_raises}


CHECKS = {"quotes": _quotes, "comments": _comments, "length": _length}


def verify(text, task_id, task, cond):
    """Mechanical only: tokenize and ast, never a model's opinion. `pass` = rule A obeyed.
    `obeyed` is A, B, neither, or both_impossible — the last meaning the model satisfied
    both rules, i.e. the conflict was escapable for that instance."""
    conflict = task.get("conflict")
    try:
        code = extract_code(text)
        a_ok, b_ok, sig = CHECKS[conflict](code)
        if a_ok and b_ok:
            obeyed = "both_impossible"
        elif a_ok:
            obeyed = "A"
        elif b_ok:
            obeyed = "B"
        else:
            obeyed = "neither"
        return {"pass": bool(a_ok), "obeyed": obeyed, "conflict": conflict,
                "a_ok": bool(a_ok), "b_ok": bool(b_ok), "parsed": True,
                "code_chars": len(code), **sig}
    except Exception as e:                      # unparseable output, never a crash
        return {"pass": None, "obeyed": None, "conflict": conflict, "parsed": False,
                "parse_error": f"{type(e).__name__}: {e}"[:200]}
