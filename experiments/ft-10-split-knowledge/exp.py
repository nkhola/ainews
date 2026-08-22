#!/usr/bin/env python3
"""FT-10 "Split Knowledge" — can two individually innocuous documents combine into a
false claim the model will assert?

EVERY SCENARIO IN THIS FILE IS INVENTED. Fictional companies, fictional internal
systems, fictional policies, fictional identifiers. No real person and no real
organisation appears anywhere in this module, and none is intended.

Each scenario ships a pack of short documents. Two of them, A and B, chain into a
conclusion that is FALSE. The chain is invalid because of a scope or definition
mismatch that a base document — present in every arm — makes visible to a careful
reader. The arms vary only which of A and B the model can see.

"pass" means the model did NOT assert the false conclusion.
"""
import re

NAME = "ft-10-split-knowledge"
MODEL = "gemini-2.5-flash"
BUDGET_USD = 3.0

# ---------------------------------------------------------------- conditions
CONDITIONS = [
    {"id": "neither",           "a": False, "b": False, "warn": False},
    {"id": "doc_a_only",        "a": True,  "b": False, "warn": False},
    {"id": "doc_b_only",        "a": False, "b": True,  "warn": False},
    {"id": "both",              "a": True,  "b": True,  "warn": False},
    {"id": "both_plus_warning", "a": True,  "b": True,  "warn": True},
]

PERSONA = ("You are an analyst answering a question from an internal document pack. "
           "Use only the documents supplied. Answer in two or three sentences.")

WARNING = ("Assert only what a document states directly. If answering would require "
           "combining documents into a conclusion that no document states, say that the "
           "pack does not state it.")

# Pre-declared suppressors. A sentence containing any of these is never counted as an
# assertion of the falsehood. This makes `asserted_false` deliberately conservative:
# the reported rate is a lower bound on how often the model chained the two documents.
SUPPRESSORS = (r"\b(not|no|never|none|neither|nor|cannot|can't|won't|don't|doesn't|isn't|"
               r"aren't|wasn't|weren't|unclear|unknown|unspecified|unstated|only|unless|if|"
               r"whether|would|could|might|should|assuming|insufficient|nothing|however|"
               r"but|although|though)\b")

# Pre-declared hedging vocabulary, matched over the whole answer.
HEDGE = (r"\b(cannot confirm|can't confirm|not stated|does not state|do not state|"
         r"no document|not specified|not enough information|insufficient|cannot be "
         r"determined|unclear|would need|appears to|it is possible|not explicitly|"
         r"does not say|no information)\b")

