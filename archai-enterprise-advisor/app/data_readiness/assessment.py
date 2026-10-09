"""Data readiness assessment.

Readiness is about the *data*, not about which tools exist. In particular a
vector database being present is never, by itself, a reason to recommend RAG.
"""

from __future__ import annotations

from app.models.enums import DataStore
from app.models.inputs import CurrentArchitecture, DataProfile
from app.models.outputs import DataReadinessAssessment, Score, ScoreFactor

DATA_WEIGHTS: dict[str, float] = {
    "availability": 20,
    "quality": 20,
    "freshness": 10,
    "ownership": 10,
    "lineage": 7.5,
    "metadata": 7.5,
    "permissions": 15,
    "document_quality": 10,
}

#: Minimum readiness for a RAG recommendation to be responsible.
RAG_MIN_DATA_READINESS = 40.0


def data_readiness_score(profile: DataProfile) -> Score:
    factors = []
    for name, weight in DATA_WEIGHTS.items():
        raw = getattr(profile, name) / 5
        factors.append(ScoreFactor(name=name, raw=round(raw, 3), weight=weight, contribution=round(raw * weight, 2)))
    value = round(sum(f.contribution for f in factors), 1)
    return Score(key="data_readiness", label="Data Readiness", value=value, factors=factors)


def _label(score: float) -> str:
    if score >= 75:
        return "AI-ready data"
    if score >= 55:
        return "Usable with targeted remediation"
    if score >= 40:
        return "Significant remediation needed"
    return "Not ready — fix data foundations first"


def assess_data_readiness(profile: DataProfile, arch: CurrentArchitecture) -> DataReadinessAssessment:
    score = data_readiness_score(profile)
    strengths: list[str] = []
    gaps: list[str] = []
    for f in score.factors:
        rating = round(f.raw * 5)
        if rating >= 4:
            strengths.append(f"{f.name.replace('_', ' ').title()} is strong ({rating}/5).")
        elif rating <= 2:
            gaps.append(f"{f.name.replace('_', ' ').title()} is weak ({rating}/5).")
    if profile.knowledge_fragmentation >= 4:
        gaps.append("Knowledge is highly fragmented across repositories — consolidation/indexing effort required.")

    rag_notes: list[str] = []
    if profile.document_quality < 2:
        rag_notes.append("Document quality too low for reliable grounding (garbage-in, garbage-out).")
    if profile.permissions < 2:
        rag_notes.append("Document permissions are not well defined — permission-aware retrieval impossible.")
    if score.value < RAG_MIN_DATA_READINESS:
        rag_notes.append(f"Overall data readiness {score.value:.0f} < {RAG_MIN_DATA_READINESS:.0f} minimum for RAG.")
    rag_ok = not rag_notes
    if rag_ok:
        rag_notes.append("Document quality, permissions and overall readiness meet RAG prerequisites.")

    vdb_note = (
        "A vector database already exists; it can be reused IF semantic retrieval is justified by the use case. "
        "Its presence alone does not justify RAG."
        if DataStore.VECTOR_DATABASE in arch.data_stores
        else "No vector database present; one is only added if semantic retrieval is justified."
    )
    return DataReadinessAssessment(
        score=score.value,
        maturity_label=_label(score.value),
        unstructured_share_pct=100 - profile.structured_share_pct,
        strengths=strengths,
        gaps=gaps,
        rag_prerequisites_met=rag_ok,
        rag_prerequisite_notes=rag_notes,
        vector_database_note=vdb_note,
    )
