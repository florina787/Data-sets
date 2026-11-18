# Flo & Jerry 3.0 — Research review for the CTO experience

Date: 2026-11-17 · Author: product/UX team (with Claude Code) · Status: **verified sources + labelled design hypotheses**

## How this review was done (and what was not possible)

* **Bibliographic details** (title, authors, venue, year, volume, pages) were verified for every cited paper against
  the Crossref DOI registry (`api.crossref.org`). Abstracts were read from Crossref or Semantic Scholar.
* **Full texts:** the Amershi et al. (2019) PDF was read in full from Microsoft Research's public copy. For Hjelle
  et al. (2024), Tractinsky et al. (2000) and Lee & See (2004) **only abstracts and secondary summaries were
  reachable** (publisher pages returned HTTP 403/503 to automated access). Claims below are limited to what those
  sources state; where we rely on a secondary summary we say so.
* We **did not** run new user studies. Every UI decision here is a **hypothesis to validate** (see the
  "Validation" column and [FLO_JERRY_3_VALIDATION.md](FLO_JERRY_3_VALIDATION.md)).
* Label key: **[E] established evidence** (peer-reviewed empirical work) · **[P] practitioner guidance** (expert
  opinion, industry guidance) · **[H] our hypothesis** (no direct evidence in the sources reviewed).

## Verified sources

| # | Source | Verified | Kind of evidence |
|---|---|---|---|
| 1 | Bhattacherjee, A. (2001). Understanding Information Systems Continuance: An Expectation-Confirmation Model. *MIS Quarterly* 25(3), 351–370. https://doi.org/10.2307/3250921 | Crossref metadata + abstract | Field survey of online-banking users; structural model |
| 2 | Amershi, S., Weld, D., Vorvoreanu, M., Fourney, A., Nushi, B., Collisson, P., Suh, J., Iqbal, S., et al. (2019). Guidelines for Human-AI Interaction. *CHI 2019*, 1–13. https://doi.org/10.1145/3290605.3300233 | Crossref + full text (MSR copy) | 18 guidelines; evaluated with 49 design practitioners against 20 AI products |
| 3 | Nielsen, J. (2006). Progressive Disclosure. Nielsen Norman Group. https://www.nngroup.com/articles/progressive-disclosure/ | Read in full | Practitioner guidance (expert opinion; cites usability testing of 46 web apps, no quantitative results) |
| 4 | Microsoft HAX Toolkit. https://www.microsoft.com/en-us/haxtoolkit/ | Read in full | Practitioner toolkit built on source 2 (Guidelines, Design Library, Workbook, Playbook) |
| 5 | Hjelle, S., Mikalef, P., Altwaijry, N., Parida, V. (2024). Organizational decision making and analytics: An experimental study on dashboard visualizations. *Information & Management* 61(6), 104011. https://doi.org/10.1016/j.im.2024.104011 | Crossref metadata; abstract via secondary indexes | Experiment with mock-up dashboards, 524 participants, two groups |
| 6 | Tractinsky, N., Katz, A. S., Ikar, D. (2000). What is beautiful is usable. *Interacting with Computers* 13(2), 127–145. https://doi.org/10.1016/S0953-5438(00)00031-X | Crossref metadata; abstract via secondary sources | Experiment with an ATM-like application, perceptions measured before and after use |
| 7 | Lee, J. D., See, K. A. (2004). Trust in Automation: Designing for Appropriate Reliance. *Human Factors* 46(1), 50–80. https://doi.org/10.1518/hfes.46.1.50_30392 | Crossref metadata; abstract (PubMed) | Integrative review and conceptual model |
| 8 | Davis, F. D. (1989). Perceived Usefulness, Perceived Ease of Use, and User Acceptance of Information Technology. *MIS Quarterly* 13(3), 319–340. https://doi.org/10.2307/249008 | Crossref metadata + abstract | Two studies, 152 users, four applications |
| 9 | Sweller, J. (1988). Cognitive Load During Problem Solving: Effects on Learning. *Cognitive Science* 12(2), 257–285. https://doi.org/10.1207/s15516709cog1202_4 | Crossref metadata + abstract | Computational model + experiments (learning context) |
| 10 | Kurosu, M., Kashimura, K. (1995). Apparent usability vs. inherent usability. *CHI '95 Companion*, 292–293. https://doi.org/10.1145/223355.223680 | Crossref metadata | Short paper (ATM layouts); abstract not available to us |

