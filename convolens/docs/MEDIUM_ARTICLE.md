# I Built an AI Analyst That Refuses to Make Things Up

## What 3,000 real customer-support conversations, one free Gemini key, and a lot of error messages taught me about trustworthy AI

*By Florina*

---

Here's a confession: the first time I asked my AI assistant **"What is our CSAT score?"**, I was secretly hoping it would get it wrong.

Not because I wanted it to fail, but because I had spent days teaching it one rule above everything else: **never make up a number.** The dataset I was using has no satisfaction ratings at all. So the only honest answer was some version of *"I can't tell you that."*

It said:

> **Not available from this data.** CSAT or satisfaction ratings are not present in this dataset. Inferred sentiment is available but is not a satisfaction score.

I may have done a small victory dance. 💃

This is the story of **ConvoLens AI**, a customer conversation intelligence app, and of **Flo**, the AI analyst who lives inside it. I'll show you:
- what it does,
- how you can run it yourself, for free,
- and the challenges and error messages that nearly broke me along the way. I've included all of them, with the actual error text, because I wish more people wrote about the messy middle.

**🔗 The code:** [github.com/florina787/Data-sets — `convolens/`](https://github.com/florina787/Data-sets/tree/claude/awesome-bohr-jqq4uz/convolens)

![Flo, the chatbot: type a question in the box at the bottom](https://raw.githubusercontent.com/florina787/Data-sets/claude/awesome-bohr-jqq4uz/convolens/docs/screenshots/00-flo-chatbot-typing.png)

---

## 📌 The 30-second version

- **The data:** 3,000 real customer-support conversations from the open-source Kaggle dataset **Customer Support on Twitter**: real customers talking to AmazonHelp, AppleSupport, Uber_Support, Delta, SpotifyCares and others.
- **The app:** dashboards, charts and interactive maps showing *what customers contact you about*, *which conversations end unresolved*, and *what to fix first*.
- **The AI:** **Flo**, a chatbot built as a LangGraph agent. It plans, calls tools, counts with SQL, quotes real messages, **checks its own claims before replying**, and **asks a human before saving anything**.
- **The twist:** I connected a **free Google Gemini key**. On the same 300 conversations, the share with a real topic jumped from **54% to 96%**, and conversations with a visible outcome went from **22 to 59**. The whole run cost **21 free requests**.

---

## 🤔 Why I built this

If you've ever worked near a customer support team, you know the feeling. There are thousands of conversations, and everyone has an opinion about *why* customers are unhappy. Few people have evidence.

AI summaries seem like the obvious fix. Paste in conversations, get insights. But here's the problem nobody talks about enough:

> **A confident AI summary without numbers you can check is a liability in a leadership meeting.**

If an AI says *"38% of refund conversations are unresolved"*, someone in that meeting will ask: *38% of what? Which conversations? Show me.* If you can't answer, you've lost the room.

So I set myself a challenge: **build an AI analyst whose every number and every claim can be audited.**

### 🎯 Pause and predict

Before you read on, guess: of 3,000 real public support conversations on Twitter, how many do you think show a clear outcome *in the thread itself*? A customer saying "fixed, thanks!" counts, and so does "still broken".

- **A)** about 80%
- **B)** about 50%
- **C)** about 20%
- **D)** less than 10%

*(The answer is further down. It surprised me.)*

---

## 🧭 What ConvoLens does

The whole product follows one chain. I drew it on a sticky note on day one and never changed it:

**Conversation data → calculated metrics → evidence-backed investigation → proposed decision → human review → assigned action → impact measurement**

Each step answers a question a support leader actually asks:

| Question | What ConvoLens does |
|---|---|
| What problems deserve attention? | Labels every conversation (topic, outcome, sentiment, escalation request) and counts them **exactly** in SQL |
| What's the evidence? | Every claim cites a real customer message, and **one click opens it** |
| What should we fix first? | An opportunity portfolio with a **visible** scoring formula |
| Who owns the fix? | Flo **proposes**, a human **approves**, and the owner is confirmed by a person |
| Did it work? | Before/after comparison, with a warning that a difference ≠ proof |

