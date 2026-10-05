"""Loads the synthetic firm into memory (read-only reference data)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.models.domain import (
    Client, Document, EthicalWall, KnowledgeDoc, Matter, Playbook, Provider, User, Workflow,
)


class DataStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        users_raw = self._load("users/users.json")
        self.firm: str = users_raw["firm"]
        self.practices: dict[str, str] = {p["practice_id"]: p["name"] for p in users_raw["practices"]}
        self.users: dict[str, User] = {u["user_id"]: User(**u) for u in users_raw["users"]}
        self.clients: dict[str, Client] = {c["client_id"]: Client(**c) for c in self._load("clients/clients.json")["clients"]}
        matters_raw = self._load("matters/matters.json")
        self.matters: dict[str, Matter] = {m["matter_id"]: Matter(**m) for m in matters_raw["matters"]}
        self.ethical_walls: list[EthicalWall] = [EthicalWall(**w) for w in matters_raw["ethical_walls"]]
        docs = (self._load("documents/project_maple_contracts.json")["documents"]
                + self._load("documents/other_matter_documents.json")["documents"])
        self.documents: dict[str, Document] = {d["doc_id"]: Document(**d) for d in docs}
        self.knowledge: dict[str, KnowledgeDoc] = {
            k["doc_id"]: KnowledgeDoc(**k) for k in self._load("policies/knowledge_corpus.json")["documents"]}
        self.playbooks: dict[str, Playbook] = {p["playbook_id"]: Playbook(**p) for p in self._load("playbooks/playbooks.json")["playbooks"]}
        self.providers: dict[str, Provider] = {p["provider_id"]: Provider(**p) for p in self._load("governance/providers.json")["providers"]}
        wf = self._load("governance/workflows.json")
        self.workflows: dict[str, Workflow] = {w["workflow_id"]: Workflow(**w) for w in wf["workflows"]}
        self.prompts: list[dict] = wf["prompts"]
        self.pregenerated: dict[str, dict] = {
            w["work_product_id"]: w for w in self._load("precedents/pregenerated_work_products.json")["work_products"]}
        self.usage_runs: list[dict] = self._load("usage/workflow_runs.json")["runs"]
        self.golden: dict = self._load("evaluations/golden_sets.json")

    def _load(self, rel: str) -> dict:
        return json.loads((self.data_dir / rel).read_text(encoding="utf-8"))

    # ---- helpers -----------------------------------------------------------
    def matter_documents(self, matter_id: str) -> list[Document]:
        return [d for d in self.documents.values() if d.matter_id == matter_id]

    def walls_for(self, matter_id: str) -> list[EthicalWall]:
        return [w for w in self.ethical_walls if matter_id in w.matter_ids]

    def playbook_for_practice(self, practice_id: str) -> Playbook | None:
        return next((p for p in self.playbooks.values() if p.practice_id == practice_id), None)

    def any_doc(self, doc_id: str):
        return self.documents.get(doc_id) or self.knowledge.get(doc_id)


@lru_cache
def get_store() -> DataStore:
    return DataStore(get_settings().data_dir)
