"""Resume parsing, analysis, fact-preserving tailoring, claim validation and export."""
from __future__ import annotations

import io
import re
from datetime import date
from typing import Any

from ..jobs.skills import extract_skills

SECTION_ALIASES = {
    "summary": ["summary", "professional summary", "profile", "about me", "objective"],
    "experience": ["experience", "work experience", "professional experience", "employment history", "work history"],
    "education": ["education", "academic background", "education and training"],
    "skills": ["skills", "technical skills", "core competencies", "technologies", "tech stack"],
    "projects": ["projects", "selected projects", "personal projects", "open source"],
    "certifications": ["certifications", "certificates", "licenses & certifications", "licenses and certifications"],
}
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
DATE_TOKEN = rf"(?:(?:{MONTHS})[a-z]*\.?\s+)?(?:19|20)\d{{2}}|present|current|now"
RANGE_RE = re.compile(rf"(?P<start>{DATE_TOKEN})\s*(?:-|–|—|to)\s*(?P<end>{DATE_TOKEN})", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com)/[\w\-/]+", re.I)
DEGREE_RE = re.compile(r"\b(B\.?Sc|BSc|B\.?A\.?|BA|B\.?Eng|BEng|B\.?Tech|BTech|M\.?Sc|MSc|M\.?A\.?|MBA|M\.?Eng|MEng|M\.?Tech|Ph\.?D|PhD|Bachelor[^,\n]*|Master[^,\n]*|Doctor[^,\n]*|Diploma[^,\n]*|Associate[^,\n]*)", re.I)
NUMBER_CLAIM_RE = re.compile(r"(?<![\w.])(\$?\d[\d,.]*\s?(?:%|percent|k|K|M|million|billion|x|\+)?)(?![\w])")


# ---------------------------------------------------------------- text extraction
def extract_text(data: bytes, mime: str) -> str:
    if mime == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) > 20:
            raise ValueError("Resume PDFs are limited to 20 pages")
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    if mime.endswith("wordprocessingml.document"):
        import docx

        d = docx.Document(io.BytesIO(data))
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return "\n".join(parts).strip()
    return data.decode("utf-8").strip()


# ---------------------------------------------------------------- parsing
def _section_of(line: str) -> str | None:
    clean = re.sub(r"[^a-z &]", "", line.lower()).strip()
    if not clean or len(clean) > 40:
        return None
    for key, names in SECTION_ALIASES.items():
        if clean in names:
            return key
    return None


def _parse_date(tok: str) -> date | None:
    tok = tok.strip().lower()
    if tok in ("present", "current", "now"):
        return date.today()
    m = re.search(r"(19|20)\d{2}", tok)
    if not m:
        return None
    year = int(m.group(0))
    month = 1
    mm = re.match(rf"({MONTHS})", tok)
    if mm:
        month = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].index(mm.group(1)[:3]) + 1
    return date(year, month, 1)


def _split_title_employer(line: str) -> tuple[str, str]:
    line = RANGE_RE.sub("", line).strip(" ,|-–—\t")
    for sep in (" at ", " | ", " — ", " – ", " - ", ", "):
        if sep in line:
            a, b = line.split(sep, 1)
            return a.strip(" ,|"), b.strip(" ,|")
    return line, ""


