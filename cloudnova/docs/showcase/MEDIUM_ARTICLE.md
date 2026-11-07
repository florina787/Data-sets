# The model was the easy part: what a messy invoice export taught me about building AI finance tools

*A Forward Deployed Engineering take-home, written up honestly — including where the AI got it wrong.*

---

A finance lead hands you a CSV and says: *"We want to ask questions about our revenue in plain English and actually trust the answers. Can you show us something by end of day?"*

That was the whole brief for CloudNova, a fictional B2B SaaS company in a take-home exercise. The file had 5,125 rows. By the end I knew it described 5,000 invoices, that the company's own currency rule probably counted FX twice, and that a small local LLM writing SQL on its own got 2 of 6 finance questions right.

This is how I got there, what I built, and what I'd tell another engineer starting the same kind of project.

## 1. Read the data before you write the rules

The export was stitched from three systems: an old billing tool, a CRM and a spreadsheet finance kept by hand. It showed:

- 18 spellings of three plan names (`Pro`, `PRO`, `Professional`, `Tier 2`…)
- 25 spellings of five payment statuses
- five date formats, including `05-01-2024`
- amounts like `"$4,900.00"`, `"31432"` and `"1,200.00 EUR"`
- duplicate rows, and invoices where two systems disagreed about the status

It's tempting to start writing a cleaning function. Instead I asked the data questions first, with tiny pandas scripts:

- **Is `01/05/2024` January or May?** In 1,320 slash dates the first number is never above 12; the second is above 12 in 786. So it's month/day.
- **And `05-01-2024`?** The first number is above 12 in 151 rows, the second never. Day/month. The 81 rows where both readings are valid get flagged, not silently guessed.
- **How many duplicates really disagree?** 43 invoice ids appeared more than once, but 27 only differed by spelling (`completed` vs `PAID`). Only 16 were real conflicts.

Those answers became the spec. The spec became the code. The code got tested against the spec.

## 2. Write it down before you build it

I wrote five short specs before any pipeline code: a data contract, metric definitions, the query interface, the agent's contract and an evaluation plan. They're boring documents, and that's the point. When the AI generated the cleaning code, it was generating it *against* something I could check.

When the code needed to change, the spec changed first. For example, I decided that a bare "revenue" means recognized revenue net of refunds, and "paid invoices" means paid only. That rule is in the spec's change log, not hidden in a regex.

## 3. Account for every row

Every raw row ends up in exactly one place: the clean `invoices` table or an audit table called `rejected_rows`, with its reason and the full original record. A test enforces it.

That one rule made the most convincing screen in the product: a waterfall from 5,125 rows to 5,000 invoices. Counting the duplicates would have overstated paid revenue by **$2,121,660.87**. The 16 conflicts would move net revenue by $168,441.54 if my tie-break rule (refunded > paid > failed > void > pending) picked the wrong record. That's a decision for the billing owner, so the tool shows it rather than hiding it.

## 4. Let the model help — but don't let it be the source of numbers

I used a small local model, Qwen2.5-Coder-3B, so there were no API keys, no per-query cost, and the invoice data never left the machine. The design is "deterministic first": a small semantic layer turns a question into *metric × breakdown × filter* and compiles it to SQL from approved definitions. Qwen only writes SQL when a question falls outside that catalog.

Then I measured what would happen if Qwen wrote *all* the SQL, scored against an independent oracle (a separate implementation of the spec that never imports the app):

| Mode | Correct on the six finance questions | Median time |
|---|---|---|
| Hybrid (approved metrics first) | 6 / 6 | 10 ms |
| Qwen writes all the SQL | 2 / 6 | 20.6 s |

Two failures were obvious SQL errors. One invented `status = 'churned'` — churn isn't a status. The scary one ranked the "top 5 accounts" by paid revenue instead of net revenue. Valid SQL, plausible output, wrong answer. My SQL guard blocks dangerous queries, but it can't tell that a correct-looking query means the wrong thing.

That table changed how I think about "AI-native" analytics. The model is great at understanding the question. It shouldn't be where the financial definitions live.

## 5. Some problems aren't yours to solve

Two findings weren't data cleaning at all.

**The FX rule.** The brief said "EUR→USD 1.08". But every EUR invoice already equaled the USD list price × 1.08. Multiplying again counts FX twice. Under the brief's literal rule, **0 of 1,421** non-USD invoices match the price book; under the inverse rule, **1,421 of 1,421** do. The 2024 revenue answer moves by $3.09M.

**Account identity.** 3,815 account ids but only 200 names, and every name spans several regions and plans. "Top 5 accounts" gives a different answer depending on which one you trust.

I could have "fixed" both. I didn't. These are accounting policy decisions. Instead, the original rules live in a versioned policy file that the app never edits. Each decision has a short record with the evidence, and changing a rule requires a finance owner's name, a rationale and approval of the exact impact numbers they were shown. Applying it is a separate rebuild. Until someone decides, the tool shows both answers, and two "expected failure" tests document exactly what would change.

## 6. Test like you don't trust yourself

The final count: 156 unit tests, an eval harness with 36 cases (33 pass and 3 *expected* failures when Qwen is included), and browser tests for the UI. Some mistakes that testing caught:

- My planner matched "account**s**" as a counting keyword, so the top-5 question returned an account count.
- "Average support tickets for churned vs active accounts" was silently answered as churn rate. Now unknown measures go to the model or ask for clarification — a silent wrong answer is worse than "I don't know".
- A 24-question battery built from the business briefing found 8 phrasing gaps. I fixed them with general rules, not 24 templates.
- I wrote "ambiguous dates could change the year" in my own docs. They can't (day and month swap within the same year). I now re-check every number in a document against the database first.

## What I'd tell another engineer

I started by trying to understand the customer and their data. The model was only one part of the solution. The harder decisions involved financial definitions, system integration, validation, and making sure the customer could trust the results.

If you're building something like this: profile before you write rules, write the spec down, keep every row accountable, measure your model against an independent answer key, and leave policy decisions to the people who own them — with the evidence in front of them.

*Code, specs, evals and screenshots: github.com/florina787/Data-sets (folder `cloudnova/`).*
