# Turning on LangSmith tracing

Tracing is off by default and nothing else depends on it. When it is on, every Flo run (graph nodes, tool calls,
model calls) appears in LangSmith **after a second redaction pass** (`hide_inputs` / `hide_outputs` in
`app/observability/`), so handles, emails, phone numbers, card numbers and agent sign-offs never leave the machine.

## 1. Get a key

1. Sign in at <https://smith.langchain.com> (the free Developer plan is enough).
2. **Settings → API keys → Create API key.** A *personal access token* is fine for one person; use a *service key*
   for a shared deployment.
3. Note your region: EU accounts use `https://eu.api.smith.langchain.com`.

Never paste the key into a chat, an issue, a commit or a screenshot.

## 2a. Local machine

Add to `convolens/.env` (git-ignored):

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...           # your key
LANGSMITH_PROJECT=convolens
# LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com   # EU accounts only
```

Restart the backend. The status strip shows **LangSmith: on**, and the Observability page links each run to its trace.

## 2b. Claude Code cloud environment (the way the Gemini key was added)

1. Open the cloud environment menu in the session title bar → **Edit**.
2. Under **Network secrets**, add a secret for host `api.smith.langchain.com` (or `eu.api.smith.langchain.com`),
   header `x-api-key`, value = your key.
3. Add the environment variables `LANGSMITH_TRACING=true`, `LANGSMITH_PROJECT=convolens`, and
   `LANGSMITH_API_KEY=injected-by-egress-proxy` (a placeholder: the real key is added to the request by the proxy and
   never enters the process).
4. Start a new session; it picks up the change.

## 3. Check it works

```bash
cd backend
uv run python -c "from app.observability.tracing import status; print(status())"
```

Then ask Flo one question and open **Observability and evaluation**: the run row gets a *View trace* link.

## 4. Experiments (optional)

```bash
uv run python -m app.evaluation.run --system llm --dataset <id> --langsmith
```

This uploads the labelled evaluation set and runs it as a LangSmith experiment, so prompt or model changes can be
compared side by side. With the Gemini free tier, an LLM evaluation run spends requests: check the case count first.
