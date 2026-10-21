"""Translation (connected mode) stored separately from the authoritative original text, plus
deterministic translation checks that flag uncertain translations for bilingual review."""
from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.prompts import TRANSLATE_SYSTEM, TRANSLATE_VERSION
from app.llm.provider import get_chat_model, provider_status

GLOSSARY = {  # approved terminology: source term -> required English rendering (case-insensitive containment)
    "reembolso": "refund", "remboursement": "refund", "rückerstattung": "refund", "contraseña": "password",
    "mot de passe": "password", "passwort": "password", "pedido": "order", "commande": "order",
}
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_CUR = re.compile(r"[€$£¥₹]|\b(?:EUR|USD|GBP|INR)\b")
_DATE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{1,2}\.\d{1,2}\.\d{2,4})\b")
_PLACE = re.compile(r"\[[A-Z_]+\]|@\[[A-Z]+\]|@\w+")
_NEG = re.compile(r"\b(no|not|never|nunca|nada|pas|jamais|nicht|kein\w*|nahi|nahin|não|nem|sin|sigue sin|toujours pas|immer noch nicht|\w+n't)\b", re.I)


def _norm_num(s: str) -> str:
    return s.replace(",", ".")


def check_translation(source: str, translation: str) -> dict:
    checks = {}
    src_nums = sorted(_norm_num(n) for n in _NUM.findall(source))
    tr_nums = sorted(_norm_num(n) for n in _NUM.findall(translation))
    checks["numbers"] = {"passed": src_nums == tr_nums, "source": src_nums, "translation": tr_nums}
    checks["currency"] = {"passed": len(_CUR.findall(source)) == len(_CUR.findall(translation))}
    checks["dates"] = {"passed": sorted(_DATE.findall(source)) == sorted(_DATE.findall(translation))}
    checks["identifiers"] = {"passed": sorted(_PLACE.findall(source)) == sorted(_PLACE.findall(translation))}
    checks["negation"] = {"passed": bool(_NEG.search(source)) == bool(_NEG.search(translation))}
    term_fail = [t for t, en in GLOSSARY.items() if t in source.lower() and en not in translation.lower()]
    checks["terminology"] = {"passed": not term_fail, "missing": term_fail}
    failed = [k for k, v in checks.items() if not v["passed"]]
    return {"checks": checks, "failed": failed, "needs_review": bool(failed)}


def translate(text: str, target: str = "English", model=None) -> dict:
    model = model or get_chat_model()
    out = model.invoke([SystemMessage(TRANSLATE_SYSTEM.format(target=target)), HumanMessage(text)])
    tr = out.content if isinstance(out.content, str) else "".join(p.get("text", "") for p in out.content if isinstance(p, dict))
    res = check_translation(text, tr)
    return {"text": tr.strip(), "model_id": provider_status()["model_id"], "prompt_version": TRANSLATE_VERSION, **res}
