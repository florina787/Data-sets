"""Build the FAISS retrieval index from analytics.duckdb.

Usage (from backend/):  uv run python -m scripts.build_embeddings
"""

from __future__ import annotations

import json

from app.retrieval.index import build_index


def main() -> None:
    print(json.dumps(build_index(), indent=2))


if __name__ == "__main__":
    main()
