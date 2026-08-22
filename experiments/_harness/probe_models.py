#!/usr/bin/env python3
"""Which model ids actually answer in THIS project? Prints a table; costs pennies."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import call_once, Budget, price_of

CANDIDATES = [
    "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro",
    "gemini-3-flash", "gemini-3.5-flash", "gemini-3.6-flash",
    "gemini-3-pro-preview", "gemini-3.1-pro-preview", "gemini-3.1-pro",
]
BODY = {"contents": [{"role": "user", "parts": [{"text": "Reply with the single word: ok"}]}],
        "generationConfig": {"maxOutputTokens": 2048}}

b = Budget(2.0)
print(f"{'model':<28} {'status':<10} {'in':>5} {'out':>5} {'thought':>8}  reply")
print("-" * 78)
for m in CANDIDATES:
    body = dict(BODY)
    if "3." in m or "3-" in m:   # 3.x family supports thinking config
        body = {**BODY, "generationConfig": {"maxOutputTokens": 2048,
                                             "thinkingConfig": {"thinkingBudget": 0}}}
    r = call_once(m, body, b, timeout=60, attempts=2)
    if r.get("ok"):
        print(f"{m:<28} {'OK':<10} {r['in_tokens']:>5} {r['out_tokens']:>5} "
              f"{r['thought_tokens']:>8}  {r['text'][:28]!r}")
    else:
        print(f"{m:<28} {'FAIL':<10} {'':>5} {'':>5} {'':>8}  {str(r.get('error'))[:44]}")
print(f"\nprobe spend ≈ ${b.spent:.4f}")
