#!/usr/bin/env python3
"""FT-04 "Same Ticket, Five Ways" — does rewording a ticket change what you get?

Six base tasks. Five meaning-preserving rewrites of each: terse bug-report, formal
spec, chatty Slack, user story, and a precise statement. Every rewrite names the same
function, describes the same behaviour, and states the same edge cases. Only register
and structure differ.

Correctness is measured by EXECUTION, not by opinion. The generated function is run
against a fixed assertion set in a child process with a restricted builtins dict, an
import allowlist, a per-assertion SIGALRM, and a hard wall-clock timeout on the parent
side. No model grades anything.
"""
import ast
import json
import re
import subprocess
import sys

NAME = "ft-04-same-ticket-five-ways"
MODEL = "gemini-2.5-flash"
BUDGET_USD = 3.0

# Identical in every arm. It fixes the output format so extraction is reliable; it is
# not part of the manipulation.
SYSTEM = ("You are a Python code generator. Reply with a single fenced Python code "
          "block containing the complete function and nothing else.")

CONDITIONS = [
    {"id": "terse_ticket", "key": "terse_ticket",
     "label": "terse bug-report shorthand"},
    {"id": "formal_spec", "key": "formal_spec",
     "label": "numbered formal specification"},
    {"id": "slack_chatty", "key": "slack_chatty",
     "label": "casual Slack message"},
    {"id": "user_story", "key": "user_story",
     "label": "agile user story with acceptance criteria"},
    {"id": "precise", "key": "precise",
     "label": "plain precise statement"},
]

