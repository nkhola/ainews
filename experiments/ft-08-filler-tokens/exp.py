#!/usr/bin/env python3
"""FT-08 "Filler Tokens" — does padding a prompt with empty tokens change quality?

The real request is byte-identical in every arm. What changes is how much semantically
empty material sits in front of it in the same user turn: nothing, or 50 / 200 / 800
nominal units of either repeated dots or neutral lorem-style sentences.

Correctness is measured by EXECUTION against a fixed assertion set, in a child process
with a restricted builtins dict, an import denylist, a per-assertion SIGALRM and a hard
parent-side timeout. No model grades anything.

Three of the six tasks (merge_intervals, rle_encode, balanced_brackets) are shared with
FT-04 with identical wordings and identical assertions, so the two experiments can be
read against each other.
"""
import ast
import json
import re
import subprocess
import sys

NAME = "ft-08-filler-tokens"
MODEL = "gemini-2.5-flash"
BUDGET_USD = 3.0

# Identical in every arm.
SYSTEM = ("You are a Python code generator. Reply with a single fenced Python code "
          "block containing the complete function and nothing else.")

# Twelve semantically empty but grammatical sentences. They assert nothing, constrain
# nothing, and mention no task. Cycled deterministically to reach a word target.
_LOREM_POOL = [
    "The document continues in the usual manner for a document of this kind.",
    "Various considerations apply here as they apply in comparable situations.",
    "It has generally been the case that matters proceed along these lines.",
    "The preceding remarks are offered in the spirit in which they were composed.",
    "Nothing in this passage is intended to bear on anything that follows it.",
    "Certain aspects remain broadly consistent with what one might otherwise expect.",
    "The arrangement described is neither unusual nor especially noteworthy.",
    "Observations of this general character have been recorded on prior occasions.",
    "The material set out above is presented purely for the sake of completeness.",
    "Such matters are ordinarily handled in whatever way they are ordinarily handled.",
    "There is little to add beyond what has already been stated in these terms.",
    "The foregoing is consistent with the general tenor of the surrounding text.",
]


def _dots(units):
    """Space-separated periods. Roughly one token per unit; the harness records the
    real promptTokenCount, so the actual cost is measured, not assumed."""
    return " ".join(["."] * units)


def _lorem(units):
    """Neutral sentences truncated to `units` words (~1.3 tokens per word)."""
    words = []
    i = 0
    while len(words) < units:
        words.extend(_LOREM_POOL[i % len(_LOREM_POOL)].split())
        i += 1
    return " ".join(words[:units])


def make_filler(kind, units):
    if kind == "none" or units <= 0:
        return ""
    if kind == "dots":
        return _dots(units)
    if kind == "lorem":
        return _lorem(units)
    raise ValueError("unknown filler kind: %r" % (kind,))


CONDITIONS = [
    {"id": "none", "kind": "none", "units": 0},
    {"id": "dots_50", "kind": "dots", "units": 50},
    {"id": "dots_200", "kind": "dots", "units": 200},
    {"id": "dots_800", "kind": "dots", "units": 800},
    {"id": "lorem_50", "kind": "lorem", "units": 50},
    {"id": "lorem_200", "kind": "lorem", "units": 200},
    {"id": "lorem_800", "kind": "lorem", "units": 800},
]

