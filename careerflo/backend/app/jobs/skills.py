"""Deterministic skill taxonomy used for extraction from resumes and job descriptions."""
from __future__ import annotations

import re

# canonical name -> (category, aliases)
TAXONOMY: dict[str, tuple[str, tuple[str, ...]]] = {
    "Python": ("language", ("python", "python3")),
    "Java": ("language", ("java",)),
    "JavaScript": ("language", ("javascript", "js", "node.js", "nodejs")),
    "TypeScript": ("language", ("typescript",)),
    "Go": ("language", ("golang", "go lang")),
    "Rust": ("language", ("rust",)),
    "C++": ("language", ("c++", "cpp")),
    "C#": ("language", ("c#", ".net", "dotnet")),
    "Scala": ("language", ("scala",)),
    "SQL": ("data", ("sql", "t-sql", "pl/sql")),
    "R": ("language", ("r programming", "rstudio")),
    "Machine Learning": ("ml", ("machine learning", "ml models", "ml engineering")),
    "Deep Learning": ("ml", ("deep learning", "neural networks", "neural network")),
    "PyTorch": ("ml", ("pytorch", "torch")),
    "TensorFlow": ("ml", ("tensorflow", "keras")),
    "scikit-learn": ("ml", ("scikit-learn", "sklearn")),
    "NLP": ("ml", ("nlp", "natural language processing")),
    "Computer Vision": ("ml", ("computer vision", "opencv")),
    "Generative AI": ("genai", ("generative ai", "genai", "gen ai")),
    "LLMs": ("genai", ("llm", "llms", "large language model", "large language models")),
    "RAG": ("genai", ("rag", "retrieval augmented generation", "retrieval-augmented generation")),
    "LangChain": ("genai", ("langchain",)),
    "LangGraph": ("genai", ("langgraph",)),
    "MCP": ("genai", ("model context protocol", "mcp")),
    "Agentic AI": ("genai", ("agentic", "ai agents", "multi-agent", "autonomous agents")),
    "Prompt Engineering": ("genai", ("prompt engineering",)),
    "Fine-tuning": ("genai", ("fine-tuning", "fine tuning", "lora", "qlora", "peft")),
    "Vector Databases": ("genai", ("vector database", "vector databases", "pinecone", "weaviate", "qdrant", "pgvector", "faiss", "chroma")),
    "Hugging Face": ("genai", ("hugging face", "huggingface", "transformers")),
    "MLOps": ("ops", ("mlops", "mlflow", "kubeflow", "model deployment")),
    "AWS": ("cloud", ("aws", "amazon web services", "sagemaker", "lambda", "ec2", "s3")),
    "Azure": ("cloud", ("azure",)),
    "GCP": ("cloud", ("gcp", "google cloud", "vertex ai", "bigquery")),
    "Docker": ("ops", ("docker", "containers", "containerization")),
    "Kubernetes": ("ops", ("kubernetes", "k8s", "eks", "aks", "gke")),
    "Terraform": ("ops", ("terraform", "infrastructure as code", "iac")),
    "CI/CD": ("ops", ("ci/cd", "continuous integration", "github actions", "jenkins", "gitlab ci")),
    "Linux": ("ops", ("linux", "bash", "shell scripting")),
    "FastAPI": ("backend", ("fastapi",)),
    "Django": ("backend", ("django",)),
    "Flask": ("backend", ("flask",)),
    "REST APIs": ("backend", ("rest", "restful", "rest api", "rest apis")),
    "GraphQL": ("backend", ("graphql",)),
    "Microservices": ("backend", ("microservices", "microservice")),
    "React": ("frontend", ("react", "react.js", "reactjs")),
    "PostgreSQL": ("data", ("postgresql", "postgres")),
    "MongoDB": ("data", ("mongodb",)),
    "Redis": ("data", ("redis",)),
    "Kafka": ("data", ("kafka",)),
    "Spark": ("data", ("spark", "pyspark", "databricks")),
    "Airflow": ("data", ("airflow",)),
    "Data Engineering": ("data", ("data engineering", "etl", "data pipelines", "data pipeline")),
    "Statistics": ("data", ("statistics", "statistical", "a/b testing")),
    "System Design": ("eng", ("system design", "distributed systems", "scalability")),
    "Security": ("eng", ("security", "owasp", "iam")),
    "AI Governance": ("eng", ("ai governance", "responsible ai", "model risk", "ai ethics")),
    "Leadership": ("soft", ("leadership", "led a team", "mentoring", "mentored", "people management")),
    "Communication": ("soft", ("communication", "stakeholder management", "stakeholders")),
    "Agile": ("soft", ("agile", "scrum", "kanban")),
    "Customer-facing": ("soft", ("customer-facing", "client-facing", "forward deployed", "solutions engineering")),
}

_PATTERNS: list[tuple[str, re.Pattern[str]]] = []
for canon, (_cat, aliases) in TAXONOMY.items():
    for alias in aliases:
        esc = re.escape(alias)
        _PATTERNS.append((canon, re.compile(rf"(?<![\w+#/.]){esc}(?![\w+#])", re.IGNORECASE)))


def extract_skills(text: str) -> list[str]:
    text = text or ""
    found: list[str] = []
    for canon, pat in _PATTERNS:
        if canon not in found and pat.search(text):
            found.append(canon)
    # "Go" and "R" are too ambiguous as bare words; require a strong alias (handled by TAXONOMY).
    return found


def category(skill: str) -> str:
    return TAXONOMY.get(skill, ("other", ()))[0]


def split_required_preferred(description: str) -> tuple[list[str], list[str]]:
    """Split description into required vs preferred skills using section cues."""
    text = description or ""
    lower = text.lower()
    pref_idx = -1
    for cue in ("nice to have", "preferred", "bonus", "plus:", "good to have", "would be a plus"):
        i = lower.find(cue)
        if i >= 0 and (pref_idx < 0 or i < pref_idx):
            pref_idx = i
    if pref_idx < 0:
        return extract_skills(text), []
    required = extract_skills(text[:pref_idx])
    preferred = [s for s in extract_skills(text[pref_idx:]) if s not in required]
    return required, preferred
