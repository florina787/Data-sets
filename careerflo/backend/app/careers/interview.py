"""Interview question bank and rubric-based answer evaluation.

Questions are general practice questions written for this product; we never claim to know any
employer's confidential interview questions.
"""
from __future__ import annotations

import re
from typing import Any

Q = dict[str, Any]


def q(text: str, concepts: list[str], followup: str, kind: str = "technical") -> Q:
    return {"question": text, "concepts": concepts, "followup": followup, "kind": kind}


BANK: dict[str, list[Q]] = {
    "python": [
        q("Explain the difference between a list and a tuple in Python and when you would use each.", ["mutable", "immutable", "hashable", "performance"], "How does immutability affect using them as dict keys?"),
        q("What is the GIL and how does it affect concurrency in Python?", ["global interpreter lock", "threads", "multiprocessing", "asyncio", "i/o-bound", "cpu-bound"], "When would you choose asyncio over threads?"),
        q("How do generators work and why are they memory efficient?", ["yield", "lazy", "iterator", "memory"], "How would you build a streaming pipeline with generators?"),
    ],
    "data_structures": [
        q("Compare a hash map and a balanced binary search tree.", ["o(1)", "o(log n)", "ordered", "collision", "hash"], "When would ordering requirements push you to a tree?"),
        q("How would you detect a cycle in a linked list?", ["two pointers", "fast", "slow", "floyd", "o(1) space"], "How do you find the start of the cycle?"),
    ],
    "algorithms": [
        q("Explain dynamic programming and give an example problem.", ["overlapping subproblems", "optimal substructure", "memoization", "tabulation"], "How do you reduce the space complexity of your example?"),
        q("How does binary search work and what are its preconditions?", ["sorted", "o(log n)", "midpoint", "invariant"], "How do you avoid off-by-one errors?"),
    ],
    "machine_learning": [
        q("Explain the bias-variance trade-off.", ["bias", "variance", "underfitting", "overfitting", "regularization"], "How would you diagnose which one you have?"),
        q("How do you handle class imbalance?", ["resampling", "class weights", "precision", "recall", "f1", "auc"], "Which metric would you report to stakeholders and why?"),
    ],
    "deep_learning": [
        q("What problem do residual connections solve?", ["vanishing gradient", "skip connection", "depth", "identity"], "Where do you see them in transformers?"),
        q("Explain the attention mechanism.", ["query", "key", "value", "softmax", "scaled"], "Why is attention quadratic in sequence length?"),
    ],
    "generative_ai": [
        q("How would you evaluate an LLM-powered feature before launch?", ["golden set", "human review", "llm-as-judge", "regression", "metrics", "hallucination"], "How do you keep evaluations current after launch?"),
        q("How do you reduce hallucinations in a production LLM system?", ["grounding", "retrieval", "citations", "validation", "temperature", "refuse"], "How do you detect a hallucination automatically?"),
    ],
    "agentic_ai": [
        q("How would you prevent an AI agent from taking unsafe actions?", ["allowlist", "human approval", "least privilege", "audit", "sandbox", "timeout"], "Where should these controls live: in the prompt or in code?"),
        q("How do you bound an agent loop?", ["max steps", "budget", "timeout", "termination", "state"], "What do you return to the user when the bound is hit?"),
    ],
    "langgraph": [
        q("What is a LangGraph StateGraph and how do conditional edges work?", ["state", "nodes", "edges", "conditional", "reducer"], "How would you persist state across requests?"),
        q("How would you add a human-in-the-loop step in LangGraph?", ["interrupt", "checkpointer", "resume", "approval"], "What state must be persisted for resume to work?"),
    ],
    "mcp": [
        q("What is the Model Context Protocol and what problem does it solve?", ["tools", "resources", "prompts", "client", "server", "standard"], "How do MCP transports differ (stdio vs HTTP)?"),
        q("How would you secure an MCP server that accesses user data?", ["authorization", "validation", "allowlist", "rate limit", "audit", "injection"], "How would you version tools safely?"),
    ],
    "rag": [
        q("Walk me through designing a RAG pipeline.", ["chunking", "embeddings", "vector", "retrieval", "rerank", "citations", "evaluation"], "How would you evaluate retrieval quality separately from generation?"),
        q("How do you choose a chunking strategy?", ["chunk size", "overlap", "semantic", "structure", "recall"], "What changes for tables and code?"),
    ],
    "vector_databases": [
        q("How does approximate nearest neighbour search work?", ["hnsw", "ivf", "recall", "latency", "index"], "How do you tune recall vs latency?"),
    ],
    "aws": [q("How would you deploy a model-serving API on AWS?", ["ecs", "eks", "lambda", "sagemaker", "autoscaling", "iam", "vpc"], "How would you control cost?")],
    "azure": [q("How would you deploy an AI service on Azure securely?", ["managed identity", "key vault", "aks", "app service", "private endpoint"], "How do you handle secrets rotation?")],
    "gcp": [q("Describe deploying a containerised API on GCP.", ["cloud run", "gke", "iam", "artifact registry", "autoscaling"], "When would you pick GKE over Cloud Run?")],
    "docker": [q("How do you make a Docker image small and secure?", ["multi-stage", "slim", "non-root", "layer", "cache", "scan"], "How do you keep builds reproducible?")],
    "kubernetes": [q("Explain Deployments, Services and Ingress in Kubernetes.", ["pods", "replicas", "service", "ingress", "load balancing", "rolling update"], "How would you roll back a bad deploy?")],
    "ci_cd": [q("Design a CI/CD pipeline for an ML service.", ["tests", "lint", "build", "staging", "canary", "rollback", "model registry"], "How do you gate deploys on model quality?")],
    "system_design": [
        q("Design a job-alert system that notifies users of new postings.", ["ingestion", "deduplication", "queue", "rate limit", "scheduler", "idempotent", "cache"], "How does it scale to a million users?"),
        q("Design a metered usage system for a SaaS product.", ["atomic", "idempotency", "reservation", "race condition", "ledger", "webhook"], "How do you reconcile with the billing provider?"),
    ],
    "governance": [q("How would you set up AI governance for an enterprise LLM deployment?", ["risk assessment", "policy", "audit", "monitoring", "human oversight", "privacy", "bias"], "Which metrics would you report to a risk committee?")],
    "leadership": [q("Tell me about a time you led a team through ambiguity.", ["situation", "task", "action", "result"], "What would you do differently?", "behavioral")],
    "behavioral": [
        q("Tell me about a time you disagreed with a stakeholder.", ["situation", "task", "action", "result"], "How did the relationship develop afterwards?", "behavioral"),
        q("Describe a project that failed. What did you learn?", ["situation", "task", "action", "result", "learned"], "How did you apply that lesson later?", "behavioral"),
        q("Tell me about a time you delivered under a tight deadline.", ["situation", "task", "action", "result"], "What trade-offs did you make?", "behavioral"),
    ],
}
TOPICS = list(BANK)