**Not verified / not used:** we did not find an accessible primary source for executive-information-system studies
specific to CTOs, or for quantified "30-second comprehension" benchmarks. Those targets in the brief are therefore
treated as **product goals [H]**, not research findings. WCAG 2.2 is used as the accessibility standard (a W3C
recommendation, not a study).

## Findings and what they mean for Flo & Jerry

### 1. Continued use depends on usefulness and confirmed expectations — not on engagement tricks
* **What the study supports [E]:** In Bhattacherjee (2001), users' *continuance intention* was determined by
  **satisfaction** and **perceived usefulness**; satisfaction was influenced by **confirmation of expectations**
  from prior use and by perceived usefulness. Davis (1989) found perceived usefulness correlated with current
  (r = .63) and predicted future usage (r = .85), more strongly than ease of use (r = .45 / .59).
* **Strength / limits:** Well-replicated constructs, but source 1 studied online-banking customers, and both use
  self-reported intentions, not observed executive behaviour.
* **Application:** The reason to return tomorrow must be *useful new information that matches what the product
  promised*: "Since your last visit", follow-ups due in the Decision Journal, outcome tracking. No streaks, badges
  or engagement nudges.
* **UI decisions:** "Since your last visit" card that says plainly *"nothing meaningful changed"* when true;
  Decision Journal with follow-up dates; homepage promises only what the data supports (expectation confirmation).
* **Validation:** Task study item "find what changed since yesterday"; post-task usefulness rating (Davis items);
  return-visit telemetry is **not** collected without consent, so we rely on interviews.

### 2. Dashboards help decisions through perceived information quality, lower perceived complexity and satisfaction
* **What the study supports [E]:** Hjelle et al. (2024) report, from an experiment with 524 participants and two
  dashboard variants, that certain information-quality dimensions affect decision-making quality **indirectly**, by
  reducing perceived task complexity and increasing information satisfaction.
* **Strength / limits:** Large sample and experimental design; we could read only the abstract, so **we do not
  claim which specific quality dimensions were significant**; mock-up dashboards, not a live enterprise tool.
* **Application:** Treat information quality (accuracy, freshness, clarity of provenance) as the main lever, and
  aim to make tasks *feel* less complex.
* **UI decisions:** every indicator shows **freshness** and **provenance** (Verified / Operational record /
  Modelled / Synthetic); at most **five** health indicators and **three** priorities on the home page; each
  priority is phrased as *What happened → Why it matters → Next step*.
* **Validation:** comprehension check ("which numbers are synthetic?"), perceived-complexity rating (single item)
  before/after redesign on the same tasks.

### 3. Reduce extraneous load; show the essentials first and keep detail one step away
* **What the sources support:** Sweller (1988) [E] shows that problem-solving search consumes working-memory
  capacity (in a learning context). Nielsen (2006) [P] recommends deferring advanced or rarely used features to a
  secondary screen, and warns that **more than two levels** of disclosure "typically have low usability".
* **Strength / limits:** Sweller's experiments concern learning, not dashboards (transfer is an assumption [H]);
  Nielsen's article is expert guidance without published effect sizes.
* **Application:** One question per screen region; technical diagnostics behind an explicit "Show diagnostics".
* **UI decisions:** 7 primary navigation items (down from 20 flat links) with **one** secondary level; developer
  controls (guided demo, run picker, storefront URL) moved out of the global header into the Technology
  workspace; Technology page asks five plain questions and reveals metrics on demand.
