"""Short-prompt interpretation: a bare technical term means "explain this".

Small local models often answer a one-word message ("langchain") with a greeting or a request for
clarification. VEENA rewrites short term-like messages into an explicit explanation request and, for
well-known technical terms, adds a one-line reference definition from this offline glossary so the
model is grounded. Typos are corrected only against this glossary and only for close matches; anything
else is passed through unchanged, with an instruction to say so honestly if the term is unknown.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

# canonical name -> (aliases, one-line reference definition). Definitions are deliberately short and
# conservative: they ground the answer, the model writes the explanation.
GLOSSARY: dict[str, tuple[tuple[str, ...], str]] = {
    "LangChain": (
        ("langchain", "lang chain"),
        "an open-source framework (Python and JavaScript) for building applications on large language models by composing prompts, models, retrievers, tools and memory into chains and agents.",
    ),
    "LangGraph": (
        ("langgraph", "lang graph"),
        "an open-source library from the LangChain team for building stateful, multi-step and multi-agent LLM applications as graphs of nodes and edges, with cycles, persistence and human-in-the-loop control.",
    ),
    "LlamaIndex": (
        ("llamaindex", "llama index", "gpt index"),
        "an open-source data framework for connecting LLMs to private data: loading, indexing and querying documents, commonly used for retrieval-augmented generation.",
    ),
    "Model Context Protocol (MCP)": (
        ("mcp", "model context protocol"),
        "an open protocol introduced by Anthropic in 2024 that standardises how AI applications connect to external tools, data sources and prompts through MCP servers and clients. (MCP can also mean Microsoft Certified Professional outside AI.)",
    ),
    "Retrieval-Augmented Generation (RAG)": (
        ("rag", "retrieval augmented generation", "retrieval-augmented generation"),
        "a technique where relevant passages are retrieved from a document collection (often via embeddings and a vector index) and given to a language model so its answer is grounded in, and can cite, those sources.",
    ),
    "Large Language Model (LLM)": (
        ("llm", "llms", "large language model"),
        "a neural network, usually a transformer, trained on large text corpora to predict tokens, and used for generation, question answering, summarisation and coding.",
    ),
    "Transformer": (
        ("transformer", "transformers", "transformer architecture"),
        "the neural-network architecture introduced in 'Attention Is All You Need' (2017) that uses self-attention instead of recurrence; the basis of most modern language models.",
    ),
    "Attention mechanism": (
        ("attention", "self attention", "self-attention", "attention mechanism"),
        "a mechanism that lets a model weigh how relevant each token is to every other token when building representations; self-attention is the core of transformers.",
    ),
    "Embeddings": (
        ("embedding", "embeddings", "vector embeddings"),
        "dense numeric vectors that represent text, images or other data so that similar meanings are close together; used for semantic search, clustering and RAG.",
    ),
    "Vector database": (
        ("vector database", "vector db", "vectordb", "vector store"),
        "a database optimised to store embeddings and run fast nearest-neighbour similarity search, e.g. FAISS (a library), Chroma, Qdrant, Milvus, Weaviate or pgvector.",
    ),
    "FAISS": (
        ("faiss",),
        "Facebook AI Similarity Search, an open-source library from Meta for efficient similarity search and clustering of dense vectors.",
    ),
    "Fine-tuning": (
        ("fine tuning", "fine-tuning", "finetuning"),
        "further training a pre-trained model on a smaller task- or domain-specific dataset to adapt its behaviour.",
    ),
    "LoRA": (
        ("lora", "low rank adaptation", "low-rank adaptation"),
        "Low-Rank Adaptation, a parameter-efficient fine-tuning method that trains small low-rank matrices added to a frozen model's weights.",
    ),
    "Quantization": (
        ("quantization", "quantisation", "model quantization"),
        "reducing the numeric precision of model weights (e.g. from 16-bit to 4-bit) to cut memory use and speed up inference with some accuracy trade-off.",
    ),
    "Prompt engineering": (
        ("prompt engineering",),
        "designing and refining the instructions, examples and context given to a language model to get reliable, useful outputs.",
    ),
    "Hallucination (AI)": (
        ("hallucination", "hallucinations", "ai hallucination"),
        "when a language model produces fluent but false or unsupported content; mitigated by grounding (e.g. RAG), citations and verification.",
    ),
    "AI agent": (
        ("ai agent", "ai agents", "agentic ai", "llm agent"),
        "a system in which a language model plans and takes actions, typically by calling tools or APIs in a loop, to accomplish a goal.",
    ),
    "Function calling / tool use": (
        ("function calling", "tool calling", "tool use"),
        "a capability where a language model outputs structured calls (usually JSON) to functions or tools that the application executes and returns results from.",
    ),
    "Ollama": (
        ("ollama",),
        "an open-source tool for downloading and running large language models locally, exposing a local HTTP API; VEENA uses it as its local AI runtime.",
    ),
    "Hugging Face": (("hugging face", "huggingface"), "a company and platform hosting open models, datasets and the Transformers library."),
    "PyTorch": (
        ("pytorch",),
        "an open-source deep-learning framework originally from Meta, with dynamic computation graphs and GPU acceleration.",
    ),
    "TensorFlow": (("tensorflow",), "an open-source machine-learning framework from Google for building and deploying neural networks."),
    "Kubernetes": (
        ("kubernetes", "k8s"),
        "an open-source system for automating deployment, scaling and management of containerised applications across clusters.",
    ),
    "Docker": (("docker",), "a platform for packaging applications and their dependencies into portable containers built from images."),
    "Terraform": (
        ("terraform",),
        "an infrastructure-as-code tool from HashiCorp that provisions cloud resources from declarative configuration files.",
    ),
    "CI/CD": (
        ("ci/cd", "cicd", "ci cd", "continuous integration"),
        "continuous integration and continuous delivery/deployment: automatically building, testing and releasing code on every change.",
    ),
    "REST API": (
        ("rest api", "restful"),
        "an architectural style for web APIs that exposes resources at URLs and uses HTTP methods such as GET, POST, PUT and DELETE.",
    ),
    "GraphQL": (
        ("graphql",),
        "a query language and runtime for APIs that lets clients request exactly the fields they need from a typed schema.",
    ),
    "gRPC": (("grpc",), "a high-performance open-source RPC framework from Google using HTTP/2 and Protocol Buffers."),
    "WebSocket": (
        ("websocket", "websockets"),
        "a protocol providing a persistent, full-duplex connection between client and server over a single TCP connection.",
    ),
    "Microservices": (
        ("microservices", "microservice"),
        "an architecture where an application is split into small, independently deployable services that communicate over the network.",
    ),
    "OAuth 2.0": (
        ("oauth", "oauth2", "oauth 2.0"),
        "an authorisation framework that lets applications obtain limited access to a user's resources without receiving their password.",
    ),
    "JSON Web Token (JWT)": (
        ("jwt", "json web token"),
        "a compact, signed token format for transmitting claims between parties, often used for authentication.",
    ),
    "SQL": (("sql",), "Structured Query Language, the standard language for querying and managing relational databases."),
    "NoSQL": (("nosql",), "a family of non-relational databases such as document, key-value, wide-column and graph stores."),
    "PostgreSQL": (
        ("postgresql", "postgres"),
        "a powerful open-source relational database known for standards compliance and extensibility.",
    ),
    "Redis": (("redis",), "an in-memory data store used as a cache, message broker and database, with rich data structures."),
    "Apache Kafka": (
        ("kafka", "apache kafka"),
        "a distributed event-streaming platform for high-throughput, durable publish/subscribe messaging.",
    ),
    "Apache Spark": (("spark", "apache spark", "pyspark"), "a distributed engine for large-scale data processing and analytics."),
    "ETL": (
        ("etl", "elt"),
        "extract, transform, load: moving data from sources, reshaping it, and loading it into a target such as a data warehouse.",
    ),
    "Git": (("git",), "a distributed version-control system for tracking changes to source code."),
    "React": (
        ("react", "reactjs", "react.js"),
        "an open-source JavaScript library from Meta for building user interfaces from components.",
    ),
    "TypeScript": (("typescript",), "a typed superset of JavaScript from Microsoft that compiles to plain JavaScript."),
    "Node.js": (
        ("node", "nodejs", "node.js"),
        "a JavaScript runtime built on Chrome's V8 engine for running JavaScript outside the browser.",
    ),
    "Python": (
        ("python",),
        "a high-level, general-purpose programming language known for readability, widely used in data science, AI and automation.",
    ),
    "Rust": (("rust", "rustlang"), "a systems programming language focused on memory safety and performance without a garbage collector."),
    "Electron": (
        ("electron", "electronjs"),
        "a framework for building cross-platform desktop apps with web technologies (Chromium and Node.js).",
    ),
    "FastAPI": (
        ("fastapi", "fast api"),
        "a modern Python web framework for building APIs with type hints, automatic validation and OpenAPI docs.",
    ),
    "AWS": (("aws", "amazon web services"), "Amazon Web Services, Amazon's cloud computing platform."),
    "Microsoft Azure": (("azure",), "Microsoft's cloud computing platform."),
    "Google Cloud Platform (GCP)": (("gcp", "google cloud"), "Google's cloud computing platform."),
    "Serverless": (
        ("serverless",),
        "a cloud model where the provider runs and scales code on demand (e.g. functions) and bills per use, without managing servers.",
    ),
    "Big-O notation": (
        ("big o", "big-o", "big o notation", "time complexity"),
        "notation describing how an algorithm's time or memory grows with input size in the worst case, e.g. O(n log n).",
    ),
    "Machine learning": (
        ("machine learning", "ml"),
        "methods that let computers learn patterns from data to make predictions or decisions without being explicitly programmed for each case.",
    ),
    "Deep learning": (("deep learning",), "machine learning with multi-layer neural networks that learn hierarchical representations."),
    "Natural language processing (NLP)": (
        ("nlp", "natural language processing"),
        "the field of computing that analyses, understands and generates human language.",
    ),
    "Computer vision": (
        ("computer vision",),
        "the field of AI that interprets images and video, e.g. classification, detection and segmentation.",
    ),
    "Reinforcement learning": (
        ("reinforcement learning", "rl"),
        "learning by trial and error, where an agent takes actions in an environment to maximise cumulative reward.",
    ),
    "RLHF": (
        ("rlhf", "reinforcement learning from human feedback"),
        "reinforcement learning from human feedback: aligning a model using a reward model trained on human preference comparisons.",
    ),
    "Speech recognition (ASR)": (
        ("asr", "speech recognition", "speech to text", "speech-to-text"),
        "automatic speech recognition: converting spoken audio into text, e.g. with Whisper.",
    ),
    "Whisper": (("whisper",), "an open-source speech-recognition model from OpenAI; VEENA runs it locally via faster-whisper."),
    "OCR": (("ocr", "optical character recognition"), "optical character recognition: extracting text from images, e.g. with Tesseract."),
    "Agile / Scrum": (
        ("agile", "scrum"),
        "iterative software-delivery approaches; Scrum organises work into short sprints with defined roles and ceremonies.",
    ),
    "System design": (
        ("system design",),
        "designing the architecture of a software system: components, data flow, storage, scaling, reliability and trade-offs.",
    ),
    "Load balancer": (
        ("load balancer", "load balancing"),
        "a component that distributes incoming traffic across multiple servers for scalability and availability.",
    ),
    "Caching": (("cache", "caching"), "storing copies of frequently used data in a faster layer to reduce latency and load."),
    "CAP theorem": (
        ("cap theorem",),
        "the principle that a distributed data store cannot simultaneously guarantee consistency, availability and partition tolerance; under a network partition it must trade consistency against availability.",
    ),
}

_ALIASES: dict[str, str] = {}
for _canon, (_aliases, _) in GLOSSARY.items():
    for _a in _aliases:
        _ALIASES[_a.lower()] = _canon

# Messages that are conversational, not terms to explain.
SMALL_TALK = {
    "hi",
    "hello",
    "hey",
    "hiya",
    "thanks",
    "thank you",
    "thx",
    "ok",
    "okay",
    "yes",
    "no",
    "yep",
    "nope",
    "sure",
    "good morning",
    "good evening",
    "good night",
    "bye",
    "goodbye",
    "cool",
    "great",
    "nice",
    "lol",
    "help",
    "continue",
    "go on",
    "more",
    "again",
    "why",
    "how",
    "what",
    "stop",
}

# Ordinary words that look like a glossary alias but must never be "corrected" into one.
NEVER_CORRECT = {
    "nodes",
    "notes",
    "codes",
    "model",
    "models",
    "graph",
    "graphs",
    "chain",
    "chains",
    "agent",
    "agents",
    "token",
    "tokens",
    "spark",
    "sparks",
    "docket",
    "rusty",
    "react",
    "reacts",
    "python",
    "pythons",
    "cache",
    "caches",
    "whisper",
    "whispers",
    "kafka",
    "redis",
    "terra",
    "torch",
    "tensor",
    "tensors",
    "vector",
    "vectors",
    "lang",
}

CLARIFICATION = re.compile(
    r"(not sure what you(?:'|’)re asking|didn(?:'|’)t understand|could you (?:please )?(?:provide more|clarify)|"
    r"please (?:provide more context|clarify)|how can i (?:assist|help) you with)",
    re.I,
)


@dataclass
class Interpretation:
    question: str  # what the model is asked
    reference: str | None  # glossary definition to ground the answer
    note: str | None  # shown to the user, e.g. a typo interpretation
    term: str | None  # canonical term, when recognised


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().strip(".!").strip()).lower()


def lookup(text: str) -> tuple[str | None, bool]:
    """Canonical term for `text` and whether it was a typo correction. Exact aliases first, then a
    close fuzzy match (at least 5 letters on both sides, high similarity) so 'langraph' -> LangGraph but
    short or ambiguous words are never 'corrected'."""
    key = _clean(text)
    if key in _ALIASES:
        return _ALIASES[key], False
    # Both sides at least 5 letters: short words ("node", "spar", "rag") are too easy to mis-correct.
    if len(key) < 5 or len(key.split()) > 3 or key in NEVER_CORRECT:
        return None, False
    match = difflib.get_close_matches(key, [a for a in _ALIASES if len(a) >= 5], n=1, cutoff=0.86)
    return (_ALIASES[match[0]], True) if match else (None, False)


def is_short_term(text: str) -> bool:
    """A bare term or short noun phrase, not a sentence, question or command."""
    t = text.strip()
    if not t or "?" in t or "\n" in t or len(t) > 60:
        return False
    words = t.split()
    if len(words) > 4 or _clean(t) in SMALL_TALK:
        return False
    first = words[0].lower()
    if len(words) > 1 and first in {
        "what",
        "how",
        "why",
        "when",
        "where",
        "who",
        "which",
        "can",
        "could",
        "should",
        "is",
        "are",
        "do",
        "does",
        "explain",
        "write",
        "show",
        "give",
        "tell",
        "list",
        "compare",
        "make",
        "create",
        "fix",
        "summarise",
        "summarize",
        "translate",
    }:
        return False  # already a request; leave it to the model
    return True


def interpret(text: str) -> Interpretation | None:
    """None when the message should be sent unchanged."""
    if not is_short_term(text):
        return None
    raw = text.strip().strip(".!")
    term, corrected = lookup(raw)
    if term:
        note = f"Interpreting “{raw}” as “{term}”." if corrected else None
        lead = (
            f"(“{raw}” is most likely a misspelling of {term}.) Begin your answer with exactly: “Assuming you mean {term}:” and then answer. "
            if corrected
            else ""
        )
        return Interpretation(
            question=f"{lead}Explain {term}: what it is, what it is used for, its main components or ideas, and a typical use case.",
            reference=GLOSSARY[term][1],
            note=note,
            term=term,
        )
    return Interpretation(
        question=(
            f"The user sent only “{raw}”. Treat it as a request to explain it: what it is, what it is used for "
            "and a short example. If it has several common meanings, briefly cover the most likely ones. If you "
            "do not recognise it, say so plainly and ask what it refers to; do not invent facts."
        ),
        reference=None,
        note=None,
        term=None,
    )


def drop_clarification_turns(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Remove short 'please clarify' replies (and the turn that prompted them) from working memory, so a
    small model does not copy them into the next answer."""
    out: list[dict[str, str]] = []
    for m in history:
        if m["role"] == "assistant" and len(m["content"]) < 400 and CLARIFICATION.search(m["content"]):
            if out and out[-1]["role"] == "user":
                out.pop()
            continue
        out.append(m)
    return out
