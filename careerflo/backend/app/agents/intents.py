"""Deterministic intent classification and parameter extraction (no LLM needed for routing)."""
from __future__ import annotations

import re
from typing import Any

AGENT_ORDER = ["job_discovery", "job_matching", "resume_intelligence", "ats_intelligence", "cover_letter", "interview",
               "coding_coach", "company_research", "recruiter_crm", "application_tracker", "portfolio", "salary",
               "career_analytics"]

AGENT_LABELS = {
    "supervisor": "Supervisor", "job_discovery": "Job Discovery Agent", "job_matching": "Job Matching Agent",
    "resume_intelligence": "Resume Intelligence Agent", "ats_intelligence": "ATS Intelligence Agent",
    "cover_letter": "Cover Letter Agent", "interview": "Interview Intelligence Agent", "coding_coach": "Live Coding Coach",
    "company_research": "Company Research Agent", "recruiter_crm": "Recruiter CRM Agent",
    "application_tracker": "Application Tracker Agent", "portfolio": "GitHub Portfolio Agent", "salary": "Salary Intelligence Agent",
    "career_analytics": "Career Analytics Agent", "autonomous_workflow": "Autonomous Career Workflow Agent",
    "governance": "Governance & Quality Agent",
}

RULES: list[tuple[str, str]] = [
    ("job_discovery", r"\b(find|search|discover|look(ing)? for|show me|list)\b.{0,60}\b(jobs?|roles?|positions?|openings?|postings?)\b|\bhidden job\b|\bjob radar\b|\b(indeed|linkedin)\b"),
    ("job_matching", r"\b(rank|match(ing)?|best (fit|opportunit)|score|compatib|fit for me)\b"),
    ("resume_intelligence", r"\b(resume|cv)\b.{0,40}\b(optimi[sz]e|tailor|improve|analy[sz]e|review|rewrite|update)\b|\b(optimi[sz]e|tailor|analy[sz]e|review|improve)\b.{0,30}\b(my )?(resume|cv)\b"),
    ("ats_intelligence", r"\bats\b|applicant tracking"),
    ("cover_letter", r"\bcover letter\b|\brecruiter (message|note|email)\b|\boutreach\b"),
    ("interview", r"\binterview|mock\b|\bprepare me\b|\binterview questions\b"),
    ("coding_coach", r"\b(coding|leetcode|algorithm) (exercise|practice|challenge|coach)|\blive coding\b|\bpractice coding\b"),
    ("company_research", r"\b(research|tell me about|compare) (the )?(compan(y|ies)|employer)|\bcompany (research|culture)\b|\bculture at\b"),
    ("recruiter_crm", r"\brecruiters?\b|\bfollow[- ]?ups?\b|\breferrals?\b"),
    ("application_tracker", r"\b(my )?applications?\b(?! automation)|\btrack(er)?\b|\bapplied\b"),
    ("portfolio", r"\bgithub\b|\bportfolio\b|\brepositor(y|ies)\b"),
    ("salary", r"\bsalar(y|ies)\b(?!.{0,3}(over|above))|\bcompensation\b|\bnegotiat|\boffer\b.{0,20}\b(counter|negotiat)"),
    ("career_analytics", r"\banalytics\b|\bdashboard\b|\bmetrics\b|\bconversion\b|\bskill gaps?\b|\bmy progress\b"),
]
AUTONOMOUS = r"\b(apply (to|for) (them|it|these|the best)|end[- ]to[- ]end|autonomous|do (everything|it all)|prepare (an )?application|application package)\b"

CITIES = ["Toronto", "Vancouver", "Montreal", "Ottawa", "Calgary", "Edmonton", "Waterloo", "Kitchener", "Winnipeg", "Halifax",
          "Quebec City", "Victoria", "Mississauga", "New York", "San Francisco", "Seattle", "Austin", "Boston", "Chicago",
          "Los Angeles", "London", "Berlin", "Dublin", "Remote"]
CURRENCIES = {"cad": "CAD", "c$": "CAD", "usd": "USD", "us$": "USD", "gbp": "GBP", "£": "GBP", "eur": "EUR", "€": "EUR"}
TOPIC_WORDS = {"python": "python", "data structure": "data_structures", "algorithm": "algorithms", "machine learning": "machine_learning",
               "deep learning": "deep_learning", "generative": "generative_ai", "agentic": "agentic_ai", "langgraph": "langgraph",
               "mcp": "mcp", "rag": "rag", "vector": "vector_databases", "aws": "aws", "azure": "azure", "gcp": "gcp",
               "docker": "docker", "kubernetes": "kubernetes", "ci/cd": "ci_cd", "system design": "system_design",
               "governance": "governance", "leadership": "leadership", "behavioral": "behavioral", "behavioural": "behavioral"}


