"""Approved communication drafting.

Drafts are produced ONLY from compliance-approved templates (six languages) filled with figures from deterministic
tools. Translation validation checks that every number, currency amount, date and preserved term in the English master
also appears in the localized draft. A compliance pre-check screens prohibited content and required disclosures.
Sending is never performed here: it requires an approved `comms:send` approval (see approvals/service.py)."""
from __future__ import annotations

import re

import yaml

from analytics.service import portfolio_metrics
from backend.config import ROOT

DISCLOSURE = {
    "en": "Past performance is not indicative of future results. This message is for information and is not a recommendation.",
    "fr": "Le rendement passé n'est pas indicatif des résultats futurs. Ce message est fourni à titre informatif et ne constitue pas une recommandation.",
    "es": "El rendimiento pasado no es indicativo de resultados futuros. Este mensaje es informativo y no constituye una recomendación.",
    "hi": "पिछला प्रदर्शन भविष्य के परिणामों का संकेत नहीं है। यह संदेश केवल जानकारी के लिए है और कोई सिफारिश नहीं है।",
    "ta": "கடந்த கால செயல்திறன் எதிர்கால முடிவுகளைக் குறிக்காது. இந்தச் செய்தி தகவலுக்காக மட்டுமே; இது பரிந்துரை அல்ல.",
    "ko": "과거 성과가 미래 결과를 보장하지 않습니다. 본 메시지는 정보 제공 목적이며 권유가 아닙니다.",
}
SUBJECT = {"en": "Your FLO portfolio review", "fr": "Revue de votre portefeuille FLO", "es": "Revisión de su cartera FLO",
           "hi": "आपके FLO पोर्टफोलियो की समीक्षा", "ta": "உங்கள் FLO போர்ட்ஃபோலியோ மதிப்பாய்வு", "ko": "FLO 포트폴리오 검토 안내"}
BODY = {
    "en": "Dear {first},\n\nAs of {as_of}, your FLO portfolio {pid} was valued at CAD {mv}. Over the last 24 months it returned {ret}% per year (time-weighted), compared with {bret}% per year for its benchmark. {goal_line}\n\nI would welcome the opportunity to review your plan together.\n\n{advisor}",
    "fr": "Bonjour {first},\n\nAu {as_of}, votre portefeuille FLO {pid} était évalué à CAD {mv}. Au cours des 24 derniers mois, son rendement a été de {ret}% par année (pondéré dans le temps), comparativement à {bret}% par année pour son indice de référence. {goal_line}\n\nJe serais heureux de revoir votre plan avec vous.\n\n{advisor}",
    "es": "Estimado/a {first}:\n\nAl {as_of}, su cartera FLO {pid} tenía un valor de CAD {mv}. En los últimos 24 meses obtuvo un rendimiento de {ret}% anual (ponderado en el tiempo), frente a {bret}% anual de su índice de referencia. {goal_line}\n\nMe gustaría revisar su plan con usted.\n\n{advisor}",
    "hi": "प्रिय {first},\n\n{as_of} तक आपके FLO पोर्टफोलियो {pid} का मूल्य CAD {mv} था। पिछले 24 महीनों में इसका प्रतिफल {ret}% प्रति वर्ष (समय-भारित) रहा, जबकि इसके बेंचमार्क का {bret}% प्रति वर्ष रहा। {goal_line}\n\nमैं आपके साथ आपकी योजना की समीक्षा करना चाहूँगा/चाहूँगी।\n\n{advisor}",
    "ta": "அன்புள்ள {first},\n\n{as_of} நிலவரப்படி உங்கள் FLO போர்ட்ஃபோலியோ {pid} மதிப்பு CAD {mv}. கடந்த 24 மாதங்களில் இது ஆண்டுக்கு {ret}% வருவாய் (நேர-எடையிட்டது) ஈட்டியது; அதன் அளவுகோல் ஆண்டுக்கு {bret}%. {goal_line}\n\nஉங்கள் திட்டத்தை உங்களுடன் மதிப்பாய்வு செய்ய விரும்புகிறேன்.\n\n{advisor}",
    "ko": "{first} 고객님께,\n\n{as_of} 기준 고객님의 FLO 포트폴리오 {pid} 평가액은 CAD {mv}입니다. 지난 24개월 동안 연 {ret}%(시간가중)의 수익률을 기록했으며, 벤치마크는 연 {bret}%였습니다. {goal_line}\n\n고객님의 계획을 함께 검토할 기회를 갖고 싶습니다.\n\n{advisor}",
}
GOAL = {
    "en": "Your retirement goal is currently {funded}% funded.", "fr": "Votre objectif de retraite est actuellement financé à {funded}%.",
    "es": "Su objetivo de jubilación está financiado actualmente al {funded}%.", "hi": "आपका सेवानिवृत्ति लक्ष्य वर्तमान में {funded}% वित्तपोषित है।",
    "ta": "உங்கள் ஓய்வு இலக்கு தற்போது {funded}% நிதியளிக்கப்பட்டுள்ளது.", "ko": "고객님의 은퇴 목표 달성률은 현재 {funded}%입니다.",
}
PROHIBITED = [r"(?i)guarantee", r"(?i)garanti", r"(?i)risk[- ]free", r"(?i)sans risque", r"(?i)can'?t lose", r"(?i)assured return"]
_glossary = yaml.safe_load((ROOT / "data" / "glossary.yaml").read_text())