def parse_resume(text: str) -> dict[str, Any]:
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for ln in lines:
        sec = _section_of(ln)
        if sec:
            current = sec
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(ln)

    header = [h for h in sections.get("header", []) if h.strip()]
    contact = {
        "name": header[0].strip() if header and not EMAIL_RE.search(header[0]) else None,
        "email": (EMAIL_RE.search(text) or [None])[0] if EMAIL_RE.search(text) else None,
        "phone": PHONE_RE.search(text).group(0).strip() if PHONE_RE.search(text) else None,
        "links": URL_RE.findall(text),
    }
    experience: list[dict[str, Any]] = []
    exp_lines = sections.get("experience", [])
    cur: dict[str, Any] | None = None
    for i, ln in enumerate(exp_lines):
        s = ln.strip()
        if not s:
            continue
        m = RANGE_RE.search(s)
        if m:
            title_line = s if len(RANGE_RE.sub("", s).strip(" ,|-–—")) > 3 else (exp_lines[i - 1].strip() if i else "")
            if cur and title_line == (exp_lines[i - 1].strip() if i else None) and cur["bullets"] and cur["bullets"][-1] == title_line:
                cur["bullets"].pop()
            title, employer = _split_title_employer(title_line)
            cur = {"title": title, "employer": employer, "start": m.group("start"), "end": m.group("end"), "bullets": []}
            experience.append(cur)
        elif cur is not None:
            cur["bullets"].append(s.lstrip("•-*· ").strip())
    education = []
    for ln in sections.get("education", []):
        s = ln.strip()
        if not s:
            continue
        deg = DEGREE_RE.search(s)
        year = re.search(r"(19|20)\d{2}", s)
        inst = re.sub(r"(19|20)\d{2}.*$", "", DEGREE_RE.sub("", s)).strip(" ,|-–—")
        if deg or re.search(r"universit|college|institute|school", s, re.I):
            education.append({"institution": inst or s, "degree": deg.group(0).strip() if deg else None,
                              "year": year.group(0) if year else None, "raw": s})
    skills_text = "\n".join(sections.get("skills", []))
    listed = [x.strip() for x in re.split(r"[,;•|\n]", skills_text) if 1 < len(x.strip()) < 40]
    skills = extract_skills(text)
    for x in listed:
        if x.lower() not in {s.lower() for s in skills}:
            skills.append(x)
    certs = [c.strip("•-* ").strip() for c in sections.get("certifications", []) if c.strip()]
    projects = [p.strip("•-* ").strip() for p in sections.get("projects", []) if p.strip()]
    return {
        "contact": contact,
        "summary": " ".join(x.strip() for x in sections.get("summary", []) if x.strip()),
        "skills": skills,
        "taxonomy_skills": extract_skills(text),
        "experience": experience,
        "education": education,
        "certifications": certs,
        "projects": projects,
        "sections_found": [k for k in sections if k != "header" and sections[k]],
        "years_experience": years_of_experience(experience),
        "word_count": len(text.split()),
    }


def years_of_experience(experience: list[dict[str, Any]]) -> float | None:
    spans = []
    for e in experience:
        a, b = _parse_date(e.get("start") or ""), _parse_date(e.get("end") or "")
        if a and b and b >= a:
            spans.append((a, b))
    if not spans:
        return None
    spans.sort()
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    days = sum((b - a).days for a, b in merged)
    return round(days / 365.25, 1)


# ---------------------------------------------------------------- analysis
def analyze_resume(parsed: dict[str, Any]) -> dict[str, Any]:
    issues, strengths = [], []
    if not parsed["contact"].get("email"):
        issues.append("No email address found.")
    if "summary" not in parsed["sections_found"]:
        issues.append("Add a 2–3 line summary at the top.")
    if not parsed["experience"]:
        issues.append("No dated work experience detected (use 'Title, Employer — Jan 2020 – Present').")
    quantified = sum(1 for e in parsed["experience"] for b in e["bullets"] if NUMBER_CLAIM_RE.search(b))
    total_bullets = sum(len(e["bullets"]) for e in parsed["experience"])
    if total_bullets and quantified / total_bullets < 0.3:
        issues.append(f"Only {quantified}/{total_bullets} bullets include a measurable result; add real figures where you have them.")
    elif total_bullets:
        strengths.append(f"{quantified}/{total_bullets} bullets are quantified.")
    if len(parsed["taxonomy_skills"]) >= 8:
        strengths.append(f"{len(parsed['taxonomy_skills'])} recognised technical skills.")
    wc = parsed["word_count"]
    if wc < 250:
        issues.append(f"Resume is short ({wc} words).")
    elif wc > 1200:
        issues.append(f"Resume is long ({wc} words); aim for 1–2 pages.")
    return {"issues": issues, "strengths": strengths, "years_experience": parsed.get("years_experience"),
            "skills": parsed["skills"], "experience_count": len(parsed["experience"])}