ROLE_TOPICS = {
    "forward deployed": ["agentic_ai", "mcp", "rag", "system_design", "behavioral"],
    "ai engineer": ["generative_ai", "agentic_ai", "langgraph", "rag", "system_design"],
    "machine learning": ["machine_learning", "deep_learning", "python", "system_design"],
    "data scientist": ["machine_learning", "python", "algorithms", "behavioral"],
    "backend": ["python", "system_design", "docker", "kubernetes"],
    "mlops": ["ci_cd", "kubernetes", "docker", "aws"],
    "data engineer": ["python", "system_design", "algorithms", "gcp"],
    "governance": ["governance", "agentic_ai", "leadership", "behavioral"],
}


def plan_interview(role: str, topics: list[str] | None = None, n: int = 5) -> list[Q]:
    role_l = (role or "").lower()
    if not topics:
        topics = next((v for k, v in ROLE_TOPICS.items() if k in role_l), ["python", "system_design", "behavioral"])
        if "senior" in role_l or "staff" in role_l or "lead" in role_l:
            topics = topics + ["leadership"]
    picked: list[Q] = []
    i = 0
    while len(picked) < n and i < 20:
        for t in topics:
            bank = BANK.get(t, [])
            if i < len(bank) and len(picked) < n:
                picked.append({**bank[i], "topic": t})
        i += 1
    return picked


STAR = {"situation": ["situation", "context", "when i was", "at my previous", "we had"],
        "task": ["task", "goal", "i needed", "responsible for", "my role"],
        "action": ["i built", "i led", "i decided", "i implemented", "i worked", "action", "so i"],
        "result": ["result", "outcome", "reduced", "increased", "improved", "%", "delivered", "learned"]}


def evaluate_answer(question: Q, answer: str) -> dict[str, Any]:
    a = (answer or "").lower()
    words = len(re.findall(r"\w+", a))
    if question.get("kind") == "behavioral":
        parts = {k: any(c in a for c in cues) for k, cues in STAR.items()}
        coverage = sum(parts.values()) / 4
        covered = [k for k, v in parts.items() if v]
        missed = [k for k, v in parts.items() if not v]
    else:
        concepts = question["concepts"]
        covered = [c for c in concepts if c in a]
        missed = [c for c in concepts if c not in a]
        coverage = len(covered) / len(concepts) if concepts else 0
    depth = min(1.0, words / 150)
    structure = 1.0 if words >= 40 and ("." in a or "\n" in a) else 0.5 if words >= 15 else 0.2
    score = round(10 * (0.6 * coverage + 0.25 * depth + 0.15 * structure), 1)
    tips = []
    if missed:
        tips.append(("Use the STAR structure; missing: " if question.get("kind") == "behavioral" else "Consider covering: ") + ", ".join(missed[:5]))
    if words < 60:
        tips.append("Add a concrete example from your own experience.")
    return {"score": score, "rubric": {"coverage": round(coverage * 10, 1), "depth": round(depth * 10, 1),
                                       "structure": round(structure * 10, 1)},
            "covered": covered, "missed": missed, "suggestions": tips, "followup": question.get("followup")}
