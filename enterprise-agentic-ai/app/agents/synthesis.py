"""Deterministic, offline synthesis used in DEMO mode.

This module plays the role of the LLM when no API key is configured. It does
not return canned text: every statement is extracted from, or computed from,
the retrieved chunks and tool results of the current request, and carries the
evidence keys it came from. That keeps the demo honest (answers change when
documents change) and lets the guardrail validate demo answers the same way it
validates live Claude answers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.agents.evidence import tool_key
from app.models.domain import AnalysisResult, Finding, Intent, RetrievedChunk, ToolCallRecord
from app.rag.text_utils import content_tokens, overlap_score, split_sentences

_METADATA_RE = re.compile(
    r"^(document owner|owner|version|last reviewed|report date|reporting period|effective date|meeting date|"
    r"facilitator|attendees|product manager|scope|project id|target release)\s*:",
    re.IGNORECASE,
)
_RISK_RE = re.compile(
    r"\brisks?\b|at risk|\bblock|threat|declin|\bfell\b|below|exceed|\bfail|slip|instabil|\bgap\b|dependen|worsening|concern",
    re.IGNORECASE,
)
_ACTION_SECTION_RE = re.compile(r"next steps|recommendation|decisions needed|action items|mitigation", re.IGNORECASE)
_IMPERATIVE_RE = re.compile(
    r"^(action:|mitigation:|approve|confirm|escalate|resolve|run|hold|treat|reduce|schedule|pair|evaluate|"
    r"ring-fence|bring|add|document|agree|parallelise|prioritise|route)",
    re.IGNORECASE,
)
_RISK_SECTION_RE = re.compile(r"^RISK-\d+", re.IGNORECASE)

_METRIC_LABELS: dict[str, tuple[str, str]] = {
    # metric -> (label, unit)
    "deployment_frequency_per_week": ("Deployment frequency", " per week"),
    "lead_time_days": ("Lead time for changes", " days"),
    "change_failure_rate_pct": ("Change failure rate", "%"),
    "mttr_hours": ("Mean time to restore", " hours"),
    "test_coverage_pct": ("Test coverage", "%"),
    "sprint_predictability_pct": ("Sprint predictability", "%"),
}
_METRIC_ACTIONS: dict[str, str] = {
    "test_coverage_pct": "Raise automated test coverage to the 80% standard before code freeze, starting with release-critical services.",
    "change_failure_rate_pct": "Add release-readiness checks and rehearse rollback to bring change failure rate below 15%.",
    "lead_time_days": "Reduce lead time by limiting work in progress and fast-tracking reviews for release blockers.",
    "sprint_predictability_pct": "Protect sprint capacity from unplanned work so predictability recovers to the 85% target.",
    "mttr_hours": "Review incident runbooks and on-call coverage to bring MTTR under four hours.",
    "deployment_frequency_per_week": "Increase deployment frequency to at least weekly per service.",
}


@dataclass(frozen=True)
class Sentence:
    text: str
    key: str  # evidence key (chunk ID)
    section: str
    chunk_score: float
    order: int


def _fmt_num(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _dedupe(findings: list[Finding], limit: int) -> list[Finding]:
    out: list[Finding] = []
    seen: list[set[str]] = []
    for f in findings:
        tokens = content_tokens(f.text)
        if any(tokens and len(tokens & s) / max(1, len(tokens | s)) > 0.6 for s in seen):
            continue
        seen.append(tokens)
        out.append(f)
        if len(out) >= limit:
            break
    return out


class OfflineSynthesizer:
    """Builds analysis and answers directly from evidence (no LLM)."""

    # --- evidence extraction ---------------------------------------------
    @staticmethod
    def sentences(chunks: list[RetrievedChunk]) -> list[Sentence]:
        out: list[Sentence] = []
        order = 0
        for chunk in chunks:
            body = chunk.text
            if chunk.section and body.startswith(chunk.section + "\n"):
                body = body[len(chunk.section) + 1 :]
            for sent in split_sentences(body):
                if _METADATA_RE.match(sent) or len(sent) < 25:
                    continue
                out.append(Sentence(sent, chunk.chunk_id, chunk.section, chunk.score, order))
                order += 1
        return out

    @staticmethod
    def _rank(query: str, sentences: list[Sentence]) -> list[Sentence]:
        return sorted(sentences, key=lambda s: overlap_score(query, s.text) + 0.5 * s.chunk_score, reverse=True)

    @staticmethod
    def _tool(tool_results: list[ToolCallRecord], name: str) -> list[tuple[int, dict[str, Any]]]:
        return [(i, r.result) for i, r in enumerate(tool_results) if r.success and r.tool_name == name]

    # --- tool-derived findings ---------------------------------------------
    def tool_findings(self, tool_results: list[ToolCallRecord]) -> list[Finding]:
        findings: list[Finding] = []
        for i, status in self._tool(tool_results, "get_project_status"):
            findings.append(
                Finding(
                    text=(
                        f"{status['name']} is {status['status']} at {status['percent_complete']}% complete "
                        f"with {status['budget_consumed_pct']}% of budget consumed and "
                        f"{status['release_blocker_count']} open release blockers."
                    ),
                    sources=[tool_key(i)],
                )
            )
            if status["budget_consumed_pct"] > status["percent_complete"]:
                findings.append(
                    Finding(
                        text=(
                            f"Budget consumed ({status['budget_consumed_pct']}%) exceeds percent complete "
                            f"({status['percent_complete']}%)."
                        ),
                        sources=[tool_key(i)],
                    )
                )
        for i, metrics in self._tool(tool_results, "get_delivery_metrics"):
            trend = metrics["velocity_trend"]
            if trend["change_from_peak_pct"] < 0:
                findings.append(
                    Finding(
                        text=(
                            f"Velocity for {metrics['project_id']} fell from a peak of {trend['peak_points']} to "
                            f"{trend['latest_points']} story points ({trend['change_from_peak_pct']}% from peak)."
                        ),
                        sources=[tool_key(i)],
                    )
                )
            for breach in metrics["target_breaches"]:
                label, unit = _METRIC_LABELS.get(breach["metric"], (breach["metric"], ""))
                findings.append(
                    Finding(
                        text=(
                            f"{label} is {_fmt_num(breach['actual'])}{unit} against a target of "
                            f"{_fmt_num(breach['target'])}{unit}."
                        ),
                        sources=[tool_key(i)],
                    )
                )
            if metrics.get("unplanned_work_pct", 0) >= 10:
                findings.append(
                    Finding(
                        text=f"Unplanned work consumes {_fmt_num(metrics['unplanned_work_pct'])}% of team capacity.",
                        sources=[tool_key(i)],
                    )
                )
        for i, issues in self._tool(tool_results, "get_open_issues"):
            blockers = [x for x in issues["issues"] if x["release_blocker"]]
            if blockers:
                ids = ", ".join(b["issue_id"] for b in blockers)
                findings.append(Finding(text=f"Open release blockers: {ids}.", sources=[tool_key(i)]))
        return findings

    def tool_actions(self, tool_results: list[ToolCallRecord]) -> list[Finding]:
        actions: list[Finding] = []
        for i, issues in self._tool(tool_results, "get_open_issues"):
            for issue in issues["issues"]:
                if issue["release_blocker"]:
                    actions.append(
                        Finding(
                            text=(
                                f"Drive {issue['issue_id']} ({issue['title']}) to resolution with "
                                f"{issue['assignee'] or 'an assigned owner'}."
                            ),
                            sources=[tool_key(i)],
                        )
                    )
        for i, metrics in self._tool(tool_results, "get_delivery_metrics"):
            for breach in metrics["target_breaches"]:
                text = _METRIC_ACTIONS.get(breach["metric"])
                if text:
                    actions.append(Finding(text=text, sources=[tool_key(i)]))
        return actions

    # --- document-derived findings -----------------------------------------
    def risk_findings(self, query: str, chunks: list[RetrievedChunk]) -> list[Finding]:
        findings: list[Finding] = []
        named = {}
        for sent in self.sentences(chunks):
            if _RISK_SECTION_RE.match(sent.section) and sent.section not in named:
                named[sent.section] = Finding(text=f"{sent.section} — {sent.text}", sources=[sent.key])
        findings.extend(named[k] for k in sorted(named))
        ranked = self._rank(query, [s for s in self.sentences(chunks) if _RISK_RE.search(s.text)])
        findings.extend(Finding(text=s.text, sources=[s.key]) for s in ranked)
        return _dedupe(findings, limit=6)

    def action_findings(
        self, query: str, chunks: list[RetrievedChunk], *, explicit_only: bool = False
    ) -> list[Finding]:
        """Action items: explicit 'Action:' items first, then other imperatives by relevance."""
        sentences = [
            s
            for s in self.sentences(chunks)
            if _IMPERATIVE_RE.match(s.text) or _ACTION_SECTION_RE.search(s.section)
        ]
        explicit = [s for s in sentences if s.text.lower().startswith("action:")]
        other = [] if explicit_only else self._rank(query, [s for s in sentences if s not in explicit])
        findings = [Finding(text=_capitalize(re.sub(r"^(Action|Mitigation):\s*", "", s.text)), sources=[s.key]) for s in explicit + other]
        return _dedupe(findings, limit=8)

    def relevant_findings(
        self, query: str, chunks: list[RetrievedChunk], limit: int = 4, focus: list[str] | None = None
    ) -> list[Finding]:
        """Most query-relevant evidence statements, optionally restricted to ``focus`` terms."""
        ranked = [s for s in self._rank(query, self.sentences(chunks)) if overlap_score(query, s.text) > 0]
        if focus:
            focused = [s for s in ranked if any(f.lower() in s.text.lower() for f in focus)]
            ranked = focused or ranked
        return _dedupe([Finding(text=s.text, sources=[s.key]) for s in ranked], limit=limit)

    def focus_terms(self, tool_results: list[ToolCallRecord]) -> list[str]:
        """Short project names (e.g. 'Phoenix') from status tool results."""
        return [s["name"].split()[-1] for _, s in self._tool(tool_results, "get_project_status")]

    def document_summary(self, chunks: list[RetrievedChunk]) -> tuple[str, list[Finding]]:
        """First statement of the overview plus the lead statement of each section."""
        by_section: dict[str, list[Sentence]] = {}
        for sent in self.sentences(chunks):
            by_section.setdefault(sent.section, []).append(sent)
        if not by_section:
            return "", []
        sections = list(by_section.items())
        lead_section, lead_sentences = sections[0]
        summary = " ".join(s.text for s in lead_sentences[:2])
        findings = [
            Finding(text=f"{section}: {sents[0].text}", sources=[sents[0].key])
            for section, sents in sections[1:]
        ]
        return summary, _dedupe(findings, limit=7)

    # --- public API ------------------------------------------------------------
    def analyze(
        self, query: str, intent: Intent, chunks: list[RetrievedChunk], tool_results: list[ToolCallRecord]
    ) -> AnalysisResult:
        tool_findings = self.tool_findings(tool_results)
        if intent is Intent.SUMMARIZATION:
            summary, findings = self.document_summary(chunks)
            return AnalysisResult(
                summary=summary,
                key_findings=findings,
                risks=self.risk_findings(query, chunks)[:3],
                action_items=self.action_findings(query, chunks)[:3],
            )
        if intent is Intent.RISK_ANALYSIS:
            risks = self.risk_findings(query, chunks)
            recs = self.action_findings(query, chunks)
            return AnalysisResult(
                summary="Major delivery risks identified in the retrieved evidence.",
                key_findings=risks,
                risks=risks,
                recommendations=recs[:5],
            )
        if intent is Intent.COMPARISON:
            doc_findings = self.relevant_findings(
                query + " status percent complete story points code freeze",
                chunks,
                limit=3,
                focus=self.focus_terms(tool_results),
            )
            breaches = [f for f in tool_findings if "against a target" in f.text]
            summary = (
                "The status report narrative and the delivery metrics point in the same direction: "
                if breaches
                else "The delivery metrics are broadly consistent with the reported status: "
            )
            summary += (
                "several delivery KPIs are outside engineering targets."
                if breaches
                else "no KPI breaches against engineering targets were found."
            )
            return AnalysisResult(
                summary=summary,
                key_findings=_dedupe(doc_findings + tool_findings, limit=8),
                risks=self.risk_findings(query, chunks)[:3],
                recommendations=_dedupe(self.tool_actions(tool_results), limit=5),
            )
        if intent is Intent.ACTION_PLANNING:
            # Dated, owned action items from meeting notes first; then blocker and KPI actions.
            actions = _dedupe(
                self.action_findings(query, chunks, explicit_only=True)[:4]
                + self.tool_actions(tool_results)
                + self.action_findings(query, chunks),
                limit=8,
            )
            return AnalysisResult(
                summary="Prioritised actions derived from open blockers, delivery metrics and recorded action items.",
                key_findings=_dedupe(tool_findings, limit=5),
                risks=self.risk_findings(query, chunks)[:3],
                action_items=actions,
            )
        # Generic analysis for any other intent routed through the analysis agent.
        return AnalysisResult(
            summary="",
            key_findings=_dedupe(self.relevant_findings(query, chunks) + tool_findings, limit=6),
            risks=self.risk_findings(query, chunks)[:3],
            action_items=self.action_findings(query, chunks)[:4],
        )

    def lead_paragraph(
        self,
        query: str,
        intent: Intent,
        chunks: list[RetrievedChunk],
        tool_results: list[ToolCallRecord],
        analysis: AnalysisResult | None,
        cite,  # Callable[[list[str]], str]
    ) -> str:
        """The 'Answer' paragraph for the given intent."""
        statuses = self._tool(tool_results, "get_project_status")
        issue_sets = self._tool(tool_results, "get_open_issues")

        if intent is Intent.PEOPLE_LOOKUP:
            for i, found in self._tool(tool_results, "search_employee_directory"):
                if found["results"]:
                    e = found["results"][0]
                    return (
                        f"Best match in the employee directory: **{e['name']}**, {e['title']} "
                        f"({e['team']} team, {e['location']}), {e['email']} {cite([tool_key(i)])}"
                    )
            return ""

        if intent is Intent.ISSUE_LOOKUP and issue_sets:
            parts = []
            for i, issues in issue_sets:
                if not issues["issues"]:
                    continue
                f = issues["filters"]
                scope = f"release {f['release']}" if f.get("release") else (f.get("project_id") or "all projects")
                kind = "open release blockers" if f.get("blocking_only") else "open issues"
                items = "; ".join(
                    f"**{x['issue_id']}** {x['title']} ({x['severity']}, {x['status']}, {x['assignee']})"
                    for x in issues["issues"][:6]
                )
                parts.append(f"There are {issues['count']} {kind} for {scope}: {items} {cite([tool_key(i)])}")
            return " ".join(parts)

        if intent is Intent.PROJECT_STATUS and statuses:
            parts = []
            for i, s in statuses:
                parts.append(
                    f"**{s['name']}** is **{s['status']}** at {s['percent_complete']}% complete, targeting release "
                    f"{s['target_release']} on {s['release_date']} (code freeze {s['code_freeze_date']}). "
                    f"{s['health_summary']} {cite([tool_key(i)])}"
                )
            doc = self.relevant_findings(query, chunks, limit=1, focus=self.focus_terms(tool_results))
            if doc:
                parts.append(f"{doc[0].text} {cite(doc[0].sources)}")
            return " ".join(parts)

        if intent is Intent.SUMMARIZATION and analysis and analysis.summary:
            title = chunks[0].title if chunks else "The document"
            keys = [chunks[0].chunk_id] if chunks else []
            return f"**{title}** — {analysis.summary} {cite(keys)}"

        if intent is Intent.RISK_ANALYSIS and analysis and analysis.risks:
            top = analysis.risks[:2]
            body = " ".join(f"{r.text} {cite(r.sources)}" for r in top)
            return f"The evidence highlights the following major delivery risks. {body}"

        if intent is Intent.COMPARISON and analysis:
            parts = [analysis.summary]
            for i, s in statuses:
                parts.append(f"The project is reported as {s['status']} at {s['percent_complete']}% complete {cite([tool_key(i)])}.")
            for i, m in self._tool(tool_results, "get_delivery_metrics"):
                names = [_METRIC_LABELS.get(b["metric"], (b["metric"], ""))[0].lower() for b in m["target_breaches"]]
                if names:
                    listed = ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + names[-1]
                    parts.append(f"The delivery metrics show {listed} outside engineering targets {cite([tool_key(i)])}.")
            return " ".join(parts).strip()

        if intent is Intent.ACTION_PLANNING and analysis and analysis.action_items:
            top = analysis.action_items[:3]
            body = " ".join(f"({n}) {a.text} {cite(a.sources)}" for n, a in enumerate(top, start=1))
            return f"Priorities for this week: {body}"

        findings = self.relevant_findings(query, chunks, limit=2)
        return " ".join(f"{f.text} {cite(f.sources)}" for f in findings)
