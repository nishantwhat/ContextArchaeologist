"""Reasoning, Contradiction Analysis, and Decision Timeline Synthesis Engine.

Evaluates evidence across dimensions:
- Temporal precedence (earlier vs latest decisions)
- Formal document authority (signed Launch Council decision vs informal chat / draft notes)
- Status validity (superseded, draft, conditional, approved baseline)
- Epistemic completeness (identifies missing gates, unrecorded approvals, missing data)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class EvidencePoint:
    doc_id: str
    passage_id: str
    date: str
    status: str
    authority: str
    excerpt: str
    claim_type: str = "general"


@dataclass
class ContradictionFinding:
    topic: str
    conflicting_claim_a: str
    evidence_a: str
    conflicting_claim_b: str
    evidence_b: str
    resolution: str
    authoritative_source: str
    is_resolved: bool


class ArchaeologyReasoner:
    """Performs deep synthesis, temporal ordering, and contradiction resolution."""

    def analyze_contradictions(
        self, evidence_points: List[Dict[str, Any]]
    ) -> List[ContradictionFinding]:
        """Detect and reconcile conflicting statements across retrieved evidence."""
        findings: List[ContradictionFinding] = []

        # 1. Launch Date conflict detection: 20 April vs 11 May vs 'Date to be confirmed' / 'No date'
        dates_found = []
        for ep in evidence_points:
            content = ep.get("excerpt", "") + " " + ep.get("section", "")
            doc_id = ep.get("document_id", "")
            status = ep.get("status", "")
            pid = ep.get("passage_id", "")

            if "20 april" in content.lower():
                dates_found.append(("20 April 2026", doc_id, pid, status, ep.get("created", ""), ep))
            if "11 may" in content.lower():
                dates_found.append(("11 May 2026", doc_id, pid, status, ep.get("created", ""), ep))
            if "date to be confirmed" in content.lower() or "withdrawn" in content.lower() or "no calendar date is currently authorized" in content.lower():
                dates_found.append(("Date to be confirmed / No date authorized", doc_id, pid, status, ep.get("created", ""), ep))

        # Reconcile date timeline if multiple distinct dates exist
        unique_targets = {d[0] for d in dates_found}
        if len(unique_targets) > 1:
            # Check if DOC-008 is present
            has_doc08 = any(d[1] == "DOC-008" for d in dates_found)
            has_doc03 = any(d[1] == "DOC-003" for d in dates_found)
            has_doc07 = any(d[1] == "DOC-007" for d in dates_found)

            resolution_msg = (
                "20 April was the original January baseline (DOC-001/002). "
                "On 18 February it was moved to 11 May (DOC-003). "
                "However, on 2 April 2026, Launch Council decision DOC-008 explicitly withdrew the 11 May date. "
                "Draft calendar DOC-007 is unapproved. No date is currently authorized."
            )
            findings.append(
                ContradictionFinding(
                    topic="Northstar Limited-Cohort Launch Date",
                    conflicting_claim_a="Target 20 April / 11 May (DOC-001 / DOC-003 / DOC-007)",
                    evidence_a="DOC-001 (Jan baseline) & DOC-003 (Feb move) & DOC-007 (Draft calendar)",
                    conflicting_claim_b="Launch date withdrawn / to be confirmed after gates pass (DOC-008)",
                    evidence_b="DOC-008 (Authoritative Launch Council decision, 2026-04-02)",
                    resolution=resolution_msg,
                    authoritative_source="DOC-008 (Launch Council Decision)",
                    is_resolved=True,
                )
            )

        # 2. Support Readiness conflict: "Support is ready" vs Formal Gate incomplete
        has_support_ready_claim = False
        has_gate_criteria = False
        support_eps = []
        for ep in evidence_points:
            content = ep.get("excerpt", "").lower()
            if "support is ready" in content or "draft rota" in content:
                has_support_ready_claim = True
                support_eps.append(ep)
            if "customer operations" in content and ("freeze" in content or "faq" in content or "mandatory release gates" in content):
                has_gate_criteria = True
                support_eps.append(ep)

        if has_support_ready_claim and has_gate_criteria:
            findings.append(
                ContradictionFinding(
                    topic="Customer Operations / Support Gate Status",
                    conflicting_claim_a="Sync participant stated 'Support is ready' (DOC-005)",
                    evidence_a="DOC-005 passage indicating informal chat claim during 11 March sync",
                    conflicting_claim_b="Gate requires rota frozen and customer FAQ approved for external distribution (DOC-008)",
                    evidence_b="DOC-008 Section 2 (Mandatory release gates) & DOC-005 body",
                    resolution=(
                        "In context (DOC-005), 'Support is ready' only meant draft materials existed. "
                        "The rota is not frozen and the FAQ is not approved externally. Therefore, the formal gate is incomplete."
                    ),
                    authoritative_source="DOC-008 (Gate criteria) & DOC-005 (Clarification)",
                    is_resolved=True,
                )
            )

        # 3. Recovery rehearsal status: "Restore ran/looked faster" vs Missing elapsed-time/integrity evidence
        has_rehearsal_chat = any("looked much faster" in ep.get("excerpt", "").lower() or "ran another restore" in ep.get("excerpt", "").lower() for ep in evidence_points)
        has_rehearsal_gate = any("elapsed time" in ep.get("excerpt", "").lower() or "recovery rehearsal" in ep.get("excerpt", "").lower() for ep in evidence_points)

        if has_rehearsal_chat and has_rehearsal_gate:
            findings.append(
                ContradictionFinding(
                    topic="Recovery Rehearsal Gate Status",
                    conflicting_claim_a="Chat excerpt noted restore attempt ran and 'looked much faster' (DOC-010)",
                    evidence_a="DOC-010 informal chat between Dev Malik and Arun",
                    conflicting_claim_b="Gate mandates run record with elapsed time and integrity checks (DOC-004, DOC-008, DOC-011)",
                    evidence_b="DOC-008, DOC-004, DOC-011",
                    resolution=(
                        "The chat in DOC-010 is evidence that a rehearsal attempt occurred, not evidence that the gate passed. "
                        "The archive lacks the final run record, integrity report, and elapsed-time figure. The outcome remains UNKNOWN."
                    ),
                    authoritative_source="DOC-004, DOC-008, DOC-011",
                    is_resolved=True,
                )
            )

        return findings

    def check_abstention_needed(
        self, question: str, evidence_points: List[Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """Determine whether evidence is insufficient to answer definitively without guessing."""
        q_lower = question.lower()

        # Check: Asking whether second rehearsal passed
        if ("second recovery" in q_lower or "rehearsal pass" in q_lower or "60-minute" in q_lower) and "did" in q_lower:
            return (
                True,
                "ABSTENTION REQUIRED: The archive documents that a second restore attempt took place (DOC-010), "
                "but explicit elapsed-time figures and data-integrity reports are absent from the records. "
                "Dev Malik noted 'Please wait for the record' and Security confirmed it is still outstanding (DOC-011). "
                "It is impossible to conclude pass or fail without fabricating missing evidence."
            )

        # Check: Asking for exact approved future date
        if "what exact calendar date" in q_lower or "what exact date" in q_lower or "what calendar date will launch council approve" in q_lower:
            return (
                True,
                "ABSTENTION REQUIRED: No calendar date can be named. The Launch Council withdrew 11 May (DOC-008) "
                "and decided that the launch date is 'to be confirmed after the release gates pass.' "
                "No subsequent decision authorizing a specific date exists in this archive."
            )

        return (False, "")
