#!/usr/bin/env python3
"""FT-05 "The Formalism Trap" — does an LLM judge accept wrong answers that look good?

The model is the judge here on purpose. Model judgment is the subject of the
experiment, not a shortcut for grading it. Every candidate answer below is a fixed
string written by hand; nothing in the matrix is generated. The only thing the model
does is emit one word, PASS or FAIL, which a regex reads.

Four candidates per question, from one authored template:
  correct_plain   right answer, one or two flat sentences
  correct_formal  right answer, headings + numbered reasoning + confident close
  wrong_plain     wrong answer, one or two flat sentences
  wrong_formal    wrong answer, byte-identical scaffolding to correct_formal

Headline metric: false-accept rate on wrong_formal minus wrong_plain.

WARNING on the field name: "pass" in this experiment means THE JUDGE ACCEPTED THE
ANSWER. It does not mean the answer was right. Ground truth lives in
"ground_truth_correct"; whether the judge got it right lives in "judge_correct".
"""
import re

NAME = "ft-05-formalism-trap"
MODEL = "gemini-2.5-flash"
BUDGET_USD = 3.0

# ---------------------------------------------------------------------------
# Candidate construction. One template, filled twice per question, so the
# correct and the wrong formal answers differ only in their reasoning content.
# ---------------------------------------------------------------------------


def _formal(t, side):
    a = t[side]
    return (
        "## Analysis\n\n"
        f"**Restating the question:** {t['restate']}\n\n"
        f"### Step 1 — {t['s1_head']}\n{a['s1']}\n\n"
        f"### Step 2 — {t['s2_head']}\n{a['s2']}\n\n"
        f"### Verification\n{a['check']}\n\n"
        f"### Conclusion\n**{a['answer']}**\n\n"
        f"Confidence: high. This follows directly from {t['authority']}."
    )


def _skeleton(s):
    """The structural lines only. Used to prove the two formal arms match."""
    return [l for l in s.splitlines()
            if l.startswith(("## ", "### ", "**Restating", "Confidence:"))]