# ---------------------------------------------------------------- tailoring (fact-preserving)
def _relevance(bullet: str, keywords: list[str]) -> int:
    b = bullet.lower()
    return sum(1 for k in keywords if k.lower() in b)


def tailor_resume(parsed: dict[str, Any], job: dict[str, Any], *, summary_override: str | None = None) -> dict[str, Any]:
    """Re-order and emphasise *existing* content for the job. Never adds employers, degrees, skills or numbers."""
    keywords = list(dict.fromkeys((job.get("required_skills") or []) + (job.get("preferred_skills") or [])))
    have = {s.lower() for s in parsed["skills"]}
    matched = [k for k in keywords if k.lower() in have]
    skills = matched + [s for s in parsed["skills"] if s not in matched]
    experience = []
    for e in parsed["experience"]:
        bullets = sorted(e["bullets"], key=lambda b: -_relevance(b, keywords))
        experience.append({**e, "bullets": bullets})
    yrs = parsed.get("years_experience")
    latest_title = parsed["experience"][0]["title"] if parsed["experience"] else None
    default_summary = " ".join(x for x in [
        f"{latest_title}" if latest_title else "Professional",
        f"with {int(yrs)}+ years of experience" if yrs and yrs >= 1 else "",
        f"in {', '.join(matched[:5])}." if matched else ".",
    ] if x).replace(" .", ".")
    if parsed.get("summary"):
        default_summary = default_summary + " " + parsed["summary"]
    gaps = [k for k in (job.get("required_skills") or []) if k.lower() not in have]
    return {
        "contact": parsed["contact"],
        "target": {"title": job.get("title"), "company": job.get("company")},
        "summary": summary_override or default_summary,
        "skills": skills,
        "experience": experience,
        "education": parsed["education"],
        "certifications": parsed["certifications"],
        "projects": parsed["projects"],
        "gaps": gaps,
        "clarifying_questions": [f"Do you have hands-on experience with {g}? If so, add it to your profile with where you used it; "
                                 "we will not add it to your resume until you confirm." for g in gaps[:6]],
    }


def render_text(t: dict[str, Any]) -> str:
    c = t["contact"]
    out = [c.get("name") or "", " | ".join(x for x in [c.get("email"), c.get("phone"), *c.get("links", [])] if x), "",
           "SUMMARY", t["summary"], "", "SKILLS", ", ".join(t["skills"]), "", "EXPERIENCE"]
    for e in t["experience"]:
        out.append(f"{e['title']}{', ' + e['employer'] if e.get('employer') else ''} — {e.get('start', '')} – {e.get('end', '')}")
        out += [f"• {b}" for b in e["bullets"]]
        out.append("")
    if t["education"]:
        out.append("EDUCATION")
        out += [e.get("raw") or f"{e.get('degree') or ''} {e['institution']} {e.get('year') or ''}".strip() for e in t["education"]]
        out.append("")
    if t["certifications"]:
        out += ["CERTIFICATIONS", *t["certifications"], ""]
    if t["projects"]:
        out += ["PROJECTS", *t["projects"]]
    return "\n".join(out).strip()


# ---------------------------------------------------------------- claim validation
def validate_claims(original_text: str, parsed: dict[str, Any], generated_text: str) -> dict[str, Any]:
    """Flag anything in generated text that the original resume does not support."""
    orig = original_text.lower()
    issues = []
    for num in set(NUMBER_CLAIM_RE.findall(generated_text)):
        n = num.strip()
        digits = re.sub(r"[^\d.]", "", n)
        if not digits or len(digits) < 2 and "%" not in n:
            continue
        # allow the derived "N+ years" phrase if N <= verified years
        if n.endswith("+") and parsed.get("years_experience") and float(digits.rstrip(".")) <= parsed["years_experience"]:
            continue
        if digits.rstrip(".") not in re.sub(r"[,]", "", orig):
            issues.append({"type": "unsupported_number", "value": n})
    for skill in extract_skills(generated_text):
        if skill.lower() not in {s.lower() for s in parsed["skills"]} and skill not in parsed["taxonomy_skills"]:
            issues.append({"type": "unsupported_skill", "value": skill})
    for m in DEGREE_RE.finditer(generated_text):
        if m.group(0).lower()[:4] not in orig:
            issues.append({"type": "unsupported_degree", "value": m.group(0)})
    for org in re.findall(r"\b(?:at|with|for) ([A-Z][\w&.]+(?: [A-Z][\w&.]+){0,3})", generated_text):
        if org.lower() not in orig and org.split()[0].lower() not in orig:
            issues.append({"type": "unsupported_organization", "value": org})
    return {"valid": not issues, "issues": issues}