* **Validation:** tree-test style task ("find technology health") without training; count of clicks to reach an
  investigation (target ≤ 3).

### 4. Beauty matters to perceived usability — so polish, but never at the cost of clarity
* **What the studies support [E]:** Tractinsky et al. (2000) found strong correlations between perceived
  aesthetics and perceived usability before *and after* use, and that the system's aesthetic level affected
  post-use perceptions while its actual usability did not. Kurosu & Kashimura (1995) first reported the
  apparent-usability link (short paper).
* **Strength / limits:** Perception studies (ATM simulations); a later critique (Monk & Lelos) argues
  experiments show "usable is beautiful" more than the reverse. Aesthetics can mask poor usability, so we treat it
  as a **risk** as well as an asset.
* **UI decisions:** a calm, premium palette (Midnight Navy × Champagne Gold × Refined Teal), generous spacing,
  restrained motion; **no decoration that implies activity** (carried over from the maps work).
* **Validation:** measure task success independently of attractiveness ratings, so beauty cannot hide failures.

### 5. Human-AI interaction: say what Jerry can do, how well, why, and how to correct it
* **What the study supports [E/P]:** Amershi et al. (2019) propose 18 guidelines in four phases — *Initially*
  (G1 make clear what the system can do; G2 make clear how well it can do it), *During interaction* (G3–G6, incl.
  G4 show contextually relevant information), *When wrong* (G7–G11, incl. G9 support efficient correction,
  G10 scope services when in doubt, G11 make clear why the system did what it did), *Over time* (G12–G18, incl.
  G12 remember recent interactions, G15 encourage granular feedback, G17 provide global controls, G18 notify
  users about changes). They were evaluated with 49 practitioners on 20 products; the authors note they are not a
  checklist.
* **Strength / limits:** Strong practitioner validation of *relevance*; not an outcome study of user performance.
* **UI decisions (guideline → feature):**
  G1 capability statement in the Jerry dock · G2 "deterministic / live AI" badge and limitations line on every
  answer · G4 page-specific suggested questions · G9/G15 "Helpful / Not helpful + comment" feedback on each answer
  (stored) · G10 Jerry declines unsupported questions · G11 sources and "How this was answered" · G12 conversation
  memory + investigation history · G18 "Since your last visit".
* **Validation:** heuristic review against all 18 guidelines (table in VALIDATION.md).

### 6. Trust should be calibrated, not maximised
* **What the review supports [E, review]:** Lee & See (2004) describe misuse (over-reliance) and disuse
  (rejection) of automation, and argue design should support **appropriate** reliance. A secondary summary lists
  performance, process and purpose as bases of trust (not verified in full text).
* **UI decisions:** provenance badges on every figure; modelled forecasts always shown with **P10–P90 ranges**;
  "Verified: 0" shown openly; recommendations always show their evidence and say they need human approval.
* **Validation:** ask users to identify which items are synthetic/modelled (target: 100% correct on test items).

### 7. Accessible, responsive, inclusive
* **Basis:** WCAG 2.2 (W3C recommendation) [P]. Decisions: contrast ≥ 4.5:1 for body text on the new palette
  (checked in VALIDATION.md), visible focus rings, full keyboard paths, `prefers-reduced-motion`, table
  alternatives for every chart and the globe, layouts tested at 390, 768 and 1440 px.

## Hypotheses we hold without direct evidence [H]
1. A CTO reads the top priority in under 30 seconds when there are ≤ 3 priorities with plain-language headlines.
2. Role-specific *lenses* (which do not change permissions) reduce irrelevant content for non-technical staff.
3. A Decision Journal with follow-up dates creates a legitimate reason to return.
4. Moving developer controls out of the header lowers perceived complexity for executives without hurting engineers.

Each is listed with a validation method in [FLO_JERRY_3_VALIDATION.md](FLO_JERRY_3_VALIDATION.md).
