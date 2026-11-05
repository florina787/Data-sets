"""Synthetic demonstration data. Every record is flagged ``is_synthetic`` and labelled in the UI.
Companies are fictional; apply links point at the reserved example.com domain."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from .normalize import NormalizedJob, enrich

COMPANIES = ["Northwind Analytics", "Maple Circuit Labs", "Aurora Fintech", "Lakeshore Health AI", "Borealis Robotics",
             "Cobalt Cloud Systems", "Harbourline Logistics", "Quill & Ledger", "Tundra Data Co", "Prairie Mobility",
             "Summit Retail Tech", "Granite Security", "Cedar Learning", "Halcyon Insurance Tech", "Fjord Energy AI",
             "Lumen Media Labs", "Orchard Commerce", "Pinecrest Biotech", "Riverstone Payments", "Skyline Gaming"]
CITIES = [("Toronto", "CA", "CAD"), ("Vancouver", "CA", "CAD"), ("Montreal", "CA", "CAD"), ("Ottawa", "CA", "CAD"),
          ("Calgary", "CA", "CAD"), ("Waterloo", "CA", "CAD"), ("New York", "US", "USD"), ("Seattle", "US", "USD"),
          ("Austin", "US", "USD"), ("London", "GB", "GBP")]
TITLES = [("AI Engineer", ["Python", "LLMs", "RAG", "LangGraph", "Docker"], ["MCP", "Kubernetes"]),
          ("Machine Learning Engineer", ["Python", "PyTorch", "Machine Learning", "MLOps"], ["AWS", "Spark"]),
          ("Forward Deployed AI Engineer", ["Python", "LLMs", "Customer-facing", "REST APIs"], ["Agentic AI", "MCP"]),
          ("Data Scientist", ["Python", "SQL", "Statistics", "scikit-learn"], ["Spark", "Airflow"]),
          ("Backend Engineer", ["Python", "FastAPI", "PostgreSQL", "Docker"], ["Kubernetes", "Kafka"]),
          ("Full-Stack Engineer", ["TypeScript", "React", "Python", "REST APIs"], ["GraphQL", "AWS"]),
          ("MLOps Engineer", ["Kubernetes", "Docker", "CI/CD", "MLOps"], ["Terraform", "GCP"]),
          ("Generative AI Engineer", ["Python", "Generative AI", "LLMs", "Vector Databases"], ["Fine-tuning", "LangChain"]),
          ("Data Engineer", ["Python", "SQL", "Spark", "Airflow", "Data Engineering"], ["Kafka", "AWS"]),
          ("AI Governance Lead", ["AI Governance", "Communication", "Leadership"], ["Security", "Machine Learning"])]
LEVELS = [("Junior", 0.62), ("", 0.85), ("Senior", 1.0), ("Staff", 1.22), ("Principal", 1.38)]
INDUSTRIES = ["Fintech", "Healthcare", "Retail", "Logistics", "Energy", "Media", "Insurance", "Education", "Security"]


def synthetic_jobs(n: int = 100, seed: int = 42) -> list[NormalizedJob]:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    jobs: list[NormalizedJob] = []
    for i in range(n):
        company = COMPANIES[i % len(COMPANIES)]
        city, country, cur = rng.choice(CITIES)
        base_title, req, pref = TITLES[rng.randrange(len(TITLES))]
        level, mult = rng.choice(LEVELS)
        title = f"{level} {base_title}".strip()
        arrangement = rng.choice(["remote", "hybrid", "onsite", "hybrid"])
        base = {"CAD": 125000, "USD": 140000, "GBP": 80000}[cur] * mult
        has_salary = rng.random() < 0.8
        smin = round(base * rng.uniform(0.9, 1.05), -3) if has_salary else None
        smax = round(smin * rng.uniform(1.15, 1.35), -3) if smin else None
        industry = rng.choice(INDUSTRIES)
        desc = (f"[SYNTHETIC DEMO POSTING] {company} ({industry}) is hiring a {title} in {city} ({arrangement}).\n\n"
                f"What you'll do:\n- Build and ship production systems with {', '.join(req[:3])}.\n"
                f"- Partner with product and customers to deliver measurable outcomes.\n\n"
                f"Requirements: {', '.join(req)}.\n\nNice to have: {', '.join(pref)}.")
        jobs.append(enrich(NormalizedJob(
            source="synthetic", source_job_id=f"demo-{i + 1:03d}", origin_publisher="Synthetic demo data",
            company=f"{company} (Demo)", title=title, location=f"{city}, {country}", city=city, country=country,
            work_arrangement=arrangement, employment_type="Full-time", seniority=None, industry=industry,
            salary_min=smin, salary_max=smax, salary_currency=cur if smin else None, salary_period="year" if smin else None,
            salary_verified=bool(smin), description=desc, required_skills=req, preferred_skills=pref,
            posted_at=now - timedelta(days=rng.randint(0, 40), hours=rng.randint(0, 23)),
            apply_url=f"https://example.com/demo/jobs/{i + 1:03d}", verification_status="synthetic", is_synthetic=True)))
    # Fixed showcase postings for the flagship demo request ("Senior AI Engineer jobs in Toronto over CAD 150,000"):
    # some above the bar, some below, one without a published salary — so filtering is visible.
    showcase = [
        ("Senior AI Engineer", "hybrid", 155000, 185000), ("Senior AI Engineer", "onsite", 162000, 195000),
        ("Senior Forward Deployed AI Engineer", "hybrid", 150000, 178000), ("Senior AI Engineer", "remote", 135000, 148000),
        ("Senior Generative AI Engineer", "hybrid", None, None), ("Staff AI Engineer", "onsite", 180000, 220000),
    ]
    req = ["Python", "LLMs", "RAG", "LangGraph", "Docker"]
    for k, (title, arr, lo, hi) in enumerate(showcase):
        i = n - len(showcase) + k
        company = COMPANIES[(k * 3 + 1) % len(COMPANIES)]
        desc = (f"[SYNTHETIC DEMO POSTING] {company} is hiring a {title} in Toronto ({arr}).\n\n"
                f"Requirements: {', '.join(req)}.\n\nNice to have: MCP, Kubernetes.")
        jobs[i] = enrich(NormalizedJob(
            source="synthetic", source_job_id=f"demo-{i + 1:03d}", origin_publisher="Synthetic demo data",
            company=f"{company} (Demo)", title=title, location="Toronto, CA", city="Toronto", country="CA", work_arrangement=arr,
            employment_type="Full-time", industry="Technology", salary_min=lo, salary_max=hi, salary_currency="CAD" if lo else None,
            salary_period="year" if lo else None, salary_verified=bool(lo), description=desc, required_skills=req,
            preferred_skills=["MCP", "Kubernetes"], posted_at=now - timedelta(days=k + 1),
            apply_url=f"https://example.com/demo/jobs/{i + 1:03d}", verification_status="synthetic", is_synthetic=True))
    return jobs
