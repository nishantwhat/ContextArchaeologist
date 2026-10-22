"""Precedence Auditor Agent.

Responsibilities:
- Receive the EvidencePacket from the Evidence Scout.
- Run deterministic contradiction analysis via ArchaeologyReasoner.
- Use LLM to interpret the contradictions, rank evidence by temporal authority,
  and identify unresolved gaps.
- Determine whether epistemic abstention is required.
- Return a structured AuditReport and validated citations.

The Auditor makes exactly one LLM call per investigation (the interpretation step).
The core contradiction analysis and validation are always deterministic (no LLM).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List

from src.agents.investigation_state import InvestigationState, AuditReport, HandoffEntry
from src.llm_client import OllamaClient
from src.reasoner import ArchaeologyReasoner
from src.tools import ToolRegistry


class PrecedenceAuditor:
    """Precedence Auditor: deterministic contradiction analysis + LLM interpretation."""

    AGENT_NAME = "precedence_auditor"

    def __init__(
        self,
        tools: ToolRegistry,
        reasoner: ArchaeologyReasoner,
        llm: OllamaClient,
        llm_available: bool = True,
    ) -> None:
        self.tools = tools
        self.reasoner = reasoner
        self.llm = llm
        self.llm_available = llm_available

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    def audit_node(self, state: InvestigationState) -> Dict[str, Any]:
        """Run contradiction analysis, LLM interpretation, abstention check."""
        q = state["question"]
        evidence = state.get("evidence_packet", {})
        handoff_log = list(state.get("handoff_log", []))

        passages = evidence.get("passages", [])

        # ---- Step 1: Deterministic contradiction analysis ----
        contra_objs = self.reasoner.analyze_contradictions(passages)
        contra_dicts = [
            {
                "topic": c.topic,
                "conflicting_claim_a": c.conflicting_claim_a,
                "evidence_a": c.evidence_a,
                "conflicting_claim_b": c.conflicting_claim_b,
                "evidence_b": c.evidence_b,
                "resolution": c.resolution,
                "authoritative_source": c.authoritative_source,
            }
            for c in contra_objs
        ]

        # ---- Step 2: Deterministic abstention check ----
        needs_abstention, abstention_reason = self.reasoner.check_abstention_needed(q, passages)

        # ---- Step 3: Citation validation ----
        all_ids = list(set(
            [p["passage_id"] for p in passages] + [p["document_id"] for p in passages]
        ))
        val_result = self.tools.validate_citations(all_ids)
        valid_citations = sorted(val_result.get("valid_citations", []))

        # ---- Step 4: Identify unresolved gaps from contradiction resolutions ----
        unresolved_gaps = [
            f"{c['topic']}: {c['resolution']}"
            for c in contra_dicts
            if any(
                w in c.get("resolution", "").lower()
                for w in ["missing", "absent", "unknown", "lacks", "unresolved"]
            )
        ]

        # ---- Step 5: LLM interpretation of contradictions + passage ranking ----
        audit_reasoning = self._llm_interpret(
            q, passages, contra_dicts, unresolved_gaps
        )

        # ---- Step 6: Rank passages by authority (deterministic) ----
        ranked = self._rank_by_authority(passages)

        report = AuditReport(
            contradictions=contra_dicts,
            unresolved_gaps=unresolved_gaps,
            ranked_passages=ranked,
            abstention_required=needs_abstention,
            abstention_reason=abstention_reason,
            audit_reasoning=audit_reasoning,
        )

        handoff_log.append(
            vars(HandoffEntry(
                from_agent=self.AGENT_NAME,
                to_agent="lead_investigator",
                summary=(
                    f"Audit complete: {len(contra_dicts)} contradictions, "
                    f"{len(unresolved_gaps)} gaps. "
                    f"Abstention: {needs_abstention}."
                ),
                payload_keys=["audit_report", "citations", "validation_result"],
            ))
        )

        return {
            "audit_report": asdict(report),
            "citations": valid_citations,
            "validation_result": val_result,
            "handoff_log": handoff_log,
        }

    # ------------------------------------------------------------------
    # LLM interpretation
    # ------------------------------------------------------------------

    def _llm_interpret(
        self,
        question: str,
        passages: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        gaps: List[str],
    ) -> str:
        """Ask LLM to interpret contradiction findings and rank their significance."""
        if not self.llm_available:
            return self._heuristic_interpret(contradictions, gaps)

        contra_text = "\n".join(
            f"- [{c['topic']}]: A='{c['conflicting_claim_a']}' (src: {c['evidence_a']}) "
            f"vs B='{c['conflicting_claim_b']}' (src: {c['evidence_b']}). "
            f"Resolution: {c['resolution']}. Authority: {c['authoritative_source']}."
            for c in contradictions
        ) or "No contradictions found."

        snippet = "\n".join(
            f"- [{p['passage_id']}] {p['document_id']} (created={p.get('created','?')}, "
            f"status={p.get('status','?')}): {p['excerpt'][:100]}"
            for p in passages[:6]
        )

        prompt = (
            "You are the Precedence Auditor on an investigation team.\n"
            f"Question under investigation: '{question}'\n\n"
            f"Evidence passages (first 6):\n{snippet}\n\n"
            f"Detected contradictions:\n{contra_text}\n\n"
            "Your job:\n"
            "1. Explain which contradictions are most material to answering the question.\n"
            "2. Identify the most authoritative passage(s) based on document date and type.\n"
            "3. Note any unresolved gaps or missing evidence that should be flagged.\n"
            "Respond in 2–4 sentences of plain English, no JSON.\n"
        )
        try:
            return self.llm.generate(prompt=prompt)
        except (TimeoutError, Exception):
            return self._heuristic_interpret(contradictions, gaps)

    def _heuristic_interpret(
        self, contradictions: List[Dict[str, Any]], gaps: List[str]
    ) -> str:
        """Deterministic interpretation fallback."""
        if not contradictions:
            return "No contradictions detected in the retrieved evidence."
        parts = [f"{len(contradictions)} contradiction(s) identified:"]
        for c in contradictions:
            parts.append(f"  • {c['topic']}: {c['resolution']}")
        if gaps:
            parts.append(f"Unresolved gaps: {'; '.join(gaps[:3])}")
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Authority ranking (deterministic)
    # ------------------------------------------------------------------

    def _rank_by_authority(self, passages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank passages: authoritative decisions > drafts > meeting notes, newest first."""
        authority_order = {
            "authoritative_current_decision": 0,
            "high_for_decision_history": 1,
            "high_for_scope_low_for_later_operational_changes": 2,
            "medium_for_attendance_and_discussion": 3,
            "draft_not_approved": 4,
        }

        def sort_key(p: Dict[str, Any]) -> tuple:
            auth = p.get("authority", "")
            rank = next(
                (v for k, v in authority_order.items() if k in auth.lower()),
                5
            )
            created = p.get("created", "9999-12-31")
            return (rank, [-ord(c) for c in created])  # lower rank first, newer date first

        return sorted(passages, key=lambda p: (
            next(
                (v for k, v in authority_order.items() if k in p.get("authority", "").lower()),
                5
            ),
            p.get("created", "9999-12-31"),
        ))