# ---------------------------------------------------------------- export
def _latin1(s: str) -> str:
    rep = {"•": "-", "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "…": "..."}
    for a, b in rep.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def export_pdf(t: dict[str, Any]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(format="Letter")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_margins(18, 15, 18)
    w = pdf.w - pdf.l_margin - pdf.r_margin
    c = t["contact"]
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(w, 9, _latin1(c.get("name") or "Resume"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(w, 5, _latin1(" | ".join(x for x in [c.get("email"), c.get("phone"), *c.get("links", [])] if x)),
                   new_x="LMARGIN", new_y="NEXT")

    def heading(txt: str) -> None:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(115, 87, 255)
        pdf.cell(w, 6, txt, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(16, 24, 40)
        pdf.set_font("Helvetica", "", 10)

    heading("SUMMARY")
    pdf.multi_cell(w, 5, _latin1(t["summary"]), new_x="LMARGIN", new_y="NEXT")
    heading("SKILLS")
    pdf.multi_cell(w, 5, _latin1(", ".join(t["skills"])), new_x="LMARGIN", new_y="NEXT")
    heading("EXPERIENCE")
    for e in t["experience"]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(w, 5, _latin1(f"{e['title']}{', ' + e['employer'] if e.get('employer') else ''}  ({e.get('start', '')} - {e.get('end', '')})"),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for b in e["bullets"]:
            pdf.multi_cell(w, 5, _latin1(f"- {b}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    if t["education"]:
        heading("EDUCATION")
        for e in t["education"]:
            pdf.multi_cell(w, 5, _latin1(e.get("raw") or e["institution"]), new_x="LMARGIN", new_y="NEXT")
    if t["certifications"]:
        heading("CERTIFICATIONS")
        for x in t["certifications"]:
            pdf.multi_cell(w, 5, _latin1(x), new_x="LMARGIN", new_y="NEXT")
    if t["projects"]:
        heading("PROJECTS")
        for x in t["projects"]:
            pdf.multi_cell(w, 5, _latin1(x), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def export_docx(t: dict[str, Any]) -> bytes:
    import docx
    from docx.shared import Pt, RGBColor

    d = docx.Document()
    c = t["contact"]
    d.add_heading(c.get("name") or "Resume", level=0)
    d.add_paragraph(" | ".join(x for x in [c.get("email"), c.get("phone"), *c.get("links", [])] if x))

    def heading(txt: str) -> None:
        h = d.add_heading(txt, level=1)
        for r in h.runs:
            r.font.color.rgb = RGBColor(0x73, 0x57, 0xFF)
            r.font.size = Pt(13)

    heading("Summary")
    d.add_paragraph(t["summary"])
    heading("Skills")
    d.add_paragraph(", ".join(t["skills"]))
    heading("Experience")
    for e in t["experience"]:
        p = d.add_paragraph()
        p.add_run(f"{e['title']}{', ' + e['employer'] if e.get('employer') else ''}").bold = True
        p.add_run(f"  ({e.get('start', '')} – {e.get('end', '')})")
        for b in e["bullets"]:
            d.add_paragraph(b, style="List Bullet")
    if t["education"]:
        heading("Education")
        for e in t["education"]:
            d.add_paragraph(e.get("raw") or e["institution"])
    if t["certifications"]:
        heading("Certifications")
        for x in t["certifications"]:
            d.add_paragraph(x, style="List Bullet")
    if t["projects"]:
        heading("Projects")
        for x in t["projects"]:
            d.add_paragraph(x, style="List Bullet")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