def _numbers(text: str) -> list[str]:
    return sorted(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text))


def validate_translation(master: str, localized: str) -> dict:
    missing_numbers = [n for n in _numbers(master) if n not in localized]
    preserved = [t for t in _glossary["preserve"] if t in master and t not in localized]
    return {"valid": not missing_numbers and not preserved, "missing_numbers": missing_numbers, "missing_terms": preserved}


def compliance_precheck(body: str, language: str) -> dict:
    hits = [p for p in PROHIBITED if re.search(p, body)]
    has_disc = DISCLOSURE[language] in body
    return {"passed": not hits and has_disc, "prohibited_hits": hits, "disclosure_present": has_disc,
            "rules": ["DOC-004 Prohibited content", "DOC-004 Approval of communications"]}


def draft_communication(ctx, client_id: str, purpose: str, language: str) -> dict:
    a = ctx.adapters
    cl = a.crm.client(client_id)
    ports = a.crm.portfolios_for(client_id)
    if not ports:
        raise ValueError("client has no managed portfolio to review")
    pm = portfolio_metrics(a, ports[0]["id"])
    bm_ann = pm["twr_annualized"] - pm["excess_annualized"]
    rules = ctx.engine.bundle.suitability
    goals = [g for g in a.crm.goals(client_id) if g["goal_type"] == "retirement"]
    funded = round(goals[0]["current_amount_cents"] / goals[0]["target_amount_cents"] * 100, 1) if goals else None
    adv = a.store.idx["advisor"][cl["advisor_id"]]["name"]
    vals = {"first": cl["full_name"].split()[0], "as_of": a.market.months()[-1].isoformat(), "pid": ports[0]["id"],
            "mv": f"{pm['market_value']:,.2f}", "ret": f"{pm['twr_annualized'] * 100:.2f}", "bret": f"{bm_ann * 100:.2f}", "advisor": adv}

    def render(lang):
        gl = GOAL[lang].format(funded=funded) if funded is not None else ""
        return BODY[lang].format(**vals, goal_line=gl) + "\n\n" + DISCLOSURE[lang]

    master = render("en")
    body = render(language)
    tv = validate_translation(master.replace(DISCLOSURE["en"], ""), body)
    pre = compliance_precheck(body, language)
    return {"client_id": client_id, "portfolio_id": ports[0]["id"], "language": language, "purpose": purpose,
            "subject": SUBJECT[language], "body": body, "master_en": master if language != "en" else None,
            "translation_validation": tv, "compliance_precheck": pre, "template_version": "COMMS-TPL-2026.1",
            "facts": {"market_value": pm["market_value"], "twr_annualized": pm["twr_annualized"], "benchmark_annualized": round(bm_ann, 6),
                      "retirement_funded_pct": funded}, "requires_approval": "comms:send",
            "suitability_rules_version": rules["version"]}