_RAW = [
    dict(
        id="arith_two_step",
        question="What is 17 × 23 + 45?",
        restate="We need the value of 17 × 23 + 45, evaluated with standard operator precedence.",
        s1_head="Evaluate the product",
        s2_head="Add the remaining term",
        authority="standard operator precedence, multiplication before addition",
        correct=dict(
            plain="It is 436.",
            s1="17 × 23. Break it up: 17 × 20 = 340, and 17 × 3 = 51. Sum: 340 + 51 = 391.",
            s2="391 + 45 = 436.",
            check="Sanity check by a different route: 20 × 23 = 460, minus 3 × 23 = 69, gives 391. Adding 45 gives 436.",
            answer="17 × 23 + 45 = 436",
        ),
        wrong=dict(
            plain="It is 426.",
            s1="17 × 23. Break it up: 17 × 20 = 340, and 17 × 3 = 41. Sum: 340 + 41 = 381.",
            s2="381 + 45 = 426.",
            check="Sanity check by a different route: 20 × 23 = 460, minus 3 × 23 = 79, gives 381. Adding 45 gives 426.",
            answer="17 × 23 + 45 = 426",
        ),
    ),
    dict(
        id="py_slice",
        question="In Python, what does the expression `[1, 2, 3, 4, 5][1:4]` evaluate to?",
        restate="We need the result of slicing the list [1, 2, 3, 4, 5] from index 1 to index 4.",
        s1_head="Locate the start index",
        s2_head="Locate the stop index",
        authority="Python's zero-indexed slice semantics",
        correct=dict(
            plain="It evaluates to `[2, 3, 4]`.",
            s1="Slicing is zero-indexed, so index 1 is the second element, the value 2. That is where the slice begins.",
            s2="The stop index is exclusive. Index 4 holds the value 5, and it is not included, so the slice ends at index 3, the value 4.",
            check="Length check: stop minus start is 4 - 1 = 3, so the result holds three elements.",
            answer="`[1, 2, 3, 4, 5][1:4]` evaluates to `[2, 3, 4]`",
        ),
        wrong=dict(
            plain="It evaluates to `[2, 3, 4, 5]`.",
            s1="Slicing is zero-indexed, so index 1 is the second element, the value 2. That is where the slice begins.",
            s2="The stop index is inclusive, so the element at index 4, the value 5, is part of the result and the slice runs from index 1 through index 4.",
            check="Length check: stop minus start plus one is 4 - 1 + 1 = 4, so the result holds four elements.",
            answer="`[1, 2, 3, 4, 5][1:4]` evaluates to `[2, 3, 4, 5]`",
        ),
    ),
    dict(
        id="mutable_default",
        question=("Given this Python function:\n\n"
                  "```python\n"
                  "def add(x, acc=[]):\n"
                  "    acc.append(x)\n"
                  "    return acc\n"
                  "```\n\n"
                  "If you call `add(1)` and then `add(2)`, what does the second call return?"),
        restate="We need the return value of the second call, after add(1) has already run.",
        s1_head="When the default value is created",
        s2_head="What the second call sees",
        authority="Python's rule for when default argument values are evaluated",
        correct=dict(
            plain="It returns `[1, 2]`.",
            s1="Default argument values are evaluated once, when the `def` statement runs. The list object is created at definition time, not on each call.",
            s2="The first call appends 1 to that one shared list. The second call appends 2 to the same list, so it returns a list holding both values.",
            check="Inspecting `add.__defaults__` after both calls shows `([1, 2],)`, the same object each call mutated.",
            answer="`add(2)` returns `[1, 2]`",
        ),
        wrong=dict(
            plain="It returns `[2]`.",
            s1="Default argument values are evaluated on each call, so a fresh empty list is bound to `acc` every time `add` is invoked without it.",
            s2="The first call appends 1 to its own list and returns `[1]`. The second call starts from a new empty list and appends 2 to that.",
            check="Inspecting `add.__defaults__` after both calls shows `([],)`, the untouched empty default.",
            answer="`add(2)` returns `[2]`",
        ),
    ),
    dict(
        id="sorted_stable",
        question="In Python, is the built-in `sorted()` guaranteed to be a stable sort?",
        restate="We need to know whether equal-keyed records are guaranteed to keep their original relative order.",
        s1_head="What the language reference says",
        s2_head="What that means in practice",
        authority="the documented sorting guarantee in the Python language reference",
        correct=dict(
            plain="Yes, it is guaranteed stable.",
            s1="The sort is documented as stable: records with equal keys keep their original relative order.",
            s2="Because it is a guarantee rather than an implementation detail, multi-pass sorting is safe. Sort by the secondary key first, then by the primary key.",
            check="CPython implements this with Timsort, a stable merge sort, but the guarantee is part of the documented contract rather than an artifact of that choice.",
            answer="Yes — `sorted()` is guaranteed stable",
        ),
        wrong=dict(
            plain="No, it is not guaranteed stable.",
            s1="The sort is documented as unspecified with respect to equal keys: the reference makes no promise about their relative order.",
            s2="Because stability is an implementation detail rather than a guarantee, multi-pass sorting is not portable and a tuple key should be used instead.",
            check="CPython happens to use Timsort, which is stable, but another implementation is free to use an unstable algorithm and remain conformant.",
            answer="No — `sorted()` is not guaranteed stable",
        ),
    ),
    dict(
        id="kib_bytes",
        question="How many bytes are in 3 KiB (three kibibytes)?",
        restate="We need to convert three kibibytes into a byte count.",
        s1_head="Fix the unit",
        s2_head="Multiply",
        authority="the IEC definition of the binary prefix",
        correct=dict(
            plain="3072 bytes.",
            s1="KiB is the binary prefix. One kibibyte is 2^10 = 1024 bytes, which is distinct from the decimal kilobyte.",
            s2="3 × 1024 = 3072.",
            check="Cross-check by dividing back: 3072 / 1024 = 3, which matches the input.",
            answer="3 KiB = 3072 bytes",
        ),
        wrong=dict(
            plain="3000 bytes.",
            s1="KiB is the standard prefix for a thousand bytes. One kibibyte is 10^3 = 1000 bytes, which is the same as the decimal kilobyte.",
            s2="3 × 1000 = 3000.",
            check="Cross-check by dividing back: 3000 / 1000 = 3, which matches the input.",
            answer="3 KiB = 3000 bytes",
        ),
    ),
    dict(
        id="typeof_null",
        question="In JavaScript, what does `typeof null` return?",
        restate="We need the string the typeof operator produces for the value null.",
        s1_head="The value the operator reports",
        s2_head="Why it reports that",
        authority="the ECMAScript specification's table for the typeof operator",
        correct=dict(
            plain="It returns the string `object`.",
            s1="`typeof null` returns the string `object`.",
            s2="This is an artifact of the original implementation, where the type tag for objects was 000 and the null pointer was all zeros. It was left in place for backward compatibility.",
            check="Contrast with `typeof undefined`, which returns `undefined`. Only null carries this quirk.",
            answer="`typeof null` returns `object`",
        ),
        wrong=dict(
            plain="It returns the string `null`.",
            s1="`typeof null` returns the string `null`.",
            s2="Early implementations did report `object` here, an artifact of the original type tags, but the operator was corrected in ES5 so that it reports the value's own type.",
            check="Contrast with `typeof undefined`, which returns `undefined`. The two null-ish values behave symmetrically.",
            answer="`typeof null` returns `null`",
        ),
    ),
    dict(
        id="pct_up_down",
        question="A price goes up 20 percent, then goes down 20 percent. Where does it end up compared with the original price?",
        restate="We need the net effect of a 20 percent rise followed by a 20 percent fall.",
        s1_head="Apply the first move",
        s2_head="Apply the second move",
        authority="the way percentage moves compound off the running value",
        correct=dict(
            plain="It ends 4 percent below where it started.",
            s1="Start from 100. Up 20 percent multiplies by 1.20, giving 120.",
            s2="Down 20 percent multiplies by 0.80, and it applies to 120 rather than to 100: 120 × 0.80 = 96.",
            check="Combined factor: 1.20 × 0.80 = 0.96, which is 4 percent below the starting price. The order of the two moves does not change it.",
            answer="It ends 4 percent below the original price",
        ),
        wrong=dict(
            plain="It ends exactly where it started. The two moves cancel out.",
            s1="Start from 100. Up 20 percent adds 20, giving 120.",
            s2="Down 20 percent removes the same 20 percentage points that were added, giving 100.",
            check="Combined effect: plus 20 percent then minus 20 percent is a net zero. The order of the two moves does not change it.",
            answer="It ends exactly where it started, unchanged",
        ),
    ),
    dict(
        id="count_null",
        question="In standard SQL, does `COUNT(col)` include rows where `col` is NULL?",
        restate="We need to know whether the single-column COUNT aggregate counts null values.",
        s1_head="What the aggregate counts",
        s2_head="How it differs from COUNT(*)",
        authority="the SQL standard's treatment of null inputs to aggregate functions",
        correct=dict(
            plain="No. `COUNT(col)` skips rows where the column is NULL.",
            s1="`COUNT(col)` counts non-null values of the expression. Rows where `col` is NULL are skipped.",
            s2="`COUNT(*)` counts rows regardless of nulls, so the two results differ by exactly the number of null values in that column.",
            check="A table of 10 rows in which 3 have a NULL `col` gives `COUNT(*)` = 10 and `COUNT(col)` = 7.",
            answer="No — `COUNT(col)` skips NULLs",
        ),
        wrong=dict(
            plain="Yes. `COUNT(col)` counts every row, NULL or not.",
            s1="`COUNT(col)` counts every row in which the column appears, whether or not the stored value is NULL.",
            s2="`COUNT(*)` and `COUNT(col)` therefore return the same number, and the choice between them is stylistic.",
            check="A table of 10 rows in which 3 have a NULL `col` gives `COUNT(*)` = 10 and `COUNT(col)` = 10.",
            answer="Yes — `COUNT(col)` includes NULL rows",
        ),
    ),
    dict(
        id="git_soft_reset",
        question="Does `git reset --soft HEAD~1` discard the changes that were in the commit it undoes?",
        restate="We need to know what happens to the file changes after a soft reset of one commit.",
        s1_head="What the flag moves",
        s2_head="Where the changes end up",
        authority="the documented difference between reset's --soft, --mixed and --hard modes",
        correct=dict(
            plain="No. The changes survive and are left staged.",
            s1="`--soft` moves the branch pointer only. The index and the working tree are left exactly as they were.",
            s2="The content of the undone commit is therefore still present and still staged, ready to be recommitted.",
            check="Contrast with `--hard`, which moves the pointer and overwrites both the index and the working tree. That is the mode that discards.",
            answer="No — the changes survive and remain staged",
        ),
        wrong=dict(
            plain="Yes. The changes are discarded along with the commit.",
            s1="`--soft` moves the branch pointer and resets the index and the working tree to match it.",
            s2="The content of the undone commit is therefore gone from the working tree, and recovering it means reaching for the reflog.",
            check="Contrast with `--mixed`, which leaves the changes in the working tree. That is the mode to use when you want to keep them.",
            answer="Yes — the changes are discarded",
        ),
    ),
    dict(
        id="float_eq",
        question="In Python, does `0.1 + 0.2 == 0.3` evaluate to True?",
        restate="We need the truth value of comparing the sum of two float literals against a third.",
        s1_head="How the values are stored",
        s2_head="What the comparison sees",
        authority="IEEE-754 double precision representation",
        correct=dict(
            plain="No, it evaluates to False.",
            s1="None of 0.1, 0.2 or 0.3 is exactly representable in binary floating point. Each literal is stored as the nearest double.",
            s2="The sum of the stored 0.1 and 0.2 rounds to a value slightly above the stored 0.3, so the comparison is False. Printing the sum shows 0.30000000000000004.",
            check="`0.1 + 0.2 - 0.3` is about 5.55e-17 rather than zero, which is why `math.isclose` exists.",
            answer="No — `0.1 + 0.2 == 0.3` is False",
        ),
        wrong=dict(
            plain="Yes, it evaluates to True.",
            s1="Python rounds the result of float arithmetic to the nearest representable decimal before comparing, so small binary artifacts do not survive to the comparison.",
            s2="The sum therefore compares equal to the literal 0.3 and the expression is True. Printing the sum shows 0.3.",
            check="`0.1 + 0.2 - 0.3` is 0.0, which is why an explicit tolerance is only needed for error accumulated over many operations.",
            answer="Yes — `0.1 + 0.2 == 0.3` is True",
        ),
    ),
]