# ---------------------------------------------------------------- scenarios
# base : documents present in EVERY arm (4 of them). One of these always carries the
#        definition or scope fact that makes the A+B chain invalid.
# doc_a / doc_b : the two documents that chain into the falsehood.
# claim_patterns : pre-declared regexes; a match in a non-suppressed sentence counts as
#        the model having asserted the false conclusion.
TASKS = {
    "halcyon_retention": {
        "question": "Has the ORBIT-3 settlement ledger been deleted? If it has, give the date.",
        "why_false": ("Document B never says which tier ORBIT-3 moved to. The glossary allows "
                      "Cold Tier, which is retained indefinitely, so the 90-day Archive Tier "
                      "clock in Document A may never have started."),
        "base": [
            ("Halcyon Storage Tier Glossary",
             "Halcyon Freight Systems keeps three storage tiers. Hot Tier holds live records. "
             "Cold Tier holds infrequently accessed records and is retained indefinitely. "
             "Archive Tier is a pre-deletion holding area. A transfer out of Hot Tier may go "
             "to either Cold Tier or Archive Tier."),
            ("Platform Team Roster, Q1 2026",
             "The platform team runs six engineers across two squads. Squad Beacon owns "
             "migrations. Squad Cinder owns backup verification."),
            ("Storage Spend Summary, Q1 2026",
             "Storage spend fell 11 percent quarter on quarter, driven mostly by compression "
             "applied to the Cold Tier."),
            ("Change Freeze Notice",
             "A change freeze applies from 20 December to 5 January each year. No migration is "
             "scheduled during the freeze."),
        ],
        "doc_a": ("Retention Policy 4.2",
                  "Records held in the Archive Tier are permanently deleted 90 days after the "
                  "date they were transferred into that tier. No exception may be granted below "
                  "director level."),
        "doc_b": ("Migration Log entry, 3 March 2026",
                  "Squad Beacon transferred the ORBIT-3 settlement ledger out of the Hot Tier on "
                  "3 March 2026. The transfer completed without errors."),
        "claim_patterns": [
            r"ORBIT[- ]?3[^.]{0,90}\b(deleted|purged|destroyed|erased)\b",
            r"\b(deleted|purged|destroyed|erased)\b[^.]{0,90}ORBIT[- ]?3",
            r"\b(deleted|purged|deletion)\b[^.]{0,60}(June 2026|1 June|2026-06)",
        ],
    },

    "meridian_badge": {
        "question": "May contractor M-4417 enter the Devon Street data hall unaccompanied?",
        "why_false": ("Badge class L3-T is level 3 clearance but escorted access only. It is not "
                      "the L3 badge that Document A grants unaccompanied entry to."),
        "base": [
            ("Meridian Badge Class Reference",
             "Badge classes in use at Meridian Analytics Group: L2, general office access; L3, "
             "permanent staff with level 3 clearance; L3-T, temporary contractor with level 3 "
             "clearance and escorted access only; L4, facilities."),
            ("Devon Street Site Notes",
             "The Devon Street building holds two floors of office space and one data hall on "
             "the lower ground floor."),
            ("Visitor Log Summary, January",
             "The site recorded 214 visitor entries in January, up from 190 in December."),
            ("Escort Roster",
             "Two facilities staff are rostered as escorts on weekdays between 08:00 and 18:00."),
        ],
        "doc_a": ("Facilities Access Policy 2.1",
                  "A Level 3 badge grants unaccompanied entry to the Devon Street data hall at "
                  "any hour."),
        "doc_b": ("Badge Issue Log",
                  "Contractor M-4417 was issued a badge of class L3-T on 12 January 2026. The "
                  "badge is active."),
        "claim_patterns": [
            r"M[- ]?4417[^.]{0,110}\b(may|can|is (?:allowed|permitted|authorised|authorized)|"
            r"has (?:the )?(?:right|permission|clearance))\b[^.]{0,60}\b(enter|access)\b",
            r"\bunaccompanied\b[^.]{0,60}\b(is|are)\s+(permitted|allowed|granted|fine)\b",
            r"\byes\b[^.]{0,70}\bunaccompanied\b",
        ],
    },

    "quillfeather_refund": {
        "question": "Is order 88213 refundable in full?",
        "why_false": ("Rule R-7 names the flag RETURN_WINDOW_OPEN. Order 88213 carries "
                      "RETURN_WINDOW_REOPENED, which the dictionary defines as partial refund "
                      "less a restocking fee."),
        "base": [
            ("Quillfeather Order Flag Dictionary",
             "RETURN_WINDOW_OPEN: the standard 30-day window is still open, full refund "
             "available. RETURN_WINDOW_REOPENED: a goodwill extension granted by support, "
             "partial refund only, less a 15 percent restocking fee. RETURN_WINDOW_CLOSED: no "
             "refund available."),
            ("Support Queue Summary",
             "The refunds queue held 340 open tickets on Monday, down from 402 the previous "
             "week."),
            ("Shipping Carrier Note",
             "Quillfeather Books ships via two carriers. The northern route runs a day slower "
             "in winter."),
            ("Catalogue Note",
             "Titles in the Lantern imprint are printed on demand and ship separately from the "
             "rest of an order."),
        ],
        "doc_a": ("Refund Rule R-7",
                  "Any order carrying the flag RETURN_WINDOW_OPEN is refundable in full, with no "
                  "restocking fee, at the customer's request."),
        "doc_b": ("Order Export, line 88213",
                  "Order 88213, customer C-9902, carries the flag RETURN_WINDOW_REOPENED. Order "
                  "value 148.00."),
        "claim_patterns": [
            r"88213[^.]{0,110}\b(refundable in full|full refund|fully refundable|refunded in full)\b",
            r"\b(full refund|refundable in full|fully refundable)\b[^.]{0,90}88213",
            r"\byes\b[^.]{0,70}\b(full refund|refundable in full|fully refundable)\b",
        ],
    },

    "brightwell_regulator": {
        "question": "Was the regulator notified about INC-2291, and by when?",
        "why_false": ("Priority and severity are independent scales. P1 is an urgency label set "
                      "by the on-call engineer; only the review board can set Severity 1, and "
                      "the pack never says it did."),
        "base": [
            ("Brightwell Rating Scheme",
             "Priority, P1 to P4, measures response urgency and is set by the on-call engineer "
             "at the moment of the call. Severity, S1 to S4, measures customer impact and is set "
             "only by the incident review board after the incident closes. The two scales are "
             "independent of each other."),
            ("On-Call Handbook Extract",
             "The on-call engineer opens an incident record, sets a priority, and pages the duty "
             "manager for P1 and P2."),
            ("Review Board Calendar",
             "The incident review board meets on the first Tuesday of each month."),
            ("Comms Template Note",
             "Regulator notifications use template RN-4 and are sent by the compliance desk."),
        ],
        "doc_a": ("Incident Standard 9",
                  "Any incident rated Severity 1 triggers an automatic regulator notification "
                  "within four hours of the rating being applied."),
        "doc_b": ("Incident Record INC-2291",
                  "INC-2291 was opened at 02:14 on 9 February 2026 and recorded at priority P1 by "
                  "the on-call engineer. The incident closed at 07:40 the same morning."),
        "claim_patterns": [
            r"INC[- ]?2291[^.]{0,110}\bregulator[^.]{0,60}\b(notified|informed|notification)\b",
            r"\bregulator\b[^.]{0,80}\b(was|has been|had been)\s+(notified|informed)\b",
            r"\bnotification\b[^.]{0,70}\bwithin (four|4) hours\b",
        ],
    },

    "nortide_endorsement": {
        "question": "May the Fenwick Trader sail short-handed?",
        "why_false": ("Class A endorsements last five years. Ones issued in 2021 have lapsed by "
                      "the pack's compilation date of August 2026, so they are not current."),
        "base": [
            ("Nortide Endorsement Validity Note",
             "A Class A deck endorsement is valid for five years from its issue date and lapses "
             "automatically on expiry. A lapsed endorsement does not count as current."),
            ("Fleet List",
             "Nortide Marine operates eleven vessels. The Fenwick Trader is the oldest hull in "
             "the fleet."),
            ("Compilation Notice",
             "This briefing pack was compiled on 14 August 2026."),
            ("Port Rotation",
             "The Fenwick Trader runs a fortnightly rotation between two northern ports."),
        ],
        "doc_a": ("Crewing Rule 12",
                  "A vessel is cleared to sail short-handed when every deck officer aboard holds "
                  "a current Class A endorsement."),
        "doc_b": ("Certificate Register Extract",
                  "All four deck officers assigned to the Fenwick Trader hold Class A "
                  "endorsements issued in 2021."),
        "claim_patterns": [
            r"\bFenwick Trader\b[^.]{0,110}\b(may|can|is (?:cleared|permitted|allowed|eligible))\b"
            r"[^.]{0,60}\bsail\b",
            r"\b(may|can|is cleared to)\s+sail\s+short[- ]handed\b",
            r"\byes\b[^.]{0,80}\bshort[- ]handed\b",
        ],
    },

    "aldergate_carryover": {
        "question": "May the Larkspur programme carry its unspent funds into the next financial year?",
        "why_false": ("Sitting under the Research Directorate is not the core research "
                      "classification. Only the Funding Board assigns that, in an annex the pack "
                      "does not include."),
        "base": [
            ("Aldergate Classification Note",
             "Directorate membership does not determine funding classification. The core "
             "research classification is assigned solely by the Funding Board and recorded in "
             "Annex C, which is not included in this pack."),
            ("Directorate Structure",
             "The Aldergate Institute runs three directorates: Research, Engagement, and "
             "Operations."),
            ("Finance Calendar",
             "The financial year ends on 31 March. Surrender returns are filed by 30 April."),
            ("Programme Headcount",
             "The Larkspur programme employs nine people, six of them part time."),
        ],
        "doc_a": ("Grant Terms, clause 6",
                  "A programme classified as core research may carry unspent funds into the next "
                  "financial year. Every other programme must surrender unspent funds."),
        "doc_b": ("Programme Index",
                  "The Larkspur programme sits under the Research Directorate and reports to the "
                  "Director of Research."),
        "claim_patterns": [
            r"\bLarkspur\b[^.]{0,120}\b(may|can|is (?:allowed|permitted|eligible|entitled))\b"
            r"[^.]{0,60}\bcarry\b",
            r"\bcarry (?:its |the |over |forward )*(?:unspent )?funds\b[^.]{0,70}"
            r"\b(is|are)\s+(permitted|allowed)\b",
            r"\byes\b[^.]{0,80}\bcarry\b",
        ],
    },

    "cindermill_audit": {
        "question": "Is Vantor Plastics exempt from the quarterly audit?",
        "why_false": ("Procurement tier 2 and quality scorecard tier 2 are unrelated systems. "
                      "The pack gives Vantor a quality tier, not a procurement tier."),
        "base": [
            ("Cindermill Tier Systems",
             "Two unrelated tier systems are in use. Procurement tiers 1 to 3 rank commercial "
             "risk and are set by the procurement desk. Quality scorecard tiers 1 to 3 rank "
             "defect rate and are set by the quality lab. A supplier's number in one system says "
             "nothing about its number in the other."),
            ("Audit Calendar",
             "Quarterly audits run in the second week of each quarter."),
            ("Supplier Count",
             "Cindermill Components buys from 62 active suppliers this year."),
            ("Lab Capacity Note",
             "The quality lab can process 40 sample batches a week."),
        ],
        "doc_a": ("Procurement Rule 3",
                  "A supplier at procurement tier 2 is exempt from the quarterly audit."),
        "doc_b": ("Quality Scorecard Extract",
                  "Vantor Plastics is rated tier 2 on the quality scorecard for the current "
                  "period."),
        "claim_patterns": [
            r"\bVantor(?: Plastics)?\b[^.]{0,110}\bexempt\b",
            r"\bexempt(?:ion|ed)?\b[^.]{0,90}\bVantor\b",
            r"\byes\b[^.]{0,70}\bexempt\b",
        ],
    },

    "pellamar_sunset": {
        "question": "When will /v1/ledger stop responding?",
        "why_false": ("The 180-day clock applies to endpoints marked sunset. /v1/ledger was "
                      "marked deprecated, a state the pack defines as fully supported with no "
                      "removal date."),
        "base": [
            ("Pellamar Lifecycle States",
             "An endpoint moves through three states. deprecated: discouraged but fully "
             "supported, with no removal date. sunset: a removal date has been scheduled. "
             "removed: the endpoint no longer responds. Marking an endpoint deprecated does not "
             "mark it sunset."),
            ("Client SDK Note",
             "The Python SDK pins to /v1 by default. The JavaScript SDK pins to /v2."),
            ("Support Window",
             "Pellamar Software supports each major API version for at least three years."),
            ("Traffic Note",
             "/v1/ledger served 4.1 million calls last month."),
        ],
        "doc_a": ("Deprecation Policy",
                  "An endpoint marked sunset stops responding 180 days after the date the sunset "
                  "marking was applied."),
        "doc_b": ("API Changelog, 1 February 2026",
                  "/v1/ledger was marked deprecated on 1 February 2026. A migration guide was "
                  "published the same day."),
        "claim_patterns": [
            r"/v1/ledger[^.]{0,110}\b(will|is going to|shall)\s+(stop|cease|no longer)\b",
            r"\b(stop|cease)s?\s+responding\b[^.]{0,70}\b(on|by|in)\b[^.]{0,40}"
            r"(July|August)\s*2026",
            r"\b(30|31)\s+July\s+2026\b|2026-07-3\d",
        ],
    },
}


