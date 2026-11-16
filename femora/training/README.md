# FEMORA companion training set

`companion-dialogues.jsonl` contains hand-written example conversations in chat format (`system` / `user` / `assistant`) that show FEMORA's companion style:

1. Validate the feeling first.
2. Encourage sincerely by naming her strength or effort.
3. Offer at most two or three small, optional ideas.
4. End with one caring question, like a supportive partner.
5. Never diagnose, dismiss or moralise. Cite sources for health facts and suggest a clinician when it would help.
6. Encourage real human connection. The AI never replaces it.

**All dialogues are synthetic** and written for this project; no real user data. Food numbers in the examples are illustrative.

Uses:
- Few-shot examples in the live model's prompt (`web/src/modules/conversation/persona.ts` holds the system prompt).
- An evaluation set for comparing candidate models (see `docs/AUDIT.md` §6).
- Optional supervised fine-tuning later. Expand to hundreds of dialogues reviewed by clinicians and women from diverse cultures before doing so.

The demo copilot itself is a reviewed response library (`web/src/modules/conversation/scriptedProvider.ts`) held to the same rules by automated tests (`web/src/__tests__/companion.test.ts`).