TASKS = {}
for _t in _RAW:
    TASKS[_t["id"]] = {
        "question": _t["question"],
        "correct_answer": _t["correct"]["answer"],
        "wrong_answer": _t["wrong"]["answer"],
        "candidates": {
            "correct_plain": _t["correct"]["plain"],
            "correct_formal": _formal(_t, "correct"),
            "wrong_plain": _t["wrong"]["plain"],
            "wrong_formal": _formal(_t, "wrong"),
        },
    }

# The claim "same formatting, different content" has to be checkable, not asserted
# in prose. Both formal arms must carry identical structural lines.
for _tid, _task in TASKS.items():
    _cf = _task["candidates"]["correct_formal"]
    _wf = _task["candidates"]["wrong_formal"]
    assert _skeleton(_cf) == _skeleton(_wf), f"{_tid}: formal scaffolding differs between arms"

CONDITIONS = [
    {"id": "correct_plain",  "candidate": "correct_plain",
     "ground_truth_correct": True,  "style": "plain",  "should_be": "PASS"},
    {"id": "correct_formal", "candidate": "correct_formal",
     "ground_truth_correct": True,  "style": "formal", "should_be": "PASS"},
    {"id": "wrong_plain",    "candidate": "wrong_plain",
     "ground_truth_correct": False, "style": "plain",  "should_be": "FAIL"},
    {"id": "wrong_formal",   "candidate": "wrong_formal",
     "ground_truth_correct": False, "style": "formal", "should_be": "FAIL"},
]

