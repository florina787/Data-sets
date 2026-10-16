"""Clinical safety screening (Agent 3).

This is a conservative keyword screen. It does NOT diagnose and does NOT decide
clinical urgency; it only interrupts routine appointment discovery and points the
person to emergency services when language suggesting a potentially urgent
condition appears. False positives are preferred to false negatives.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

RED_FLAGS: dict[str, list[str]] = {
    "sudden_severe_headache": [r"sudden(ly)?\s+(severe|worst|terrible|intense)\s+headache", r"worst headache",
                               r"thunderclap headache"],
    "neurological_weakness": [r"(new|sudden)\s+(weakness|numbness)", r"(face|arm|leg)\s+(is\s+)?(drooping|numb|weak)",
                              r"can'?t\s+move\s+(my\s+)?(arm|leg|side)", r"one side of (my|the) (body|face)"],
    "speech_difficulty": [r"(difficulty|trouble|can'?t)\s+(speaking|talking|speak|talk)", r"slurred speech",
                          r"slurring"],
    "chest_pain": [r"chest\s+(pain|pressure|tightness)", r"pain in (my|the) chest", r"heart attack"],
    "loss_of_consciousness": [r"(lost|loss of|losing)\s+consciousness", r"passed out", r"fainted", r"blacked out",
                              r"unconscious"],
    "seizure": [r"seizure", r"convulsion"],
    "breathing_difficulty": [r"(can'?t|cannot|difficulty|trouble)\s+breath", r"short(ness)? of breath"],
    "self_harm": [r"(kill|hurt|harm)\s+myself", r"suicid", r"end my life"],
    "severe_bleeding": [r"(heavy|severe|uncontrolled)\s+bleeding", r"won'?t stop bleeding"],
}
_NEGATIONS = re.compile(r"\b(no|not|never|denies|without|don'?t have|haven'?t had)\b[\w\s,]{0,20}$", re.I)

EMERGENCY_MESSAGE = (
    "Some of what you described may need urgent medical attention. I can't assess symptoms. "
    "If this could be an emergency, call 911 or go to the nearest emergency department now. "
    "If you're unsure, you can call Health811 (dial 811 in Ontario) to speak with a registered nurse. "
    "If you're having thoughts of harming yourself, call or text 988 (Suicide Crisis Helpline). "
    "I've paused the appointment search so this message isn't delayed."
)
SOFT_REMINDER = ("Reminder: if your symptoms change or worsen, seek urgent care or call 911. "
                 "I can help with appointment logistics, not medical assessment.")


class SafetyResult(BaseModel):
    interrupt: bool
    flags: list[str]
    negated_flags: list[str]
    message: str | None


def screen(text: str) -> SafetyResult:
    t = (text or "").lower()
    flags: list[str] = []
    negated: list[str] = []
    for flag, patterns in RED_FLAGS.items():
        for p in patterns:
            m = re.search(p, t)
            if not m:
                continue
            prefix = t[max(0, m.start() - 30):m.start()]
            # Negation only softens non-life-threatening mentions; self-harm is never treated as negated.
            if flag != "self_harm" and _NEGATIONS.search(prefix):
                negated.append(flag)
            else:
                flags.append(flag)
            break
    if flags:
        return SafetyResult(interrupt=True, flags=flags, negated_flags=negated, message=EMERGENCY_MESSAGE)
    return SafetyResult(interrupt=False, flags=[], negated_flags=negated, message=SOFT_REMINDER if negated else None)
