"""Thin HTTP client for the FastAPI backend.

The frontend only knows the API base URL. It never reads or handles any LLM
API key: all model calls happen server-side.
"""

from __future__ import annotations

from typing import Any

import httpx


class APIError(RuntimeError):
    """Raised when the backend is unreachable or returns an error."""


class CopilotAPI:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise APIError(f"Cannot reach the copilot API ({type(exc).__name__}). Is the backend running?") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            if isinstance(detail, dict):
                detail = f"{detail.get('message')} (request_id={detail.get('request_id')})"
            raise APIError(f"API error {response.status_code}: {detail}")
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def chat(self, question: str, top_k: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"question": question}
        if top_k:
            payload["top_k"] = top_k
        return self._request("POST", "/chat", json=payload)

    def upload(self, filename: str, data: bytes, content_type: str | None) -> dict[str, Any]:
        files = {"file": (filename, data, content_type or "application/octet-stream")}
        return self._request("POST", "/documents/upload", files=files)

    def documents(self) -> list[dict[str, Any]]:
        return self._request("GET", "/documents")

    def tools(self) -> list[dict[str, Any]]:
        return self._request("GET", "/tools")

    def metrics(self) -> dict[str, Any]:
        return self._request("GET", "/metrics")