# Assertion format: [[arg, ...], expected].
# expected == {"__raises__": "ExceptionName"} means the call must raise that exception.
TASKS = {
    # --- shared verbatim with FT-04 -------------------------------------------------
    "merge_intervals": {
        "func": "merge_intervals",
        "prompt": (
            "Write a Python function merge_intervals(intervals). The argument is a "
            "list of [start, end] pairs which may be unsorted and may overlap. Return "
            "a new list of merged intervals sorted by start value. Intervals that "
            "touch at an endpoint, such as [1,4] and [4,5], count as overlapping and "
            "are merged into one. If the input list is empty, return an empty list."
        ),
        "asserts": [
            [[[[1, 3], [2, 6], [8, 10], [15, 18]]], [[1, 6], [8, 10], [15, 18]]],
            [[[[1, 4], [4, 5]]], [[1, 5]]],
            [[[]], []],
            [[[[5, 7], [1, 3]]], [[1, 3], [5, 7]]],
            [[[[1, 10], [2, 3]]], [[1, 10]]],
            [[[[1, 2]]], [[1, 2]]],
        ],
    },
    "rle_encode": {
        "func": "rle_encode",
        "prompt": (
            "Write a Python function rle_encode(s) that returns the run-length "
            "encoding of the string `s` as a string. Each consecutive run of an "
            "identical character becomes that character followed by the decimal "
            "length of the run, and runs of length one are included with an explicit "
            "count of 1. So rle_encode('aaabbc') returns 'a3b2c1' and "
            "rle_encode('xyz') returns 'x1y1z1'. An empty input string returns an "
            "empty string."
        ),
        "asserts": [
            [["aaabbc"], "a3b2c1"],
            [[""], ""],
            [["a"], "a1"],
            [["aabbaa"], "a2b2a2"],
            [["xyz"], "x1y1z1"],
            [["wwwwwwwwwwww"], "w12"],
        ],
    },
    "balanced_brackets": {
        "func": "balanced_brackets",
        "prompt": (
            "Write a Python function balanced_brackets(s) that returns a boolean "
            "indicating whether the round, square and curly brackets in the string "
            "`s` are balanced and correctly nested. Ignore every character that is "
            "not one of ( ) [ ] { }. So '([{}])' returns True, '(]' returns False "
            "and ')(' returns False. An empty string returns True."
        ),
        "asserts": [
            [["()"], True],
            [["([{}])"], True],
            [["(]"], False],
            [["((("], False],
            [[""], True],
            [["a(b)c[d]"], True],
            [[")("], False],
        ],
    },

    # --- harder three, added to keep the ceiling out of reach ------------------------
    "spiral_order": {
        "func": "spiral_order",
        "prompt": (
            "Write a Python function spiral_order(matrix) that takes a list of rows, "
            "each row a list of values forming a rectangular matrix, and returns a "
            "flat list of every element in clockwise spiral order starting at the "
            "top-left corner and moving right. For [[1,2,3],[4,5,6],[7,8,9]] the "
            "result is [1,2,3,6,9,8,7,4,5]. A matrix with a single row or a single "
            "column is handled correctly, and an empty matrix returns an empty list."
        ),
        "asserts": [
            [[[[1, 2, 3], [4, 5, 6], [7, 8, 9]]], [1, 2, 3, 6, 9, 8, 7, 4, 5]],
            [[[[1, 2], [3, 4]]], [1, 2, 4, 3]],
            [[[]], []],
            [[[[1]]], [1]],
            [[[[1, 2, 3, 4]]], [1, 2, 3, 4]],
            [[[[1], [2], [3]]], [1, 2, 3]],
            [[[[1, 2, 3], [4, 5, 6]]], [1, 2, 3, 6, 5, 4]],
        ],
    },
    "evaluate_rpn": {
        "func": "evaluate_rpn",
        "prompt": (
            "Write a Python function evaluate_rpn(tokens) that evaluates a list of "
            "string tokens in reverse Polish notation and returns the integer result. "
            "Tokens are either the operators '+', '-', '*' and '/' or integer "
            "literals, which may be negative. Division is integer division that "
            "truncates toward zero, so ['-3','2','/'] evaluates to -1, not -2. The "
            "expression is always valid. For ['2','1','+','3','*'] the result is 9."
        ),
        "asserts": [
            [[["2", "1", "+", "3", "*"]], 9],
            [[["4", "13", "5", "/", "+"]], 6],
            [[["-3", "2", "/"]], -1],
            [[["5"]], 5],
            [[["10", "6", "-"]], 4],
            [[["3", "-4", "*"]], -12],
            [[["7", "2", "/"]], 3],
        ],
    },
    "longest_common_prefix": {
        "func": "longest_common_prefix",
        "prompt": (
            "Write a Python function longest_common_prefix(strs) that takes a list of "
            "strings and returns the longest string that is a prefix of every one of "
            "them. Return an empty string when there is no common prefix, when the "
            "list is empty, or when any string in the list is empty. For "
            "['flower','flow','flight'] the result is 'fl'."
        ),
        "asserts": [
            [[["flower", "flow", "flight"]], "fl"],
            [[["dog", "racecar", "car"]], ""],
            [[[]], ""],
            [[["a"]], "a"],
            [[["abc", "abc"]], "abc"],
            [[["", "abc"]], ""],
            [[["interspecies", "interstellar", "interstate"]], "inters"],
        ],
    },
}


# --------------------------------------------------------------------------------
# Mechanical verification: execute the candidate, compare against fixed assertions.
# --------------------------------------------------------------------------------