# Assertion format: [[arg, ...], expected].
# expected == {"__raises__": "ExceptionName"} means the call must raise that exception.
TASKS = {
    "merge_intervals": {
        "func": "merge_intervals",
        "wordings": {
            "terse_ticket": (
                "merge_intervals(intervals) missing. Need it.\n"
                "Input: list of [start, end] pairs, unsorted, may overlap.\n"
                "Output: new list, overlaps merged, sorted by start.\n"
                "Touching endpoints ([1,4],[4,5]) count as overlapping -> merge.\n"
                "Empty input -> empty list."
            ),
            "formal_spec": (
                "SPECIFICATION\n"
                "1. Implement a Python function with the signature "
                "merge_intervals(intervals).\n"
                "2. The parameter `intervals` is a list of two-element [start, end] "
                "pairs. It shall not be assumed to be sorted.\n"
                "3. The function shall return a new list of intervals in which all "
                "overlapping intervals have been merged, ordered by start value.\n"
                "4. Intervals that share only an endpoint, such as [1,4] and [4,5], "
                "shall be treated as overlapping and merged.\n"
                "5. An empty input list shall produce an empty output list."
            ),
            "slack_chatty": (
                "hey quick one - can you write me a merge_intervals(intervals) in "
                "python? it takes a list of [start, end] pairs, they come in any "
                "order and some of them overlap, and it should hand back a new list "
                "with the overlapping ones merged together, sorted by start. oh and "
                "if two intervals just touch at the edge like [1,4] and [4,5] treat "
                "that as overlapping too and merge them. empty list in, empty list "
                "out. thanks!"
            ),
            "user_story": (
                "As a scheduling service, I want a Python function "
                "merge_intervals(intervals) so that I can collapse a messy list of "
                "time ranges into a clean one.\n\n"
                "Acceptance criteria:\n"
                "- Accepts a list of [start, end] pairs in arbitrary order.\n"
                "- Returns a new list with overlapping intervals merged, sorted by "
                "start value.\n"
                "- Intervals touching at an endpoint, e.g. [1,4] and [4,5], are "
                "merged.\n"
                "- An empty input list returns an empty list."
            ),
            "precise": (
                "Write a Python function merge_intervals(intervals). The argument is "
                "a list of [start, end] pairs which may be unsorted and may overlap. "
                "Return a new list of merged intervals sorted by start value. "
                "Intervals that touch at an endpoint, such as [1,4] and [4,5], count "
                "as overlapping and are merged into one. If the input list is empty, "
                "return an empty list."
            ),
        },
        "asserts": [
            [[[[1, 3], [2, 6], [8, 10], [15, 18]]], [[1, 6], [8, 10], [15, 18]]],
            [[[[1, 4], [4, 5]]], [[1, 5]]],
            [[[]], []],
            [[[[5, 7], [1, 3]]], [[1, 3], [5, 7]]],
            [[[[1, 10], [2, 3]]], [[1, 10]]],
            [[[[1, 2]]], [[1, 2]]],
        ],
    },

    "roman_to_int": {
        "func": "roman_to_int",
        "wordings": {
            "terse_ticket": (
                "Need roman_to_int(s).\n"
                "In: uppercase roman numeral string, valid, range 1-3999.\n"
                "Out: int value.\n"
                "Must handle subtractive pairs IV IX XL XC CD CM.\n"
                "e.g. MCMXCIV -> 1994."
            ),
            "formal_spec": (
                "SPECIFICATION\n"
                "1. Implement a Python function with the signature roman_to_int(s).\n"
                "2. The parameter `s` is a valid uppercase Roman numeral string "
                "representing a value in the range 1 to 3999 inclusive.\n"
                "3. The function shall return the integer value of that numeral.\n"
                "4. The subtractive forms IV, IX, XL, XC, CD and CM shall be handled "
                "correctly.\n"
                "5. Example: roman_to_int('MCMXCIV') returns 1994."
            ),
            "slack_chatty": (
                "hey, need a python roman_to_int(s) if you have a sec. you pass it an "
                "uppercase roman numeral string (always valid, always somewhere "
                "between 1 and 3999) and it gives back the integer. it does need to "
                "get the subtractive ones right - IV, IX, XL, XC, CD, CM - so "
                "MCMXCIV should come out as 1994. cheers"
            ),
            "user_story": (
                "As a data importer, I want a Python function roman_to_int(s) so "
                "that I can turn Roman numerals in legacy records into integers.\n\n"
                "Acceptance criteria:\n"
                "- Accepts a valid uppercase Roman numeral string for a value from 1 "
                "to 3999.\n"
                "- Returns the integer value of that numeral.\n"
                "- Subtractive pairs IV, IX, XL, XC, CD and CM are handled "
                "correctly.\n"
                "- roman_to_int('MCMXCIV') returns 1994."
            ),
            "precise": (
                "Write a Python function roman_to_int(s). The argument is a valid "
                "uppercase Roman numeral string representing a value between 1 and "
                "3999 inclusive. Return its integer value. The subtractive pairs IV, "
                "IX, XL, XC, CD and CM must be handled correctly, so that "
                "roman_to_int('MCMXCIV') returns 1994."
            ),
        },
        "asserts": [
            [["III"], 3],
            [["IV"], 4],
            [["IX"], 9],
            [["XL"], 40],
            [["LVIII"], 58],
            [["MCMXCIV"], 1994],
            [["MMXXVI"], 2026],
        ],
    },

    "chunk_list": {
        "func": "chunk_list",
        "wordings": {
            "terse_ticket": (
                "chunk_list(items, size) needed.\n"
                "Split list into consecutive chunks of length `size`.\n"
                "Return a list of lists, not a generator.\n"
                "Last chunk short if it does not divide evenly.\n"
                "size >= len(items) -> one chunk with everything.\n"
                "Empty input -> []."
            ),
            "formal_spec": (
                "SPECIFICATION\n"
                "1. Implement a Python function with the signature "
                "chunk_list(items, size).\n"
                "2. The function shall split `items` into consecutive chunks of "
                "length `size` and return a list of lists. It shall not return a "
                "generator.\n"
                "3. Where the length of `items` is not an exact multiple of `size`, "
                "the final chunk shall contain the remaining elements.\n"
                "4. Where `size` is greater than or equal to the length of `items`, "
                "the result shall be a single chunk containing every element.\n"
                "5. An empty input list shall produce an empty output list."
            ),
            "slack_chatty": (
                "can someone write a chunk_list(items, size) in python? nothing "
                "fancy, it just cuts a list up into consecutive chunks of `size` and "
                "gives back a list of lists - an actual list please, not a generator. "
                "if it doesn't divide evenly the last chunk is just shorter, and if "
                "size is bigger than the list you get one chunk with everything in "
                "it. empty list in, empty list out. ta"
            ),
            "user_story": (
                "As a batch uploader, I want a Python function "
                "chunk_list(items, size) so that I can send records in fixed-size "
                "batches.\n\n"
                "Acceptance criteria:\n"
                "- Splits `items` into consecutive chunks of length `size`.\n"
                "- Returns a list of lists, not a generator.\n"
                "- The final chunk is shorter when the length is not an exact "
                "multiple of `size`.\n"
                "- A `size` at or above the length of `items` yields one chunk "
                "containing everything.\n"
                "- An empty input list returns an empty list."
            ),
            "precise": (
                "Write a Python function chunk_list(items, size) that splits `items` "
                "into consecutive chunks of length `size` and returns a list of "
                "lists. Do not return a generator. If the length of `items` is not "
                "an exact multiple of `size`, the last chunk holds the remainder. If "
                "`size` is greater than or equal to the length of `items`, return a "
                "single chunk containing every element. If `items` is empty, return "
                "an empty list."
            ),
        },
        "asserts": [
            [[[1, 2, 3, 4, 5], 2], [[1, 2], [3, 4], [5]]],
            [[[], 3], []],
            [[[1, 2, 3], 5], [[1, 2, 3]]],
            [[[1, 2, 3, 4], 4], [[1, 2, 3, 4]]],
            [[["a", "b", "c"], 1], [["a"], ["b"], ["c"]]],
            [[[1, 2, 3, 4, 5, 6], 3], [[1, 2, 3], [4, 5, 6]]],
        ],
    },

    "parse_semver": {
        "func": "parse_semver",
        "wordings": {
            "terse_ticket": (
                "parse_semver(version) missing.\n"
                "In: string, exactly MAJOR.MINOR.PATCH, all non-negative integers.\n"
                "Out: tuple of three ints.\n"
                "Anything else (wrong part count, non-digit part) -> raise "
                "ValueError.\n"
                "'1.2.3' -> (1, 2, 3). '1.2' -> ValueError."
            ),
            "formal_spec": (
                "SPECIFICATION\n"
                "1. Implement a Python function with the signature "
                "parse_semver(version).\n"
                "2. The parameter `version` is a string expected to be exactly three "
                "dot-separated non-negative integers, in the form "
                "MAJOR.MINOR.PATCH.\n"
                "3. On a conforming input the function shall return a tuple of three "
                "integers, e.g. parse_semver('1.2.3') returns (1, 2, 3).\n"
                "4. On any non-conforming input, including the wrong number of parts "
                "or a part that is not composed of digits, the function shall raise "
                "ValueError.\n"
                "5. Example: parse_semver('1.2') raises ValueError."
            ),
            "slack_chatty": (
                "need a little parse_semver(version) in python when you get a "
                "chance. give it a string that should be exactly MAJOR.MINOR.PATCH, "
                "all non-negative integers, and it hands back a tuple of three ints, "
                "so '1.2.3' becomes (1, 2, 3). if it's not that shape - wrong number "
                "of parts, or one of the parts isn't digits - just raise ValueError. "
                "so '1.2' should blow up with a ValueError. thanks!"
            ),
            "user_story": (
                "As a release tool, I want a Python function parse_semver(version) "
                "so that I can compare version strings numerically.\n\n"
                "Acceptance criteria:\n"
                "- Accepts a string of exactly three dot-separated non-negative "
                "integers, MAJOR.MINOR.PATCH.\n"
                "- Returns a tuple of three integers, so '1.2.3' gives (1, 2, 3).\n"
                "- Raises ValueError for any other input, including the wrong number "
                "of parts or a part that is not all digits.\n"
                "- parse_semver('1.2') raises ValueError."
            ),
            "precise": (
                "Write a Python function parse_semver(version). The argument is a "
                "string that should be exactly three dot-separated non-negative "
                "integers in the form MAJOR.MINOR.PATCH. Return a tuple of three "
                "integers, so parse_semver('1.2.3') returns (1, 2, 3). Raise "
                "ValueError for any other input, including the wrong number of parts "
                "or a part that is not composed of digits; parse_semver('1.2') "
                "raises ValueError."
            ),
        },
        "asserts": [
            [["1.2.3"], [1, 2, 3]],
            [["0.0.0"], [0, 0, 0]],
            [["10.20.30"], [10, 20, 30]],
            [["1.2"], {"__raises__": "ValueError"}],
            [["1.2.x"], {"__raises__": "ValueError"}],
            [["1.2.3.4"], {"__raises__": "ValueError"}],
        ],
    },

    "rle_encode": {
        "func": "rle_encode",
        "wordings": {
            "terse_ticket": (
                "rle_encode(s) needed.\n"
                "Run-length encode a string.\n"
                "Every run -> character followed by its length, INCLUDING runs of "
                "1.\n"
                "'aaabbc' -> 'a3b2c1'. 'xyz' -> 'x1y1z1'.\n"
                "'' -> ''."
            ),
            "formal_spec": (
                "SPECIFICATION\n"
                "1. Implement a Python function with the signature rle_encode(s).\n"
                "2. The function shall return the run-length encoding of the string "
                "`s` as a string.\n"
                "3. Each consecutive run of an identical character shall be emitted "
                "as that character followed by the decimal length of the run. Runs of "
                "length one are NOT exempt and shall be emitted with an explicit "
                "count of 1.\n"
                "4. Example: rle_encode('aaabbc') returns 'a3b2c1', and "
                "rle_encode('xyz') returns 'x1y1z1'.\n"
                "5. An empty input string shall return an empty string."
            ),
            "slack_chatty": (
                "quick favour - a python rle_encode(s) that run-length encodes a "
                "string. each run of the same character becomes the character then "
                "how many of them there were, and yes that includes runs of one, so "
                "'aaabbc' comes out as 'a3b2c1' and 'xyz' comes out as 'x1y1z1' not "
                "just 'xyz'. empty string gives you an empty string back. appreciate "
                "it"
            ),
            "user_story": (
                "As a log compressor, I want a Python function rle_encode(s) so that "
                "I can shrink repetitive strings.\n\n"
                "Acceptance criteria:\n"
                "- Returns the run-length encoding of `s` as a string.\n"
                "- Each run is the character followed by the length of the run.\n"
                "- Runs of length one still carry an explicit count of 1, so "
                "rle_encode('xyz') returns 'x1y1z1'.\n"
                "- rle_encode('aaabbc') returns 'a3b2c1'.\n"
                "- An empty input string returns an empty string."
            ),
            "precise": (
                "Write a Python function rle_encode(s) that returns the run-length "
                "encoding of the string `s` as a string. Each consecutive run of an "
                "identical character becomes that character followed by the decimal "
                "length of the run, and runs of length one are included with an "
                "explicit count of 1. So rle_encode('aaabbc') returns 'a3b2c1' and "
                "rle_encode('xyz') returns 'x1y1z1'. An empty input string returns an "
                "empty string."
            ),
        },
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
        "wordings": {
            "terse_ticket": (
                "balanced_brackets(s) needed. Returns bool.\n"
                "Checks (), [], {} are balanced and correctly nested.\n"
                "Every other character is ignored.\n"
                "'([{}])' -> True. '(]' -> False. ')(' -> False.\n"
                "'' -> True."
            ),
            "formal_spec": (
                "SPECIFICATION\n"
                "1. Implement a Python function with the signature "
                "balanced_brackets(s).\n"
                "2. The function shall return a boolean indicating whether the round, "
                "square and curly brackets in `s` are balanced and correctly "
                "nested.\n"
                "3. All characters other than ( ) [ ] { } shall be ignored.\n"
                "4. Examples: '([{}])' returns True; '(]' returns False; ')(' "
                "returns False.\n"
                "5. An empty input string shall return True."
            ),
            "slack_chatty": (
                "anyone able to knock out a balanced_brackets(s) in python? returns "
                "True or False depending on whether the (), [] and {} in the string "
                "are balanced and nested properly. anything that isn't a bracket you "
                "just ignore. so '([{}])' is True, '(]' is False, ')(' is False, and "
                "an empty string is True. thanks a lot"
            ),
            "user_story": (
                "As a syntax checker, I want a Python function balanced_brackets(s) "
                "so that I can reject malformed expressions early.\n\n"
                "Acceptance criteria:\n"
                "- Returns a boolean for whether (), [] and {} in `s` are balanced "
                "and correctly nested.\n"
                "- Characters that are not brackets are ignored.\n"
                "- '([{}])' returns True, '(]' returns False, ')(' returns False.\n"
                "- An empty string returns True."
            ),
            "precise": (
                "Write a Python function balanced_brackets(s) that returns a boolean "
                "indicating whether the round, square and curly brackets in the "
                "string `s` are balanced and correctly nested. Ignore every character "
                "that is not one of ( ) [ ] { }. So '([{}])' returns True, '(]' "
                "returns False and ')(' returns False. An empty string returns True."
            ),
        },
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


def _extract_code(text, func):
    """First fenced block that parses and defines the target function; else the
    longest fenced block; else the raw text."""
    blocks = _fenced_blocks(text)
    for b in blocks:
        if _defines(b, func):
            return b
    if blocks:
        return blocks[0]
    return text if isinstance(text, str) else ""


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
    user = task["wordings"][cond["key"]]
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
