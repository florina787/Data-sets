---
title: Career_flo AI
emoji: 🧭
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: gpl-3.0
short_description: AI career partner — Qwen3 agents, MCP tools, career graph
models:
  - Qwen/Qwen3-1.7B
  - unsloth/Qwen3-1.7B-GGUF
---

# Career_flo AI

Your Intelligent AI Career Partner. FastAPI + LangGraph agents + MCP tools + open-weight **Qwen3** (llama.cpp, CPU) in one container;
accounts and data in **Supabase**; payments through **Stripe** (test mode until approved).

Source, documentation and deployment guide: see the project repository (`careerflo/`).

**Data handling:** no user data is stored in this Space — the container disk is ephemeral and all records live in the
configured Supabase project. Secrets are provided as Space *Secrets* and never committed.
