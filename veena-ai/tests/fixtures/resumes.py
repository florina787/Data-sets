"""Synthetic resumes (fictional person) as real PDFs, for retrieval tests."""

import pymupdf

HEADER = ["Jordan Avery", "Senior Machine Learning Engineer", "jordan.avery@example.com | London, UK"]
WITH_YEARS = HEADER + [
    "SUMMARY",
    "Machine learning engineer with 9 years of professional experience building NLP and retrieval systems.",
]
DATES_ONLY = HEADER + ["SUMMARY", "Engineer focused on search, NLP and reliable ML platforms."]
BODY = [
    "EXPERIENCE",
    "Lead ML Engineer, Northwind Analytics - March 2021 to Present",
    "Built a retrieval-augmented generation platform with FAISS and LangChain serving 2M queries a month.",
    "Led a team of five engineers; reduced inference cost by 38% with quantized models.",
    "Machine Learning Engineer, Contoso Health - June 2018 to February 2021",
    "Trained clinical text classifiers in PyTorch; deployed models with Docker and Kubernetes on AWS.",
    "Software Engineer, Fabrikam Ltd - September 2016 to May 2018",
    "Developed REST APIs in Java and Python; maintained PostgreSQL data pipelines.",
    "SKILLS",
    "Programming languages: Python, Java, TypeScript, SQL, Go",
    "AI and ML: LLMs, RAG, embeddings, fine-tuning with LoRA, PyTorch, Hugging Face Transformers, LangGraph",
    "Cloud and tools: AWS, Docker, Kubernetes, Terraform, GitHub Actions",
    "EDUCATION",
    "MSc Computer Science, University of Leeds, 2016",
]


def pdf(lines):
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    for line in lines:
        if y > 780:
            page = doc.new_page()
            y = 60
        page.insert_text((50, y), line, fontsize=10)
        y += 16 if line.isupper() else 14
    data = doc.tobytes()
    doc.close()
    return data


def resume_with_years():
    return pdf(WITH_YEARS + BODY)


def resume_dates_only():
    return pdf(DATES_ONLY + BODY)
