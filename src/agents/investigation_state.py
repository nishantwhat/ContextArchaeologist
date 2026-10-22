"""Shared investigation state for the multi-agent Context Archaeologist system.

This TypedDict is the single shared message-passing contract between:
  - Lead Investigator  (intent classification + synthesis)
  - Evidence Scout     (autonomous tool-driven retrieval)
  - Precedence Auditor (contradiction resolution + gap analysis)

All agents read from and write to this state through the LangGraph StateGraph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict


# ---------------------------------------------------------------------------
# Evidence packet produced by Evidence Scout
# ---------------------------------------------------------------------------

@dataclass
class EvidencePacket:
    """Structured collection of evidence returned by the Evidence Scout."""
    passages: List[Dict[str, Any]] = field(default_factory=list)
    inspected_docs: List[str] = field(default_factory=list)
    search_rounds: int = 0
    retrieval_log: List[str] = field(default_factory=list)  # human-readable trace


# ---------------------------------------------------------------------------
# Audit report produced by Precedence Auditor
# ---------------------------------------------------------------------------

@dataclass
class AuditReport:
    """Structured analysis returned by the Precedence Auditor."""
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_gaps: List[str] = field(default_factory=list)
    ranked_passages: List[Dict[str, Any]] = field(default_factory=list)
    abstention_required: bool = False
    abstention_reason: str = ""
    audit_reasoning: str = ""   # LLM interpretation of the contradiction analysis


# ---------------------------------------------------------------------------
# Handoff log entry (drives UI agent trace panel)
# ---------------------------------------------------------------------------

@dataclass
class HandoffEntry:
    """Single event in the inter-agent handoff log."""
    from_agent: str   # "lead_investigator" | "evidence_scout" | "precedence_auditor"
    to_agent: str
    summary: str      # one-line description of what was handed off
    payload_keys: List[str] = field(default_factory=list)  # state keys transferred


# ---------------------------------------------------------------------------
# Full shared state (LangGraph TypedDict)
# ---------------------------------------------------------------------------

class InvestigationState(TypedDict):
    # ---- Input ----
    question: str

    # ---- Lead Investigator outputs (stage 1) ----
    intent: Dict[str, Any]          # classified intent from LLM
    task_assignment: Dict[str, Any] # instructions passed to Evidence Scout

    # ---- Evidence Scout outputs ----
    evidence_packet: Dict[str, Any]          # serialized EvidencePacket
    scout_steps: List[Dict[str, Any]]        # per-iteration tool call traces

    # ---- Precedence Auditor outputs ----
    audit_report: Dict[str, Any]            # serialized AuditReport
    citations: List[str]
    validation_result: Dict[str, Any]

    # ---- Lead Investigator final synthesis ----
    final_answer: str
    is_abstained: bool
    abstention_reason: str

    # ---- Cross-cutting ----
    handoff_log: List[Dict[str, Any]]        # serialized HandoffEntry list
    error: Optional[str]                     # propagated error (if any)