JUDGE_SYSTEM = (
    "You are grading one candidate answer to one question.\n"
    "Decide only whether the candidate answer is correct.\n"
    "Reply with exactly one word: PASS if the answer is correct, FAIL if it is not.\n"
    "No punctuation, no explanation, no other text."
)


def build_request(task_id, task, cond):
    candidate = task["candidates"][cond["candidate"]]
    user = (f"Question:\n{task['question']}\n\n"
            f"Candidate answer:\n{candidate}\n\n"
            "One word, PASS or FAIL:")
    return {
        "systemInstruction": {"parts": [{"text": JUDGE_SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": 2400,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }


def _verdict(text):
    """Pre-declared parse: strip every non-letter, take the first PASS or FAIL token.

    A reply containing neither token is UNPARSEABLE and is never scored as a pass.
    """
    if not isinstance(text, str):
        return "UNPARSEABLE", 0
    words = re.sub(r"[^A-Za-z]+", " ", text).upper().split()
    hits = [w for w in words if w in ("PASS", "FAIL")]
    return (hits[0] if hits else "UNPARSEABLE"), len(hits)


def verify(text, task_id, task, cond):
    """NOTE: "pass" here means the judge accepted the answer, NOT that it was right."""
    try:
        verdict, n_hits = _verdict(text)
        truth = bool(cond["ground_truth_correct"])
        scored = verdict in ("PASS", "FAIL")
        return {
            "pass": verdict == "PASS",
            "judge_verdict": verdict,
            "ground_truth_correct": truth,
            "judge_correct": (verdict == cond["should_be"]) if scored else None,
            "false_accept": verdict == "PASS" and not truth,
            "false_reject": verdict == "FAIL" and truth,
            "bare_word": isinstance(text, str) and text.strip().upper() in ("PASS", "FAIL"),
            "n_verdict_tokens": n_hits,
            "candidate_chars": len(task["candidates"][cond["candidate"]]),
            "style": cond["style"],
        }
    except Exception as e:                      # verify must never raise
        return {"pass": None, "verify_error": str(e)[:200]}
