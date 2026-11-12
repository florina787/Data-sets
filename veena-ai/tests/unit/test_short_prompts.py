"""Short prompts: a bare technical term is answered, not met with a request for clarification."""

import pytest

from backend.agents import terms

# 55 common technical terms/questions a user might type on their own -> expected canonical term.
EXPECTED = {
    "langchain": "LangChain",
    "LangChain": "LangChain",
    "langgraph": "LangGraph",
    "llamaindex": "LlamaIndex",
    "MCP": "Model Context Protocol (MCP)",
    "model context protocol": "Model Context Protocol (MCP)",
    "RAG": "Retrieval-Augmented Generation (RAG)",
    "LLM": "Large Language Model (LLM)",
    "transformer": "Transformer",
    "self-attention": "Attention mechanism",
    "embeddings": "Embeddings",
    "vector database": "Vector database",
    "faiss": "FAISS",
    "fine-tuning": "Fine-tuning",
    "LoRA": "LoRA",
    "quantization": "Quantization",
    "prompt engineering": "Prompt engineering",
    "hallucination": "Hallucination (AI)",
    "ai agents": "AI agent",
    "function calling": "Function calling / tool use",
    "ollama": "Ollama",
    "hugging face": "Hugging Face",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "docker": "Docker",
    "terraform": "Terraform",
    "CI/CD": "CI/CD",
    "REST API": "REST API",
    "graphql": "GraphQL",
    "gRPC": "gRPC",
    "websocket": "WebSocket",
    "microservices": "Microservices",
    "OAuth": "OAuth 2.0",
    "JWT": "JSON Web Token (JWT)",
    "SQL": "SQL",
    "NoSQL": "NoSQL",
    "postgres": "PostgreSQL",
    "redis": "Redis",
    "kafka": "Apache Kafka",
    "pyspark": "Apache Spark",
    "ETL": "ETL",
    "git": "Git",
    "react": "React",
    "typescript": "TypeScript",
    "node.js": "Node.js",
    "python": "Python",
    "rust": "Rust",
    "electron": "Electron",
    "fastapi": "FastAPI",
    "AWS": "AWS",
    "azure": "Microsoft Azure",
    "serverless": "Serverless",
    "big o notation": "Big-O notation",
    "machine learning": "Machine learning",
    "deep learning": "Deep learning",
    "NLP": "Natural language processing (NLP)",
    "RLHF": "RLHF",
    "whisper": "Whisper",
    "OCR": "OCR",
    "system design": "System design",
    "load balancer": "Load balancer",
    "CAP theorem": "CAP theorem",
}

TYPOS = {
    "langraph": "LangGraph",
    "langchian": "LangChain",
    "kubernets": "Kubernetes",
    "pytorh": "PyTorch",
    "tensorflw": "TensorFlow",
    "postgress": "PostgreSQL",
}


def test_glossary_covers_at_least_50_terms():
    assert len(EXPECTED) >= 50 and len(terms.GLOSSARY) >= 50


@pytest.mark.parametrize(("text", "canonical"), sorted(EXPECTED.items()))
def test_bare_term_becomes_explanation_request_with_reference(text, canonical):
    m = terms.interpret(text)
    assert m is not None and m.term == canonical
    assert m.question.startswith("Explain ") and canonical in m.question
    assert m.reference and len(m.reference) > 30
    assert m.note is None  # exact match: no "interpreting as" note


@pytest.mark.parametrize(("typo", "canonical"), sorted(TYPOS.items()))
def test_close_typos_are_corrected_and_announced(typo, canonical):
    m = terms.interpret(typo)
    assert m is not None and m.term == canonical
    assert m.note == f"Interpreting “{typo}” as “{canonical}”."
    assert f"Assuming you mean {canonical}" in m.question


@pytest.mark.parametrize(
    "word",
    ["lang", "graph", "chain", "cv", "cap", "rest", "spar", "nodes", "notes", "models", "rug", "rack", "mcq", "ram", "tensor", "vectors"],
)
def test_no_overcorrection_of_short_or_ordinary_words(word):
    m = terms.interpret(word)
    assert m is not None and m.term is None, f"{word!r} must not be 'corrected' to {m.term if m else None}"
    assert "do not invent facts" in m.question


@pytest.mark.parametrize("text", ["hi", "Hello", "thanks", "ok", "help", "continue", "bye"])
def test_small_talk_is_left_alone(text):
    assert terms.interpret(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "What is LangChain?",
        "how does RAG work",
        "Explain kubernetes pods",
        "write a python function to sort a list",
        "compare kafka and rabbitmq",
        "Why is my docker build slow",
        "a" * 80,
        "line one\nline two",
    ],
)
def test_full_questions_and_requests_pass_through_unchanged(text):
    assert terms.interpret(text) is None


def test_unknown_term_asks_for_honest_explanation_without_reference():
    m = terms.interpret("zorblaxify")
    assert m is not None and m.term is None and m.reference is None
    assert "zorblaxify" in m.question and "If you do not recognise it, say so plainly" in m.question


def test_clarification_replies_are_dropped_from_working_memory():
    history = [
        {"role": "user", "content": "langchain"},
        {
            "role": "assistant",
            "content": "I'm sorry, but I'm not sure what you're asking for specifically. Could you please provide more context?",
        },
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language."},
        {"role": "user", "content": "MCP"},
        {"role": "assistant", "content": "Hello! How can I assist you with MCP?"},
    ]
    kept = terms.drop_clarification_turns(history)
    assert kept == history[2:4]


def test_long_answers_mentioning_clarify_are_kept():
    long = {"role": "assistant", "content": "To clarify your question about caching: " + "details " * 80}
    assert terms.drop_clarification_turns([{"role": "user", "content": "x"}, long]) == [{"role": "user", "content": "x"}, long]
