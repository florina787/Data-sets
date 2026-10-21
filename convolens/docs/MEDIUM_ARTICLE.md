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

**🔗 The code:** [github.com/florina787/Data-sets — `convolens/`](https://github.com/florina787/Data-sets/tree/master/convolens)

![Flo, the chatbot: type a question in the box at the bottom](https://raw.githubusercontent.com/florina787/Data-sets/master/convolens/docs/screenshots/00-flo-chatbot-typing.png)

---

## 📌 The 30-second version

- **The data:** 3,000 real customer-support conversations from the open-source Kaggle dataset **Customer Support on Twitter**: real customers talking to AmazonHelp, AppleSupport, Uber_Support, Delta, SpotifyCares and others.
- **The app:** dashboards, charts and interactive maps showing *what customers contact you about*, *which conversations end unresolved*, and *what to fix first*.
- **The AI:** **Flo**, a chatbot built as a LangGraph agent. It plans, calls tools, counts with SQL, quotes real messages, **checks its own claims before replying**, and **asks a human before saving anything**.
- **The twist:** I connected a **free Google Gemini key**. On the same 300 conversations, the share with a real topic jumped from **54% to 96%**, and conversations with a visible outcome went from **22 to 59**. That labelling run cost **21 free requests**.
- **Then it went live:** Flo now answers questions on the real data with Gemini (about 2 requests per question, every number checked), search understands meaning thanks to Gemini embeddings, and a **blind human-review page** measures which labels are actually *right*.
- **Then I audited myself:** I asked for a ruthless, evidence-only audit of my own project. It found a bug that counted tokens up to **35 times over** and would have broken every live action proposal. Challenges 18–21 are that story.

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

![Executive overview on the real data](https://raw.githubusercontent.com/florina787/Data-sets/master/convolens/docs/screenshots/01-overview-real.png)

---

## 💬 Meet Flo

Flo is the chatbot on every page. I gave Flo a small teal circle with an **F** in it, and **no fake human persona**. No "Hi, I'm Flo, your Senior Insights Manager! 😊". Just:

> *"Hello, I'm Flo. I can help you investigate customer issues, compare conversation patterns, and prepare evidence-backed decisions."*

Here's what happens when you ask Flo a real question:

![Flo's answer, annotated](https://raw.githubusercontent.com/florina787/Data-sets/master/convolens/docs/screenshots/00-flo-chatbot-answer.png)

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
cd Data-sets/convolens
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
export MODEL_MAX_RETRIES=0
uv run python -m app.ingestion.cli analyze <dataset_id> --batch-size 15 --max-requests 12
```

3. In the app, switch the top bar to **Connected analysis**.

> 💡 **Tip:** the free tier has **daily request limits per model**. Batching 15 conversations per request, and stopping at a cap, is what makes it workable. More on that pain below. 😅

### Step 6 (optional): Search by meaning, and label a little every day

```bash
# Embed customer messages once (paced for the free tier, cached forever)
uv run python -m app.ingestion.cli embed <dataset_id> --max-texts 700
export EMBEDDING_PROVIDER=gemini     # then restart the backend

# One capped day of labelling; run it again tomorrow to continue
DATASET_ID=<dataset_id> MAX_REQUESTS=12 ../scripts/daily_label.sh
```

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

The environment's network policy blocked Kaggle completely. Hugging Face was blocked too, so I couldn't download an embedding model for semantic search. (Spoiler: Gemini rescued that later, in Challenge 15.)

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

### Challenge 13: "~ Jess" kept slipping through 🕵️‍♀️

My redaction removed customer handles, emails, phone numbers and greeting names. But support agents on Twitter sign their replies: *"…we'll sort this out ~ Jess"*, *"^MK"*, *"-Dan"*. Those are real staff names, and they were flowing straight to the model.

The tricky part: *"~ Jess"* at the end of a **support** message is a signature. The same shape in a **customer** message might be anything. So the new rule only strips sign-offs from support messages, with a small list of words that look like sign-offs but aren't names (*"^Team"*, *"-Support"*).

That removed **2,723** sign-offs from the 3,000 conversations. I re-imported everything, and only **42** conversations changed enough to need re-labelling, because labels are cached by a hash of the redacted text. Three free requests. 🎉

### Challenge 14: Flo meets Gemini, and the tools won't fit 🧩

Labelling worked, but Flo's *planning* step failed on Gemini. The planner returns a list of tool calls, each with its own arguments, so the schema had an open-ended "arguments" object. Gemini's structured output wants every field spelled out in advance, and an "anything goes" object didn't fit.

**Fix:** the planner now returns arguments as a **JSON string** (`{"top_n": 5}`). I parse it, validate it against the tool's own typed schema, and reject anything invalid *before* a tool runs. It's less elegant, but safer.

Then the first live answer came back, and the citations looked like this: **[E1, E2, E3, E4, E5]**. Plain text, not clickable. My renderer expected one reference per bracket. It now splits a group into one button each, with a test so it stays that way.

The result: **Flo's first live answer on real data, with every claim validated, in 9.2 seconds, for 2 free requests.**

![Flo answering a real question with Gemini, claims validated](https://raw.githubusercontent.com/florina787/Data-sets/master/convolens/docs/screenshots/flo-gemini-live-1.png)

### Challenge 15: Embeddings, and the request that counts 100 times 🔢

With Hugging Face blocked, I tried Gemini's own embedding model for semantic search. One test call with two sentences worked perfectly. So I sent 100 messages in one batch request, and got:

```
"code": 429, "Quota exceeded for metric:
generativelanguage.googleapis.com/embed_content_free_tier_requests, limit: 100"
```

On the free tier, **every text in a batch counts as one request**, with a limit of 100 per minute. My single "request" was really 100, plus the 2 from the test.

**What I did:**
- **Embed only customer messages.** That's what search looks at by default, and it halves the cost. Support replies stay searchable by keyword.
- **Pace it** at 90 texts per minute.
- **Cache every vector forever**, keyed by a hash of the text. A message is paid for once; after that, a search costs about one request.

It was worth it. For *"my package never showed up"*, keyword search returned a food-delivery cancellation and **an Uber free-ride complaint** (it matched on "never"). Semantic search returned four genuinely missing parcels: *"tracking says they were handed to resident"*, *"Where is it???"*.

![Hybrid keyword + Gemini semantic search](https://raw.githubusercontent.com/florina787/Data-sets/master/convolens/docs/screenshots/semantic-search-gemini.png)

### Challenge 16: The crash that cost nothing (luckily) 💥

To label all 3,000 on the free tier, I wrote a daily script: label up to 12 batches, stop, continue tomorrow. Its first run died instantly:

```
sqlite3.IntegrityError: UNIQUE constraint failed: analyses.conversation_id, analyses.method, ...
```

My cache reuses a label when the same conversation text was already labelled anywhere. But it looked up *the oldest* matching label, which belonged to another dataset, and then copied it onto a conversation that **already had its own copy**. Two identical rows → boom.

The good news: it crashed while checking the cache, **before calling Gemini**, so not a single free request was wasted. I wrote a test that fails without the fix, then fixed it: always prefer the conversation's own row.

The rerun labelled 67 new conversations. Five of its 10 requests failed with `upstream request failed`, Google's gateway having a moment. Failed conversations are stored as *failed*, never cached, so tomorrow's run retries them.

### Challenge 17: "Why is everything unknown?" 🤷

Every dashboard I showed had the same awkward bar: **outcome unknown** for most conversations. People kept asking why.

I knew the answer from reading threads: support says *"Can you DM us your order number?"*, and the rest happens in private. But "I read some threads" isn't evidence. So I made it a label: a **private-channel** flag, set only when the thread *shows* it, with the quote attached.

The numbers on the 3,000: support asked to move to DMs in **994**, customers confirmed in **85**. **36%** of conversations leave the public thread. Now the overview has a banner, *"Why are outcomes often unknown?"*, and one click shows exactly those conversations.

And when I asked Flo *"does moving to a private channel lead to resolution?"*, it put the two numbers side by side and **did not claim a causal link**. That's the behaviour I spent weeks building. 💙

![Flo on private channels: numbers side by side, no causal claim](https://raw.githubusercontent.com/florina787/Data-sets/master/convolens/docs/screenshots/flo-gemini-live-2.png)

---

### Challenge 18: I asked for an audit, and it found a real bug 🔬

When everything looked finished, I did the scariest thing I could think of: I asked for a rigorous audit of my own project. The rules were strict. Don't trust the dashboard, read the code, query the database directly, and run the real thing. And never claim something passed without proof.

Most of it held up. The 3,000 conversations were really 3,000 threads, 11,359 messages, every one starting with a customer. LangGraph really ran seven steps, Gemini really planned and wrote the answer, and every number in Flo's answer matched an independent SQL recount.

Then the audit compared the **size of a prompt** with the **tokens it was reported to cost**. A prompt of about 3,900 characters was recorded as **35,376 input tokens**. Text averages about 4 characters per token. That number was impossible.

I streamed one tiny answer from Gemini and printed what every chunk reported:

```
1 'Parcels arrive on our doorstep'   {'input_tokens': 8, 'output_tokens': 14}
2 ' tape. Opening them feels like'   {'input_tokens': 8, 'output_tokens': 38}
3 ' every day.'                      {'input_tokens': 8, 'output_tokens': 41}
4 ''                                 {'input_tokens': 8, 'output_tokens': 41}
SUMMED (my old code): {'input_tokens': 32, 'output_tokens': 134}
```

There it was. Gemini repeats the **running total** on every chunk, and my code added the chunks together. On that tiny test the real cost was 8 tokens in, 41 out, and I recorded 32 and 134. On a real answer with dozens of chunks, the error grew to 13–35 times.

### Challenge 19: Why a wrong number was a broken feature 💣

A wrong cost figure is embarrassing. But this one was dangerous, and here's why.

Flo has a safety budget: any run that goes over **24,000 tokens** is stopped. It's there so a confused agent can't run up a bill. With the over-count, a perfectly normal answer "cost" around 50,000 tokens. The next step after writing the answer is the **approval pause**, and it checks the budget first.

So any time someone asked Flo to *propose an action*, it would write the brief, reach the approval step, and stop with:

```
Model token budget of 24000 exceeded
```

My most important safety feature, human approval before saving anything, was unreachable on Gemini. I'd only ever tested approvals in demo mode and with scripted test models, which reported usage once. Real providers don't all behave the same way.

**The fix** was a small class, `StreamUsage`, that recognises the three ways providers report streaming usage:
- a **running total on every chunk** (Gemini): use the last one,
- **one final report** (many OpenAI-style APIs): use it,
- **per-chunk increments** (Anthropic-style): add them up.

If no chunk reports usage at all, it says **"missing"** rather than guessing. I wrote the test first, with a fake model that streams like Gemini, and watched it fail on the old code with exactly the budget error. Then I fixed it and watched it pass.

The live check afterwards:

| Same live answer | Input tokens | Output tokens |
|---|---|---|
| Gemini's own report | 603 | 293 |
| My old code | 8,442 | 2,186 |
| My fixed code | **603** | **293** |

### Challenge 20: The model forgot what I asked for 🙃

With the budget fixed, I asked Flo live: *"Propose an action to reduce unresolved billing and refund issues."*

It answered nicely, and never proposed an action. The small model, `gemini-3.5-flash-lite`, had planned some counts and a search, and simply left out the action step.

Flo already knew, from a simple rule, when a user explicitly asks for an action. So now, if you clearly ask for one and the model's plan leaves it out, Flo uses its standard action plan: a decision brief from SQL counts and evidence, then a draft action. **The draft still waits for a person to approve it.** The fallback only makes sure your request isn't silently dropped; it never skips the human.

The same question, live again: it stopped at the approval card, nothing saved, 11.7 seconds.

**Lesson:** test the path your users will actually take, with the model they'll actually use. My scripted tests were too polite.

### Challenge 21: Measuring search instead of admiring it 📏

I'd been proudly showing one search example: *"my package never showed up"*. One example is an anecdote, not a measurement. So I wrote 17 reworded support questions, deliberately avoiding the words customers actually used: *"my money back still hasn't shown up"*, *"locked out of my account"*, *"waited on hold for an hour"*.

Then I ran each one through three kinds of search on the 300 real conversations that have Gemini labels and embeddings:

| Search mode | Precision@5 | Wrong results in top 5 |
|---|---|---|
| Keyword | 0.34 | 66% |
| Semantic (Gemini embeddings) | **0.67** | **33%** |
| Hybrid (both, equal weight) | 0.60 | 40% |

Two surprises. Semantic search **doubled** precision. And my "best of both worlds" hybrid scored *below* semantic alone, because giving weak keyword matches an equal vote drags good results down.

I didn't tune the weights on these same 17 questions. That would just teach the system to pass my own test. It's on the list, with a fresh question set.

One honest caveat: "relevant" here means the result's conversation has the right topic according to **Gemini's** labels. That's a silver standard, not human ground truth. The human review page exists for exactly that reason.

## 📊 The results: what changed when a real LLM joined

Remember the "pause and predict" question? Here's the answer.

**With keyword rules, only 22 of 300 conversations showed a clear outcome in the thread. With Gemini, 59 of 300, about 20%.** So the answer is **C**. Most public support conversations quickly move to private messages ("please DM us"; that's 36% of them, see Challenge 17), so the outcome is simply not visible. ConvoLens says *unknown* instead of pretending.

![Keyword rules vs Gemini on the same 300 conversations](https://raw.githubusercontent.com/florina787/Data-sets/master/convolens/docs/screenshots/gemini-vs-rules.png)

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
3. **These are differences, not accuracy scores.** Without human-checked labels, I can't say which is *right*, only how they *differ*. So I built a way to find out (next section).

![A real conversation with Gemini's evidence highlighted](https://raw.githubusercontent.com/florina787/Data-sets/master/convolens/docs/screenshots/gemini-explorer-real.png)

### So which one is right? Ask a human, blind 🙈

I added a **Human review** page. It shows one conversation and asks you to pick the topic, outcome, sentiment and escalation yourself, **with the AI's answers hidden**. If you saw Gemini's label first, you'd be tempted to agree with it. Only after you submit does it reveal what the rules and Gemini said.

Every review becomes a "gold" label, and each system is scored against them, field by field, with a **95% confidence interval**. Conversations come in a fixed random order, so the reviewed ones are a fair sample. With fewer than 30 reviews, the page warns you that the intervals are too wide to call a winner. If a second person reviews the same conversation, it also measures how often *humans* agree, which tells you how hard the task really is.

![Blind human review: label first, then see what the AI said](https://raw.githubusercontent.com/florina787/Data-sets/master/convolens/docs/screenshots/human-review.png)

My next weekend: 100 reviews, and the first real accuracy numbers.

---

## 🛡️ The guardrails I'd put in any AI analyst

If you remember one section, make it this one:

1. **Let SQL do the counting.** The model plans and explains; it never computes a number.
2. **Validate every claim before showing it.** Check numbers against tool results, and check quotes against stored text.
3. **No evidence, no label.** Downgrade to "unknown" and record the downgrade.
4. **Measure accuracy blind.** Hide the AI's answer from the person checking it.
5. **Refuse what the data can't support.** CSAT, revenue, churn and location get a clear "not available".
6. **Treat customer text as untrusted data.** Someone *will* type "IGNORE ALL PREVIOUS INSTRUCTIONS" into a support chat. Mine did, in the test data, on purpose.
7. **Pause for humans before any write.** And make sure approving twice can't create two records.
8. **Fail loudly.** If the model is down, show an error. Never quietly switch to a weaker method.
9. **Report quality per language.** One overall score hides the languages where you're weakest.
10. **Respect the free tier.** Caps, caching and no automatic retries. Everything in this article cost about 50 free requests.
11. **Audit yourself, with evidence.** Read the code, query the data directly, run the real thing. My worst bug was invisible on the dashboard.
12. **Test with the real provider's behaviour.** Scripted test models are polite; real streams and small models are not.

---

## 🧠 Quick quiz (answers below, no peeking!)

1. Why can't you just use the first 5,000 rows of the dataset?
2. Why did `119237` become `119237.0`?
3. What happens to a Gemini label that has no supporting quote?
4. How many free Gemini requests did the 300-conversation labelling cost?
5. What does Flo say when you ask for the CSAT score?
6. Why did 100 embeddings in one request break the free tier?
7. Why are system labels hidden on the Human review page?
8. Why did a wrong token count break human approval?

<details>
<summary>Answers</summary>

1. Replies are scattered across the file, so you'd split conversations and lose their parent messages.
2. pandas turns a numeric column with blank cells into floats.
3. It becomes "unknown", and the downgrade is recorded.
4. 21: 20 batches of 15, plus one retry.
5. "Not available from this data", with no invented number.
6. On the free tier, every text in a batch counts as one request, and the limit is 100 per minute.
7. So the reviewer isn't anchored by the AI's answer. Otherwise you'd measure agreement, not accuracy.
8. Gemini repeats running totals on every chunk; adding them up pushed normal runs over the 24,000-token safety budget, which is checked right before the approval step.

</details>

*(Medium doesn't support collapsible answers, so on Medium the answers simply appear here.)*

---

## 📋 What's honestly not done yet

I promised myself this project would never overclaim, so:

Done since the first version:

- ✅ **Flo's live chat on the real data with Gemini** (Challenge 14), now checked in five live runs, every number matching an independent SQL recount.
- ✅ **Semantic search** with Gemini embeddings (Challenge 15), now measured (Challenge 21).
- ✅ **Agent sign-offs like "~ Jess"** are redacted (Challenge 13).
- ✅ **Token accounting** is accurate, and action proposals reach the approval pause on Gemini (Challenges 18–20).
- ✅ **101 automated tests**, run by CI on every pull request.

Still open:
- ⏳ **Gemini labels for all 3,000.** 440 so far (I'd misreported this as 154 earlier; the audit caught that too). 2,560 to go, about 171 free requests.
- ⏳ **Semantic search on all 3,000.** The 300-conversation sample is embedded; 5,641 customer messages to go.
- ⏳ **Accuracy numbers** need about 100 human reviews. The metrics are built; the reviews are my homework.
- **LangSmith tracing** needs a LangSmith key. The setup guide is in the repo.
- **Most public threads have no visible outcome.** That's the data, not a bug, and the app explains why.

---

## 🙌 Try it, break it, tell me

Everything is open source:

**👉 [github.com/florina787/Data-sets — `convolens/`](https://github.com/florina787/Data-sets/tree/master/convolens)**

Clone it, run it, ask Flo something tricky, and please tell me where it breaks. And if you've ever had an AI tool confidently hand you a made-up number in front of your boss… I see you. This one's for us. 💙

*— Florina*

---

*Data: "Customer Support on Twitter" by Thought Vector on Kaggle (CC BY-NC-SA 4.0). The dataset is not included in the repository. Customer handles and names in screenshots are redacted.*

**Tags:** `Artificial Intelligence` · `LLM` · `Customer Experience` · `LangGraph` · `Data Science`