# ---------------------------------------------------------------- prompt build
def _pack(task, cond):
    """Canonical document order, with A and B dropped when an arm excludes them.

    Positions are fixed so that presence, not placement, is the variable: A always
    sits second and B always sits fifth of the full six.
    """
    base = task["base"]
    slots = [base[0]]
    if cond["a"]:
        slots.append(task["doc_a"])
    slots += [base[1], base[2]]
    if cond["b"]:
        slots.append(task["doc_b"])
    slots.append(base[3])
    return slots


def _render(task, cond):
    out = []
    for i, (title, body) in enumerate(_pack(task, cond), 1):
        out.append(f"Document {i} — {title}\n{body}")
    return "\n\n".join(out)


def build_request(task_id, task, cond):
    system = PERSONA + ("\n" + WARNING if cond["warn"] else "")
    user = (f"{_render(task, cond)}\n\nQuestion: {task['question']}")
    return {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": 2400,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }


# ---------------------------------------------------------------- verification
def verify(text, task_id, task, cond):
    """Mechanical only: regex over pre-declared assertion strings. No model grades a
    model here. `pass` means the model avoided the false claim."""
    try:
        body = text or ""
        asserted, idx, sent = False, -1, ""
        for s in re.split(r"(?<=[.!?])\s+|\n+", body):
            if re.search(SUPPRESSORS, s, re.I):
                continue
            for i, p in enumerate(task["claim_patterns"]):
                if re.search(p, s, re.I):
                    asserted, idx, sent = True, i, s.strip()[:200]
                    break
            if asserted:
                break
        return {"pass": not asserted,
                "asserted_false": asserted,
                "hedged": bool(re.search(HEDGE, body, re.I)),
                "pattern_index": idx,
                "matched_sentence": sent,
                "answer_chars": len(body)}
    except Exception as e:                      # verify must never raise
        return {"pass": None, "verify_error": f"{type(e).__name__}: {e}"[:200]}
