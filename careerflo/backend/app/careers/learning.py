"""Learning catalogue: books, certifications and proof-projects per skill, arranged on four progression
paths — Ladder (deepen the core), Lattice (broaden sideways), Wave (ride emerging tech), Portfolio (prove it).
Titles are real public books/certifications; Career_flo has no affiliation with their publishers or issuers."""
from __future__ import annotations

from typing import Any

PATHS = {
    "ladder": "Climb: deepen the core skills your target roles require.",
    "lattice": "Move sideways: add adjacent skills that open new role families.",
    "wave": "Ride the wave: emerging tools that postings are starting to ask for.",
    "portfolio": "Prove it: ship something public that evidences the skill.",
}

CATALOG: dict[str, dict[str, list[dict[str, str]]]] = {
    "Python": {"books": [{"title": "Fluent Python (2nd ed.)", "author": "Luciano Ramalho"}],
               "certifications": [{"name": "PCAP – Certified Associate Python Programmer", "issuer": "Python Institute"}]},
    "Machine Learning": {"books": [{"title": "Hands-On Machine Learning with Scikit-Learn, Keras & TensorFlow", "author": "Aurélien Géron"}],
                         "certifications": [{"name": "Machine Learning Specialization", "issuer": "DeepLearning.AI / Stanford (Coursera)"}]},
    "Deep Learning": {"books": [{"title": "Deep Learning", "author": "Goodfellow, Bengio & Courville"}],
                      "certifications": [{"name": "Deep Learning Specialization", "issuer": "DeepLearning.AI (Coursera)"}]},
    "LLMs": {"books": [{"title": "AI Engineering", "author": "Chip Huyen"}],
             "certifications": [{"name": "Generative AI with Large Language Models", "issuer": "DeepLearning.AI & AWS (Coursera)"}]},
    "Generative AI": {"books": [{"title": "Generative Deep Learning (2nd ed.)", "author": "David Foster"}],
                      "certifications": [{"name": "AWS Certified AI Practitioner", "issuer": "Amazon Web Services"}]},
    "RAG": {"books": [{"title": "AI Engineering", "author": "Chip Huyen"}], "certifications": []},
    "MLOps": {"books": [{"title": "Designing Machine Learning Systems", "author": "Chip Huyen"}],
              "certifications": [{"name": "Professional Machine Learning Engineer", "issuer": "Google Cloud"}]},
    "AWS": {"books": [], "certifications": [{"name": "AWS Certified Machine Learning Engineer – Associate", "issuer": "Amazon Web Services"},
                                             {"name": "AWS Certified Solutions Architect – Associate", "issuer": "Amazon Web Services"}]},
    "Azure": {"books": [], "certifications": [{"name": "Azure AI Engineer Associate (AI-102)", "issuer": "Microsoft"}]},
    "GCP": {"books": [], "certifications": [{"name": "Professional Cloud Architect", "issuer": "Google Cloud"}]},
    "Kubernetes": {"books": [{"title": "Kubernetes Up & Running (3rd ed.)", "author": "Burns, Beda, Hightower & Evenson"}],
                   "certifications": [{"name": "Certified Kubernetes Administrator (CKA)", "issuer": "The Linux Foundation / CNCF"}]},
    "Docker": {"books": [{"title": "Docker Deep Dive", "author": "Nigel Poulton"}], "certifications": []},
    "Terraform": {"books": [{"title": "Terraform: Up & Running (3rd ed.)", "author": "Yevgeniy Brikman"}],
                  "certifications": [{"name": "HashiCorp Certified: Terraform Associate", "issuer": "HashiCorp"}]},
    "System Design": {"books": [{"title": "Designing Data-Intensive Applications", "author": "Martin Kleppmann"}], "certifications": []},
    "SQL": {"books": [{"title": "Learning SQL (3rd ed.)", "author": "Alan Beaulieu"}], "certifications": []},
    "Data Engineering": {"books": [{"title": "Fundamentals of Data Engineering", "author": "Joe Reis & Matt Housley"}],
                         "certifications": [{"name": "Databricks Certified Data Engineer Associate", "issuer": "Databricks"}]},
    "Statistics": {"books": [{"title": "Practical Statistics for Data Scientists (2nd ed.)", "author": "Bruce, Bruce & Gedeck"}], "certifications": []},
    "Security": {"books": [], "certifications": [{"name": "CompTIA Security+", "issuer": "CompTIA"}]},
    "AI Governance": {"books": [], "certifications": [{"name": "Artificial Intelligence Governance Professional (AIGP)", "issuer": "IAPP"}]},
    "Leadership": {"books": [{"title": "The Manager's Path", "author": "Camille Fournier"}], "certifications": []},
    "Agile": {"books": [], "certifications": [{"name": "Professional Scrum Master I (PSM I)", "issuer": "Scrum.org"}]},
}
WAVE = {"Agentic AI", "MCP", "LangGraph", "RAG", "LLMs", "Generative AI", "Vector Databases", "Fine-tuning"}
CORE = {"Python", "SQL", "Machine Learning", "System Design", "Data Engineering", "Statistics"}


def path_for(skill: str, demand_rank: int) -> str:
    if skill in WAVE:
        return "wave"
    if skill in CORE or demand_rank < 3:
        return "ladder"
    return "lattice"


def learning_plan(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan = []
    for i, g in enumerate(gaps[:8]):
        s = g["skill"]
        entry = CATALOG.get(s, {"books": [], "certifications": []})
        plan.append({"skill": s, "demand": g.get("demand"), "path": path_for(s, i), "books": entry["books"],
                     "certifications": entry["certifications"],
                     "portfolio_project": f"Ship a small public project that uses {s} and write up what you measured."})
    return plan


def catalog() -> dict[str, Any]:
    return {"paths": PATHS, "skills": [{"skill": k, "path": path_for(k, 99), **v} for k, v in CATALOG.items()]}