# Runs in a child interpreter (python -I). exec() with a small builtins dict and an
# import denylist; SIGALRM caps each individual call; the parent caps the whole child.
# The child exists so that an infinite loop in generated code cannot wedge a harness
# worker thread, which has no timeout of its own.
#
# Honest about what this is: a restricted builtins dict is hygiene, not a security
# boundary — `getattr` alone makes it escapable. The actual containment is that this
# is a short-lived, isolated child process running benign small-function code.
#
# Byte-identical to the block in ft-04-same-ticket-five-ways/exp.py. Duplicated rather
# than shared so each experiment directory stays self-contained, per the harness
# contract (an exp.py imports nothing from the harness).
_CHILD = r'''
import builtins, copy, inspect, json, signal, sys

# Denylist, not an allowlist: a gratuitous `import x` must not fail an otherwise
# correct answer, or the verifier measures the sandbox instead of the model.
_DENIED_MODULES = {
    "os", "posix", "nt", "subprocess", "socket", "shutil", "pathlib", "ctypes",
    "pickle", "marshal", "shelve", "dbm", "sqlite3", "tempfile", "glob", "fileinput",
    "filecmp", "tarfile", "zipfile", "gzip", "bz2", "lzma", "urllib", "http",
    "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "ssl", "select",
    "asyncio", "concurrent", "multiprocessing", "threading", "signal", "importlib",
    "builtins", "runpy", "site", "sysconfig", "distutils", "venv", "zipimport",
    "imp", "resource", "atexit", "gc", "pty", "tty", "termios", "fcntl", "mmap",
    "curses", "webbrowser", "getpass", "pwd", "grp", "platform", "ensurepip", "pip",
}
_real_import = builtins.__import__


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    top = str(name).split(".")[0]
    if top in _DENIED_MODULES or top.startswith("_"):
        raise ImportError("blocked module: " + str(name))
    return _real_import(name, globals, locals, fromlist, level)


_SAFE_NAMES = [
    "abs", "all", "any", "ascii", "bin", "bool", "bytes", "bytearray", "callable",
    "chr", "complex", "delattr", "dict", "divmod", "enumerate", "filter", "float",
    "format", "frozenset", "getattr", "hasattr", "hash", "hex", "id", "int",
    "isinstance", "issubclass", "iter", "len", "list", "map", "max", "min", "next",
    "object", "oct", "ord", "pow", "print", "range", "repr", "reversed", "round",
    "set", "setattr", "slice", "sorted", "staticmethod", "classmethod", "property",
    "str", "sum", "super", "tuple", "type", "zip", "vars",
    "True", "False", "None", "NotImplemented", "Ellipsis",
    "BaseException", "Exception", "ArithmeticError", "AssertionError",
    "AttributeError", "EOFError", "ImportError", "IndexError", "KeyError",
    "LookupError", "MemoryError", "NameError", "NotImplementedError",
    "OverflowError", "RecursionError", "RuntimeError", "StopIteration",
    "StopAsyncIteration", "TypeError", "ValueError", "ZeroDivisionError",
    "UnboundLocalError", "KeyboardInterrupt", "GeneratorExit",
]
SAFE = {n: getattr(builtins, n) for n in _SAFE_NAMES if hasattr(builtins, n)}
SAFE["__import__"] = _guarded_import
SAFE["__build_class__"] = builtins.__build_class__


class _Timeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise _Timeout("call timed out")


_HAS_ALARM = hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer")
if _HAS_ALARM:
    try:
        signal.signal(signal.SIGALRM, _on_alarm)
    except Exception:
        _HAS_ALARM = False


def _alarm(seconds):
    if _HAS_ALARM:
        try:
            signal.setitimer(signal.ITIMER_REAL, seconds)
        except Exception:
            pass


def _norm(v, depth=0):
    if depth > 6:
        return v
    if v is None or isinstance(v, (str, bytes, bool, int, float)):
        return v
    if isinstance(v, dict):
        return {k: _norm(x, depth + 1) for k, x in v.items()}
    if isinstance(v, (set, frozenset)):
        try:
            return [_norm(x, depth + 1) for x in sorted(v)]
        except Exception:
            return [_norm(x, depth + 1) for x in v]
    if isinstance(v, (list, tuple)):
        return [_norm(x, depth + 1) for x in v]
    if hasattr(v, "__iter__"):
        out = []
        for i, x in enumerate(v):
            if i >= 5000:
                break
            out.append(_norm(x, depth + 1))
        return out
    return v


def _eq(got, expected):
    if isinstance(expected, bool):
        return isinstance(got, bool) and got == expected
    return _norm(got) == _norm(expected)


def _emit(res):
    sys.stderr.write("\n@@RESULT@@" + json.dumps(res) + "\n")
    sys.stderr.flush()


def main():
    payload = json.loads(sys.stdin.read())
    code = payload["code"]
    func = payload["func"]
    asserts = payload["asserts"]
    res = {"pass": False, "n_passed": 0, "n_asserts": len(asserts),
           "signature_ok": False, "exec_error": None}

    g = {"__builtins__": SAFE, "__name__": "__sandbox__"}
    try:
        _alarm(5.0)
        exec(compile(code, "<candidate>", "exec"), g)
    except BaseException as e:
        res["exec_error"] = "exec:" + type(e).__name__
        _alarm(0)
        _emit(res)
        return
    _alarm(0)

    fn = g.get(func)
    if not callable(fn):
        res["exec_error"] = "missing_function"
        _emit(res)
        return

    if asserts:
        try:
            inspect.signature(fn).bind(*asserts[0][0])
            res["signature_ok"] = True
        except Exception:
            res["signature_ok"] = False

    n = 0
    for item in asserts:
        args, expected = item[0], item[1]
        want_exc = expected.get("__raises__") if isinstance(expected, dict) else None
        try:
            call_args = [copy.deepcopy(a) for a in args]
        except Exception:
            call_args = list(args)
        try:
            _alarm(2.0)
            got = fn(*call_args)
            _alarm(0)
        except BaseException as e:
            _alarm(0)
            if want_exc and type(e).__name__ == want_exc:
                n += 1
            continue
        if want_exc:
            continue
        try:
            _alarm(2.0)
            ok = _eq(got, expected)
            _alarm(0)
        except BaseException:
            _alarm(0)
            ok = False
        if ok:
            n += 1

    res["n_passed"] = n
    res["pass"] = bool(asserts) and n == len(asserts)
    _emit(res)


try:
    main()
except BaseException as _e:
    _emit({"pass": None, "n_passed": 0, "n_asserts": 0, "signature_ok": False,
           "exec_error": "child:" + type(_e).__name__})
'''

