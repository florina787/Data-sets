import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="careerflo-test-")
os.environ.update({
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db"),
    "ENVIRONMENT": "test", "AUTH_MODE": "local", "LLM_PROVIDER": "scripted", "LLM_MODEL": "qwen3:1.7b",
    "ENABLE_SYNTHETIC_JOBS": "true", "JSEARCH_API_KEY": "", "ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": "",
    "STRIPE_SECRET_KEY": "", "STRIPE_WEBHOOK_SECRET": "whsec_test_secret", "STRIPE_PRICE_PRO": "price_pro_test",
    "STRIPE_PRICE_PREMIUM": "price_premium_test", "ADMIN_EMAILS": "admin@example.com", "RATE_LIMIT_PER_MINUTE": "100000",
})

import itertools  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.security.ratelimit import limiter  # noqa: E402

_counter = itertools.count()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_limits():
    limiter.reset()
    yield


def register(client, email=None, password="CorrectHorse42"):
    email = email or f"user{next(_counter)}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    data = r.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


@pytest.fixture
def user(client):
    return register(client)


RESUME = b"""Alex Morgan
alex.morgan@example.com | +1 416 555 0199

SUMMARY
Backend and AI engineer focused on Python services and LLM applications.

EXPERIENCE
Senior AI Engineer, Example Robotics - Mar 2020 - Present
- Built a RAG service with LangGraph and FastAPI used by 5,000 people
- Cut cloud costs by 20% using Docker and Kubernetes autoscaling
- Mentored 3 engineers and led code reviews

Software Engineer, Sample Bank - Jan 2016 - Feb 2020
- Wrote Python and SQL data pipelines on AWS
- Built REST APIs and CI/CD with GitHub Actions

EDUCATION
BSc Computer Science, University of Waterloo, 2015

SKILLS
Python, SQL, LLMs, RAG, LangGraph, FastAPI, Docker, Kubernetes, AWS, CI/CD, Leadership
"""


def upload_resume(client, headers, content=RESUME, name="resume.txt"):
    r = client.post("/api/resumes", headers=headers, files={"file": (name, content, "text/plain")})
    assert r.status_code == 201, r.text
    return r.json()


def search_jobs(client, headers, **filters):
    body = {"query": "AI Engineer", "limit": 20} | filters
    r = client.post("/api/jobs/search", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def admin_headers(client):
    """Register the admin once per session; later calls log in."""
    creds = {"email": "admin@example.com", "password": "CorrectHorse42"}
    r = client.post("/api/auth/login", json=creds)
    if r.status_code != 200:
        r = client.post("/api/auth/register", json=creds)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
