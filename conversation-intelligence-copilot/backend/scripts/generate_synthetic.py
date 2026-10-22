"""Generate a small, clearly-labelled synthetic demo set (NOT real data).

Purpose: exercise the "synthetic" and "combined" dataset modes and the lexicon
fallback on phrasing that does not match the Syncora templates. It is not used
for any reported finding; the app defaults to the original dataset and these
records carry dataset_source = "synthetic_demo" and IDs prefixed "S".

Usage (from backend/):  uv run python -m scripts.generate_synthetic [--n 120] [--seed 7]
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta

from app.config import get_settings

OPENINGS = [
    "My card got billed two times for the {p} subscription, please sort it.",
    "Paid already but the {p} still isn't active on my account.",
    "The promo code just won't work for {p}.",
    "Been waiting a week and my {p} never showed up.",
    "The app shuts down every time I open {p}.",
    "I'm locked out of my account and can't sign in.",
    "Something is wrong with {p}, it doesn't work at all.",
    "Quick question about {p} please.",
]
CUSTOMER = ["This still isn't sorted, I want a manager.", "Please hurry, this is really urgent.", "Alright, I'll wait to hear back.",
            "Brilliant, it works now, thank you!", "Thanks for the quick help."]
AGENT = ["I'm really sorry for the hassle, let me look into it.", "Could you confirm the email on the account?", "Give me a minute to check this.",
         "I completely understand how annoying this is.", "Thanks for your patience while I check."]
PRODUCTS = ["Wallet", "Broadband", "Flight", "Course", "Insurance", "Order"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = get_settings().synthetic_dataset_path
    out.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2025, 8, 1, 9, 0)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["conv_id", "turn_index", "timestamp", "role", "text", "customer_name", "agent_name"])
        for i in range(args.n):
            cid = f"S{i + 1:07d}"
            t0 = start + timedelta(days=rng.randint(0, 120), minutes=rng.randint(0, 600))
            agent = f"SynAgent{rng.randint(1, 8):02d}"  # few agents, so agent-level comparisons are possible in the demo
            turns = [("customer", rng.choice(OPENINGS).format(p=rng.choice(PRODUCTS)))]
            for k in range(rng.randint(2, 5)):
                turns += [("agent", rng.choice(AGENT)), ("customer", rng.choice(CUSTOMER))]
            turns.append(("agent", "I've escalated this to our specialist team; you'll hear back soon."))
            for k, (role, text) in enumerate(turns):
                w.writerow([cid, k, (t0 + timedelta(minutes=4 * k)).isoformat(timespec="seconds"), role, text, f"SynCust{i:04d}", agent])
    print(f"Wrote {args.n} synthetic demo conversations to {out}")


if __name__ == "__main__":
    main()
