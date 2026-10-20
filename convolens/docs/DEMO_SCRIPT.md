# Five-minute leadership demo

**Setup:** start the backend and frontend (see the README), open http://127.0.0.1:5173, and keep the Flo panel open. Use **Connected analysis** with the imported Kaggle dataset. If no dataset has been imported, use **Demonstration**, and say aloud that it shows synthetic fixtures.

**0:00 – The question (30 s)**
- "Our support teams handle thousands of public conversations. Which problems deserve attention, what is the evidence, and who will act?"
- Point to the top bar: the dataset, the mode, the data range and **the actual number of conversations selected**.

**0:30 – Executive overview (60 s)**
- Show the stat cards. Each one shows its denominator and its unknowns, for example "32 of 281 with known outcome".
- Explain why outcomes are often unknown: public threads move to DMs.
- Click the **Billing & refunds** bar. Every chart re-filters, and the active-scope chip appears.
- Click a stacked segment. The Conversation Explorer opens with exactly those conversations.

**1:30 – Evidence (45 s)**
- In the Explorer, open a thread.
- Point out the customer and support turns, the reply branches, the redacted handles, and the evidence highlights behind each label.
- Correct one label as a reviewer. The original prediction is preserved.

**2:15 – Ask Flo (75 s)**
- With the refund scope active, ask "Why is this happening?"
- Walk through the answer:
  - The tool activity streams in, showing tools and filters.
  - The answer covers Finding, Scope and denominator, Evidence, Limitations and Next action.
  - The answer says it describes **reported patterns, not verified causes**.
- Click a citation `[E1]`, then **Open message**. The exact message is highlighted.
- Ask "What is our CSAT?" Flo gives a clear limitation instead of a made-up number.

**3:30 – Decision and ownership (60 s)**
- Ask "Propose an action to reduce unresolved refund issues."
- Show the decision brief:
  - the hypothesis is labelled as one,
  - alternative explanations are listed,
  - there are no ROI or churn figures,
  - effort is marked "requires reviewer input".
- Enter an owner and your name, then click **Approve and save**. One record is saved, and approving again cannot duplicate it.
- Open **Decisions and actions**: the status, owner, due date, success measure and approval history.

**4:30 – Trust and measurement (30 s)**
- **Insight maps → Agent execution:** the real LangGraph path the answer took.
- **Impact review:** pick an intervention date. Comparable denominators and coverage checks appear, with an explicit warning that a before/after change is not proof of impact.
- Close: "Every number is a SQL count with its denominator. Every claim links to a message. Nothing is saved without a person approving it."
