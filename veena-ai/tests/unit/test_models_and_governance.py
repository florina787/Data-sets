import pytest

from backend.agents.governance import review
from backend.llm.ollama import LLMUnavailable, ModelInfo
from backend.llm.select import resolve_text_model, resolve_vision_model
from backend.models.hardware import detect
from backend.models.profiles import recommend_profile

TEXT = ModelInfo("qwen2.5:3b", 1_900_000_000, "qwen2", "3B", "Q4", ["completion"])
VIS = ModelInfo("qwen2.5vl:3b", 3_200_000_000, "qwen25vl", "3.8B", "Q4", ["completion", "vision"])
LLAMA = ModelInfo("llama3.2:3b", 2_000_000_000, "llama", "3B", "Q4", ["completion"])


def test_text_model_prefers_setting_then_qwen():
    assert resolve_text_model("llama3.2:3b", [TEXT, LLAMA]) == "llama3.2:3b"
    assert resolve_text_model(None, [LLAMA, TEXT, VIS]) == "qwen2.5:3b"
    with pytest.raises(LLMUnavailable):
        resolve_text_model(None, [])


def test_vision_model_only_from_capabilities():
    # A Qwen name is not enough: only models Ollama reports as vision qualify.
    assert resolve_vision_model(None, [TEXT, LLAMA]) is None
    assert resolve_vision_model("qwen2.5:3b", [TEXT, VIS]) == "qwen2.5vl:3b"


@pytest.mark.parametrize(
    "ram,gpus,disk,expected",
    [
        (8, [], 100, "lite"),
        (16, [], 100, "balanced"),
        (32, [], 100, "performance"),
        (16, [{"accelerated": True, "vram_mb": 12288}], 100, "performance"),
        (16, [{"accelerated": False, "vram_mb": 12288}], 100, "balanced"),
        (32, [], 4, "lite"),
    ],
)
def test_profile_recommendation(ram, gpus, disk, expected):
    rec = recommend_profile({"ram_gb": ram, "gpus": gpus, "disk_free_gb": disk})
    assert rec["profile"] == expected
    assert "benchmark" in rec["caveat"].lower()


def test_hardware_detection_on_this_machine():
    hw = detect()
    assert hw["ram_gb"] > 0 and hw["cpu"]["logical_cores"] >= 1
    assert hw["os"]["system"] in ("Linux", "Darwin", "Windows")
    assert "python" in hw["runtimes"]


def test_governance_flags():
    ev = [{"n": 1}, {"n": 2}]
    g = review("Answer [1] and [7].", evidence=ev, knowledge_requested=True, interview_mode=False, resume_evidence=False, notes=[])
    assert any(f["kind"] == "invalid_citation" for f in g["flags"]) and g["cited"] == [1]
    g = review("No evidence here.", evidence=[], knowledge_requested=True, interview_mode=False, resume_evidence=False, notes=[])
    assert g["flags"][0]["kind"] == "no_evidence"
    g = review(
        "I led a team that increased revenue 40%.",
        evidence=[],
        knowledge_requested=False,
        interview_mode=True,
        resume_evidence=False,
        notes=[],
    )
    kinds = {f["kind"] for f in g["flags"]}
    assert {"unsupported_experience", "unsupported_metric"} <= kinds
    g = review("Grounded [2].", evidence=ev, knowledge_requested=True, interview_mode=False, resume_evidence=False, notes=[])
    assert g["grounded"] and not g["flags"]