def classify(message: str) -> list[str]:
    m = message.lower()
    agents = [name for name, pat in RULES if re.search(pat, m)]
    if re.search(AUTONOMOUS, m):
        return ["autonomous_workflow"]
    # "analyze my resume" + "rank" + jobs in one request -> discovery, matching, resume analysis.
    return [a for a in AGENT_ORDER if a in agents]


def extract_params(message: str) -> dict[str, Any]:
    p: dict[str, Any] = {}
    m = message
    low = m.lower()
    for c in CITIES:
        if re.search(rf"\b{re.escape(c.lower())}\b", low):
            if c == "Remote":
                p["work_arrangement"] = "remote"
            else:
                p.setdefault("city", c)
    if "hybrid" in low:
        p["work_arrangement"] = "hybrid"
    elif re.search(r"\bon-?site\b|\bin[- ]office\b", low):
        p["work_arrangement"] = "onsite"
    for k, v in CURRENCIES.items():
        if k in low:
            p["currency"] = v
            break
    sal = re.search(r"(?:over|above|paying|at least|more than|minimum|min|>)\s*(?:of\s*)?(?:cad|usd|gbp|eur|c\$|us\$|\$|£|€)?\s*"
                    r"(\d{2,3}(?:,\d{3})+|\d{2,3}\s?[kK]|\d{5,7})", low)
    if sal:
        raw = sal.group(1).replace(",", "").replace(" ", "")
        p["salary_min"] = float(raw[:-1]) * 1000 if raw.lower().endswith("k") else float(raw)
        if p.get("city") in ("Toronto", "Vancouver", "Montreal", "Ottawa", "Calgary", "Edmonton", "Waterloo") and "currency" not in p:
            p["currency"] = "CAD"
    t = re.search(r"(?:find|search(?: for)?|discover|show me|look(?:ing)? for|list)\s+(?:me\s+)?(?:some\s+|all\s+|the\s+)?(.+?)\s+(?:jobs?|roles?|positions?|openings?)\b", m, re.I)
    if t:
        title = re.sub(r"\b(remote|hybrid|onsite|new|open|latest|top|best)\b", "", t.group(1), flags=re.I).strip(" ,")
        if title:
            p["query"] = title
            lvl = re.search(r"\b(junior|senior|staff|principal|lead)\b", title, re.I)
            if lvl:
                p["seniority"] = lvl.group(1).lower()
    role = re.search(r"\bfor (?:a |an |the )?((?:senior |junior |staff |principal |lead )?[A-Z][\w\- ]{2,60}?)(?: role| position| job|$|[.,])", m)
    if role:
        p["role"] = role.group(1).strip()
    elif p.get("query"):
        p["role"] = p["query"]
    comp = re.search(r"\b(?:at|about|research|compare)\s+([A-Z][\w&.\-]+(?:\s+[A-Z][\w&.\-]+){0,3})", m)
    if comp and comp.group(1) not in CITIES:
        p["company"] = comp.group(1)
    gh = re.search(r"github\.com/([A-Za-z0-9-]{1,39})|github (?:user(?:name)?|account|profile)\s+@?([A-Za-z0-9-]{1,39})", m, re.I)
    if gh:
        p["github_username"] = gh.group(1) or gh.group(2)
    topics = [v for k, v in TOPIC_WORDS.items() if k in low]
    if topics:
        p["topics"] = list(dict.fromkeys(topics))
    if re.search(r"\bindeed\b", low):
        p["origin"] = "indeed"
    elif re.search(r"\blinkedin\b", low):
        p["origin"] = "linkedin"
    off = re.search(r"offer (?:of|is|for)\s*(?:cad|usd|\$)?\s*(\d{2,3}(?:,\d{3})+|\d{2,3}\s?[kK])", low)
    if off:
        raw = off.group(1).replace(",", "").replace(" ", "")
        p["offer"] = float(raw[:-1]) * 1000 if raw.lower().endswith("k") else float(raw)
    return p