HARD_TIMEOUT_S = 25.0

_FENCE = re.compile(r"```(?:python|py|python3)?[ \t]*\r?\n(.*?)```", re.DOTALL)


def _fenced_blocks(text):
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


_CODE_START = re.compile(r"^(?:def |async def |class |import |from |@)", re.M)


def _salvage(text):
    """No fence at all. Start at the first plausible code line and trim lines off the
    end until the region parses, so a response that skipped the fence is still scored
    on its code rather than on its prose."""
    try:
        m = _CODE_START.search(text)
        if not m:
            return ""
        lines = text[m.start():].splitlines()
        for cut in range(len(lines), 0, -1):
            cand = "\n".join(lines[:cut])
            try:
                ast.parse(cand)
            except Exception:
                continue
            return cand
    except Exception:
        pass
    return ""


def _extract_code(text, func):
    """First fenced block that parses and defines the target function; else the
    longest fenced block; else a salvaged unfenced code region; else the raw text."""
    if not isinstance(text, str):
        return ""
    blocks = _fenced_blocks(text)
    for b in blocks:
        if _defines(b, func):
            return b
    if blocks:
        return blocks[0]
    return _salvage(text) or text


def _run_asserts(code, func, asserts):
    payload = json.dumps({"code": code, "func": func, "asserts": asserts})
    base = {"pass": None, "n_passed": 0, "n_asserts": len(asserts),
            "signature_ok": False, "exec_error": None}
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", _CHILD],
            input=payload.encode("utf-8"),
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=HARD_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        # A candidate that never returns is a wrong answer, not an unusable run.
        return {**base, "pass": False, "exec_error": "hard_timeout"}
    except Exception as e:
        return {**base, "exec_error": "spawn:" + type(e).__name__}
    err = (proc.stderr or b"").decode("utf-8", "replace")
    for line in reversed(err.splitlines()):
        if "@@RESULT@@" in line:
            try:
                out = json.loads(line.split("@@RESULT@@", 1)[1])
            except Exception:
                break
            if isinstance(out, dict) and "pass" in out:
                return out
            break
    return {**base, "exec_error": "no_result"}


def build_request(task_id, task, cond):
    filler = make_filler(cond["kind"], cond["units"])
    user = (filler + "\n\n" + task["prompt"]) if filler else task["prompt"]
    return {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": 2400,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }


def verify(text, task_id, task, cond):
    asserts = task.get("asserts") or []
    base = {"pass": None, "n_passed": 0, "n_asserts": len(asserts),
            "signature_ok": False, "exec_error": None}
    try:
        if not isinstance(text, str) or not text.strip():
            return {**base, "exec_error": "empty_output"}
        code = _extract_code(text, task["func"])
        if not code.strip():
            return {**base, "pass": False, "exec_error": "no_code"}
        try:
            ast.parse(code)
        except SyntaxError:
            return {**base, "pass": False, "exec_error": "syntax_error"}
        except Exception:
            return {**base, "pass": False, "exec_error": "unparseable"}
        out = _run_asserts(code, task["func"], asserts)
        out["chars"] = len(text)
        out["fenced"] = bool(_fenced_blocks(text))
        return out
    except Exception as e:
        return {**base, "exec_error": "verify:" + type(e).__name__}
