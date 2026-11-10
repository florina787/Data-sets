"""Fixture dataset with hand-computed expected answers (see EXPECTED below).

Same CSV schema as the Syncora sample, including random lowercase filler after
each sentence, shuffled-looking timestamps are NOT used here so the
expectations stay easy to verify by hand.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

N = "Still not fixed. Can you escalate?"  # -1.0
U = "It’s urgent. Please expedite."  # -0.6
W = "Okay, waiting for an update."  # 0
F = "Got it. I’ve retried, and it works now."  # +1.0
T = "Thanks, that helps."  # +0.8
E = "I understand this is frustrating. I'm investigating now."  # empathy
H = "Please allow me a moment while I run some checks."  # no empathy
RES = {
    "refund": "I have issued a refund. You’ll see it in 3-5 business days.",
    "coupon": "I have applied the coupon manually and adjusted your invoice.",
    "escalated": "We escalated the case to our specialist team. You'll get an update soon.",
    "reset": "I’ve reset your account. Please try logging in again.",
    "service": "Service activated. Please restart the app and confirm.",
    "delivery": "The order is out for delivery. Expected by tomorrow evening.",
}

# (conv_id, start, agent, opening, [agent, customer, agent, customer, agent(resolution)])
CONVERSATIONS = [
    ("C0000001", "2025-02-03T10:00:00", "AgentAAAA", "I was charged twice for my Wallet.", [H, N, H, U, RES["refund"]]),
    ("C0000002", "2025-02-05T11:00:00", "AgentAAAA", "I was charged twice for my Bus.", [E, N, E, F, RES["coupon"]]),
    ("C0000003", "2025-02-07T12:00:00", "AgentBBBB", "App crash ho rahi hai while using Order.", [H, U, E, N, RES["escalated"]]),
    ("C0000004", "2025-02-10T09:00:00", "AgentBBBB", "Coupon isn’t applying on checkout for the Voucher.", [E, T, H, F, RES["coupon"]]),
    ("C0000005", "2025-02-12T15:00:00", "AgentCCCC", "Hi, I need help with my Insurance.", [H, W, H, T, RES["refund"]]),
    ("C0000006", "2025-02-20T16:00:00", "AgentDDDD", "I was charged twice for my Loan.", [H, N, H, N, RES["refund"]]),
    ("C0000007", "2025-02-27T08:00:00", "AgentAAAA", "I can’t log in. It says account locked.", [E, U, H, N, RES["reset"]]),
    ("C0000008", "2025-01-08T10:00:00", "AgentBBBB", "App crash ho rahi hai while using Wallet.", [H, N, H, N, RES["service"]]),
    ("C0000009", "2025-01-15T10:00:00", "AgentEEEE", "Coupon isn’t applying on checkout for the Order.", [E, F, E, T, RES["coupon"]]),
    ("C0000010", "2025-01-20T10:00:00", "AgentFFFF", "The Gift Card hasn’t arrived yet. Can you check?", [H, W, H, W, RES["delivery"]]),
    # Unknown phrasing + PII: exercises the lexicon fallback and masking.
    ("C0000011", "2025-01-25T10:00:00", "AgentFFFF", "Hi, my email is jane.doe@example.com and my order never came, terrible service.",
     [E, "Thanks a lot, it works now.", H, W, RES["delivery"]]),
]

EXPECTED = {
    "latest_month": "2025-02",
    "feb_conversations": 7,
    "feb_negative": 4,  # C1, C3, C6, C7
    "feb_ranking_by_count": ["Duplicate charge", "App crash", "Login / account locked", "Coupon not applying", "General help request"],
    "feb_duplicate_negative": 2,
    "feb_duplicate_conversations": 3,
    "coaching_all": {"AgentAAAA": {"negative_turns": 8, "empathic_replies": 3}, "AgentBBBB": {"negative_turns": 7, "empathic_replies": 2}},
    "coaching_top_agent": "AgentAAAA",
    "trajectory_C0000002_turning_points": [4],
}

NOISE = " xkqwe plorvn zzmqt"


def write_fixture(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["conv_id", "turn_index", "timestamp", "role", "text", "customer_name", "agent_name"])
        for cid, start, agent, opening, rest in CONVERSATIONS:
            t0 = datetime.fromisoformat(start)
            turns = [("customer", opening)] + [("agent" if i % 2 == 0 else "customer", txt) for i, txt in enumerate(rest)]
            for i, (role, txt) in enumerate(turns):
                w.writerow([cid, i, (t0 + timedelta(minutes=7 * i)).isoformat(), role, txt + NOISE, f"Cust{cid[-4:]}", agent])
    return path