![Executive overview on the real data](https://raw.githubusercontent.com/florina787/Data-sets/claude/awesome-bohr-jqq4uz/convolens/docs/screenshots/01-overview-real.png)

---

## 💬 Meet Flo

Flo is the chatbot on every page. I gave Flo a small teal circle with an **F** in it, and **no fake human persona**. No "Hi, I'm Flo, your Senior Insights Manager! 😊". Just:

> *"Hello, I'm Flo. I can help you investigate customer issues, compare conversation patterns, and prepare evidence-backed decisions."*

Here's what happens when you ask Flo a real question:

![Flo's answer, annotated](https://raw.githubusercontent.com/florina787/Data-sets/claude/awesome-bohr-jqq4uz/convolens/docs/screenshots/00-flo-chatbot-answer.png)

1. **Flo knows your context.** If you filtered the dashboard to *Billing & refunds* and ask *"Why is this happening?"*, Flo analyses **that** scope and tells you so.
2. **Every answer has the same structure:** Finding → Scope and denominator → Supporting evidence → Limitations → Proposed next action.
3. **Numbers are tagged** (`M1`, `M2`…). Each one is an exact SQL count with its denominator, like *13 of 79*.
4. **Quotes are tagged** (`E1`, `E2`…). Click one and you jump to that exact message in the conversation.
5. **Patterns ≠ causes.** For "why" questions, Flo says plainly that these are *reported patterns, not verified causes*.

### 🎮 Try these questions yourself

Once you've got it running (instructions below), type these into Flo's chat box:

- `Brief me on this dataset.`
- `Investigate unresolved issues.`
- `Compare resolved and unresolved conversations.`
- `Show the evidence behind this chart.`
- `Prepare a decision brief.`
- `Propose an action to reduce unresolved refund issues.` ← watch it **pause** for your approval
- `What is our CSAT score?` ← my favourite 😄

---

## 🚀 How to use it yourself (step by step)

You don't need any API keys to start. ConvoLens has a **Demonstration mode** with clearly labelled synthetic conversations and transparent rules.

### Step 1: Get the code

```bash
git clone https://github.com/florina787/Data-sets.git
cd Data-sets
git checkout claude/awesome-bohr-jqq4uz
cd convolens
```

### Step 2: Start the backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Step 3: Start the frontend (in a second terminal)

```bash
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. You'll see the demo data and Flo on the right. Try clicking a bar in the topic chart: every chart on the page filters at once.

### Step 4: Add the real Kaggle data

1. Download **Customer Support on Twitter** from Kaggle (you get a zip containing `twcs.csv`).
2. Import it:

```bash
cd backend
uv run python -m app.ingestion.cli file ~/Downloads/twcs/twcs.csv
uv run python -m app.ingestion.cli list
```

The importer rebuilds conversations, picks **up to 3,000** with a fixed random seed (anyone can reproduce the same selection), removes personal data, and writes an import manifest.

### Step 5: Turn on the AI with a free Gemini key

1. Go to **aistudio.google.com/apikey** and click **Create API key**. The free tier needs no credit card.
2. Then run:

```bash
export MODEL_PROVIDER=gemini
export GOOGLE_API_KEY=your_key_here
export GEMINI_MODEL=gemini-3.5-flash-lite
export MODEL_REQUESTS_PER_MINUTE=8
uv run python -m app.ingestion.cli analyze <dataset_id> --batch-size 15
```

3. In the app, switch the top bar to **Connected analysis**.

> 💡 **Tip:** the free tier has **daily request limits per model**. Batching 15 conversations per request is what makes it workable. More on that pain below. 😅

Prefer Docker? `docker compose up --build`, then open http://127.0.0.1:8080.

---

## 🧗 The challenges (the honest, messy middle)

This is the part I wish more people wrote. Every error message below is real.

### Challenge 1: I couldn't even download the dataset 🚫

I built most of this in a locked-down cloud environment. My very first attempt to fetch the data:

```
curl: (56) CONNECT tunnel failed, response 403
```

So I tried Kaggle's own library, `kagglehub`:

```
requests.exceptions.ProxyError: HTTPSConnectionPool(host='api.kaggle.com', port=443):
... Tunnel connection failed: 403 Forbidden
```

The environment's network policy blocked Kaggle completely. Hugging Face was blocked too, which is why semantic search with downloaded embeddings is still untested.

**What I did:** I didn't wait. I built the whole pipeline against **synthetic data in the exact Kaggle schema**, with deliberate defects baked in: duplicate rows, a reply loop, missing parents, an invalid boolean, a broken timestamp, and even a **prompt-injection attack** hidden in a customer tweet. When the real data finally arrived, the pipeline already knew how to handle every one of those.

**Lesson:** build against the *schema*, not the *file*. And make your test data nasty.

### Challenge 2: The 20 MB upload limit vs a half-gigabyte file 📦

When I finally had the Kaggle zip on my laptop, I hit the next wall: the upload limit was **20 MB**, and `twcs.csv` is about **half a gigabyte**.

My first instinct was a quick pandas script:

```python
df = pd.read_csv(csv_file, nrows=5000)
```

It ran, but it was quietly wrong in **two** ways:

1. **It split conversations.** The first 5,000 rows of the file are not 5,000 complete conversations. Replies are scattered all over the file, so you get half-conversations whose parent messages are missing.
2. **It corrupted the IDs.** Because `in_response_to_tweet_id` has blank cells, pandas turns the column into floats. So `119237` became `119237.0`. 🙃

**What I did:** I wrote small tools that keep **only complete conversation threads**. They follow the reply links, group them, and pick whole threads until the file fits, keeping every ID as the exact original string.

A bonus bug in my own zip-shrinking tool: my "maximum compression" attempt produced a **289 MB** zip from a 290 MB file. The cause:

```python
zipfile.ZipInfo(name)   # defaults to ZIP_STORED, i.e. NO compression
```

The ZIP *archive* was set to compress, but each *entry* I created defaulted to "stored". One line fixed it, and taught me never to trust a size until I've printed it.

### Challenge 3: A tweet is not a conversation 🧵

This was the intellectual heart of the project. The dataset is a flat list of tweets. Each tweet points to the tweet it replies to. To analyse *conversations*, I had to rebuild them as **reply trees**, and real data is messy:

| Problem | Real count in my data |
|---|---|
| Replies whose parent isn't in the file | 154 |
| Conversations not started by a customer (brand broadcasts) | 577 |
| Conversations over 50 messages | 16 |
| Conversations with **branching** replies (one message, several answers) | 420 of the 3,000 selected |
| Reply **loops** (A replies to B, which replies to A) | 0 in the real data, but my synthetic test file had one, and it broke an early version |

I made three rules I'm proud of:
- **The unit of analysis is a reply tree.** Every message belongs to exactly one conversation, so nothing is ever counted twice.
- **Branches stay inside one conversation.** They're never flattened into separate ones.
- **Two exchanges are never merged** just because the same person wrote them.

Then: **159,240 tweets → 41,661 conversations → 40,914 eligible → 3,000 selected** with a fixed seed, and every exclusion recorded with its reason.

### Challenge 4: My language detector thought English was French 🇫🇷

I wanted language detection *per message*, not per conversation, because people switch languages mid-chat. My first library, `langdetect`, labelled these English messages as **French**:

> *"We've sent an engineer appointment request, you'll get a confirmation text."*

And this one as **mixed language**:

> *"This is unacceptable, I'm filing a formal complaint"*

It was apparently detecting traces of Tagalog. 🤷‍♀️

**What I did:** I switched to `lingua`, restricted it to likely languages, and required a confidence margin. A message only counts as "mixed" if each segment is confidently a different language. Short tweets like *"hello??"* now honestly get **unknown**.

I also built a small lexicon for **Romanized Hindi (Hinglish)**, e.g. *"mera refund abhi tak nahi aaya hai"*, which most detectors miss completely.

### Challenge 5: My approval button did… nothing 😶

Flo is allowed to *propose* an action, but it must **pause** and wait for a human before saving. LangGraph has a feature for exactly this, `interrupt()`. In my first test, the approval card never appeared, and the action list stayed empty.

The bug was my own error handling. I'd wrapped every workflow step in a friendly `try/except` that turned errors into readable messages. But `interrupt()` *works* by raising a special exception (`GraphInterrupt`), and I was catching it and swallowing the pause. 🤦‍♀️

```python
except GraphInterrupt:
    raise  # let LangGraph pause here
except Exception as exc:
    ...
```

Right after that came a sneakier bug. The approval event finally fired, but the frontend never noticed it, because I'd written:

```python
yield {"type": "approval_required", **payload}
```

The payload *also* had a `"type"` key, so it silently overwrote mine. Swapping the order fixed it.

Then I tested the most important property: **approve twice, get one record.** ✅ (Idempotency keys for the win.)

### Challenge 6: The page that went completely blank ⬜

I clicked a citation to jump to the cited message, and the entire app turned into an empty grey rectangle. The browser console said:

```
TypeError: Invalid option : timeStyle
```

I'd used `toLocaleDateString()` with a time option. It only accepts date options, and `toLocaleString()` is the right call. One crashed date formatter took down the whole React page.

**Lesson:** a citation feature is only trustworthy if the click actually lands. I now test it in a real browser, end to end.

### Challenge 7: My fact-checker fact-checked the customers 🔍

Flo checks every number in its own answer against the validated SQL results. In my first evaluation, **7 out of 8 answers failed** that check.

Why? The checker was flagging numbers from **customer quotes**: *"why was I billed $59.99 when the price was $39.99?"*. Those numbers aren't Flo's claims; they're evidence. I taught the checker to allow numbers that appear in quoted evidence, stated limitations, or your own question, and to keep rejecting anything else.

To prove it works, I wrote a test with a fake model that confidently claims *"87% of customers churned, costing 120000 dollars"*. ConvoLens blocks the answer and shows only verified results. 🛡️

### Challenge 8: Docker didn't trust the internet 🐳

The Docker build failed on its first line:

```
SSL: CERTIFICATE_VERIFY_FAILED ... self-signed certificate in certificate chain
ERROR: Could not find a version that satisfies the requirement uv==0.11.32
```

That was the sandbox's network proxy, not my Dockerfile. Before that, the Docker daemon wasn't even running:

```
failed to connect to the docker API at unix:///var/run/docker.sock
```

**What I did:** I started the daemon, verified the build with a *temporary* variant that trusted the proxy's certificate, and kept the real Dockerfiles clean. Both containers then ran, with the health check passing and Flo streaming through nginx with zero security-policy errors.

### Challenge 9: Connecting Gemini, a six-error saga 🤖

This one deserves its own blog post. I wanted a *free* way to show real AI labelling, so I got a free Google AI Studio key. Here's what happened, in order.

**Error 1: wrong kind of key.** I'd stored the key as a Bearer token. Gemini's main API replied:

```
"code": 401, "Request had invalid authentication credentials.
Expected OAuth 2 access token..."
```

**Fix:** Gemini also has an **OpenAI-compatible endpoint** that accepts the key as a Bearer token. ✅

**Error 2: the model had retired.**

```
"This model models/gemini-2.5-flash is no longer available to new users.
Please update your code to use models/gemini-3.8-flash"
```

**Error 3: the recommended model was too popular.**

```
"code": 503, "This model is currently experiencing high demand."
```

(Plus a `502 upstream request failed`, for variety.)

**Error 4: the model "thought" too much.** One response came back completely empty:

```
'output_tokens': 0, 'total_tokens': 2621
```

The model had spent its whole output budget on internal "thinking" tokens. **Fix:** give it more room and lower the thinking effort.

**Error 5: my schema was "invalid".**

```
"code": 400, "Request contains an invalid argument."
```

Single-conversation requests worked. Batch requests failed. After isolating it, I found the culprit: Gemini rejected my **nested JSON schema**, where array items pointed to shared definitions. **Fix:** flatten the schema before sending it, then validate the full structure with Pydantic afterwards.

**Error 6: I ran out of free requests while debugging.** 😭

```
"Quota exceeded for metric: generate_content_free_tier_requests,
limit: 20, model: gemini-3.6-flash ... Please retry in 7h1m11s."
```

**Twenty requests per day.** My debugging had used them all.

**Fix:** switch to **Flash-Lite**, put **15 conversations in each request**, set a hard request cap, turn **off** automatic retries (each retry costs quota), and cache every label so nothing is ever sent twice.

### Challenge 10: The AI was confident, and sometimes wrong 🎭

With Gemini working, the first batch looked great: every conversation got a neat topic and outcome. Then I looked closer.

- It returned **zero evidence quotes**. The `evidence` field was optional, so the small model simply skipped it.
- A tweet that said only **"@O2 ? [URL]"** was labelled **customer-confirmed resolved**. 🤨

**What I did:** I added one rule that changed everything.

> **Any label without a verified quote becomes "unknown".**

I also made evidence a **required** field. The next batch came back with real quotes, every one matching the stored message exactly, such as *"worried about making my connection :("* for a travel disruption.

I added two more fixes:
- **Ending sentiment** now counts only if the customer **wrote again**. A one-message conversation can't show how someone *ended up* feeling, but the model guessed anyway, 162 times.
- **A privacy gap.** A support reply said *"Hi Debbie, what flight are you on?"*, and my redaction missed the first name. I added a rule for names in greetings and **re-imported everything before any text reached the AI**. That removed 536 names.

### Challenge 11: "Don't exhaust my free key!" 🙅‍♀️

Mid-run, I realised my labelling job could burn through the entire free quota. I stopped it after **one** request and set a budget: **25 requests, total**.

The final run used **21**: 20 batches, plus one retry after a Google gateway error. Embarrassing footnote: my request counter printed **0** the whole time, because the callback never fired. Thankfully the cap still held, since 300 conversations ÷ 15 per request = 20 requests, with automatic retries turned off. Always have a second safety net. 😅

### Challenge 12: I killed my own terminal 💀

To restart my server, I ran `pkill -f "uvicorn ..."`. The pattern also matched **the shell running the command**. Exit code 144. Silence.

No lesson here, really. I just think you deserve to know. 🙃

---

## 📊 The results: what changed when a real LLM joined

Remember the "pause and predict" question? Here's the answer.

**With keyword rules, only 22 of 300 conversations showed a clear outcome in the thread. With Gemini, 59 of 300, about 20%.** So the answer is **C**. Most public support conversations quickly move to private messages ("please DM us"), so the outcome is simply not visible. ConvoLens says *unknown* instead of pretending.

![Keyword rules vs Gemini on the same 300 conversations](https://raw.githubusercontent.com/florina787/Data-sets/claude/awesome-bohr-jqq4uz/convolens/docs/screenshots/gemini-vs-rules.png)

| Same 300 real conversations | Keyword rules | Gemini (free tier) |
|---|---|---|
| Conversations with a real topic | 163 | **287** |
| Left as "other" or "unknown" | 137 | **13** |
| Outcome visible in the thread | 22 | **59** |
| Customer-confirmed resolved | 3 | **21** |
| Explicitly unresolved | 2 | **10** |
| Escalation requested | 14 | **4** (stricter) |
| Verified evidence quotes | — | **374** |

Three things surprised me:

1. **Keyword rules can't read real people.** *"Why is your rice always undercooked"* has none of my keywords, so the rules called it "other". Gemini knew it was a service complaint instantly.
2. **The AI was *stricter* about escalation.** Rules flagged any tweet containing "complaint". Gemini only flagged explicit requests like *"I asked for a supervisor or senior manager"*.
3. **These are differences, not accuracy scores.** Without human-checked labels, I can't say which is *right*, only how they *differ*. The app has reviewer-correction buttons, so that's the next step.

![A real conversation with Gemini's evidence highlighted](https://raw.githubusercontent.com/florina787/Data-sets/claude/awesome-bohr-jqq4uz/convolens/docs/screenshots/gemini-explorer-real.png)

---

## 🛡️ The guardrails I'd put in any AI analyst

If you remember one section, make it this one:

1. **Let SQL do the counting.** The model plans and explains; it never computes a number.
2. **Validate every claim before showing it.** Check numbers against tool results, and check quotes against stored text.
3. **No evidence, no label.** Downgrade to "unknown" and record the downgrade.
4. **Refuse what the data can't support.** CSAT, revenue, churn and location get a clear "not available".
5. **Treat customer text as untrusted data.** Someone *will* type "IGNORE ALL PREVIOUS INSTRUCTIONS" into a support chat. Mine did, in the test data, on purpose.
6. **Pause for humans before any write.** And make sure approving twice can't create two records.
7. **Fail loudly.** If the model is down, show an error. Never quietly switch to a weaker method.
8. **Report quality per language.** One overall score hides the languages where you're weakest.

---

## 🧠 Quick quiz (answers below, no peeking!)

1. Why can't you just use the first 5,000 rows of the dataset?
2. Why did `119237` become `119237.0`?
3. What happens to a Gemini label that has no supporting quote?
4. How many free Gemini requests did the 300-conversation labelling cost?
5. What does Flo say when you ask for the CSAT score?

<details>
<summary>Answers</summary>

1. Replies are scattered across the file, so you'd split conversations and lose their parent messages.
2. pandas turns a numeric column with blank cells into floats.
3. It becomes "unknown", and the downgrade is recorded.
4. 21: 20 batches of 15, plus one retry.
5. "Not available from this data", with no invented number.

</details>

*(Medium doesn't support collapsible answers, so on Medium the answers simply appear here.)*

---

## 📋 What's honestly not done yet

I promised myself this project would never overclaim, so:

- **Flo's live chat on the real data with Gemini** isn't shown yet. I skipped it to protect the free daily quota. The code path is tested with scripted models.
- **Gemini labelling covers 300 conversations, not all 3,000.** The rest would take about 180 more requests, several days of free quota.
- **There are no human-checked labels yet,** so accuracy isn't measured.
- **Some agent sign-offs**, like "~ Jess", still slip through redaction.

---

## 🙌 Try it, break it, tell me

Everything is open source:

**👉 [github.com/florina787/Data-sets — `convolens/`](https://github.com/florina787/Data-sets/tree/claude/awesome-bohr-jqq4uz/convolens)**

Clone it, run it, ask Flo something tricky, and please tell me where it breaks. And if you've ever had an AI tool confidently hand you a made-up number in front of your boss… I see you. This one's for us. 💙

*— Florina*

---

*Data: "Customer Support on Twitter" by Thought Vector on Kaggle (CC BY-NC-SA 4.0). The dataset is not included in the repository. Customer handles and names in screenshots are redacted.*

**Tags:** `Artificial Intelligence` · `LLM` · `Customer Experience` · `LangGraph` · `Data Science`
