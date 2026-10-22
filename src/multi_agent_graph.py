"""Multi-Agent Investigation Graph for Context Archaeologist.

Wires three genuine LLM-backed agents into a LangGraph StateGraph:

  Lead Investigator (assign) → Evidence Scout → Precedence Auditor → Lead Investigator (synthesize) → END

Each agent node is backed by a real LLM call to local Ollama, with deterministic
heuristic fallbacks for timeout/unavailability — no hardcoded answers.

Public API:
    MultiAgentArchaeologist.investigate(question) -> MultiAgentReport
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END

from src.agents.investigation_state import InvestigationState, HandoffEntry
from src.agents.lead_investigator import LeadInvestigator
from src.agents.evidence_scout import EvidenceScout
from src.agents.precedence_auditor import PrecedenceAuditor
from src.ingestion import DocumentArchive
from src.tools import ToolRegistry
from src.reasoner import ArchaeologyReasoner
from src.llm_client import OllamaClient


# ---------------------------------------------------------------------------
# Structured output report
# ---------------------------------------------------------------------------

@dataclass
class MultiAgentReport:
    """Complete investigation report from the multi-agent system."""
    question: str
    summary_answer: str
    is_abstained: bool
    abstention_reason: str
    citations: List[str]

    # Per-agent trace
    task_assignment: Dict[str, Any]
    evidence_packet: Dict[str, Any]
    audit_report: Dict[str, Any]
    validation_result: Dict[str, Any]

    # Handoff trace (drives UI panel)
    handoff_log: List[Dict[str, Any]]

    # Scout iteration steps
    scout_steps: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Multi-Agent Archaeologist
# ---------------------------------------------------------------------------

class MultiAgentArchaeologist:
    """Three-agent investigation system backed by local Ollama LLM.

    Parameters
    ----------
    dataset_dir : Path or str
        Path to the ``context_archaeologist_dataset`` directory.
    require_llm : bool
        If True (default), raise ConnectionError when Ollama is unreachable.
        Set False for offline testing — agents run all deterministic logic
        but skip LLM calls.
    """

    def __init__(
        self,
        dataset_dir: Path | str,
        require_llm: bool = True,
        use_llm: Optional[bool] = None,
    ) -> None:
        self.archive = DocumentArchive(dataset_dir)
        self.tools = ToolRegistry(self.archive)
        self.reasoner = ArchaeologyReasoner()

        self.llm = OllamaClient()
        self.llm_available = self.llm.is_available()

        # Support use_llm kwarg for test compatibility
        if use_llm is not None:
            if not use_llm:
                self.llm_available = False
            require_llm = use_llm

        if require_llm and not self.llm_available:
            raise ConnectionError(
                "Ollama is not running or the model is not available. "
                "Start Ollama with `ollama serve` and pull the model with "
                "`ollama pull llama3:latest`. Context Archaeologist requires "
                "a local LLM — it does not fall back to scripted answers."
            )

        # Instantiate the three agents, sharing the same LLM client
        self.lead = LeadInvestigator(self.llm, self.llm_available)
        self.scout = EvidenceScout(self.tools, self.llm, self.llm_available)
        self.auditor = PrecedenceAuditor(self.tools, self.reasoner, self.llm, self.llm_available)

        self.graph = self._build_graph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self):
        workflow = StateGraph(InvestigationState)

        # Register nodes — each is an agent's method
        workflow.add_node("lead_assign", self.lead.assign_node)
        workflow.add_node("evidence_scout", self.scout.scout_node)
        workflow.add_node("precedence_auditor", self.auditor.audit_node)
        workflow.add_node("lead_synthesize", self.lead.synthesize_node)

        # Wire the graph: Lead → Scout → Auditor → Lead (synthesis) → END
        workflow.set_entry_point("lead_assign")
        workflow.add_edge("lead_assign", "evidence_scout")
        workflow.add_edge("evidence_scout", "precedence_auditor")
        workflow.add_edge("precedence_auditor", "lead_synthesize")
        workflow.add_edge("lead_synthesize", END)

        return workflow.compile()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, question: str) -> Dict[str, Any]:
        """Execute the multi-agent investigation and return the raw state dict."""
        initial_state: InvestigationState = {
            "question": question,
            "intent": {},
            "task_assignment": {},
            "evidence_packet": {},
            "scout_steps": [],
            "audit_report": {},
            "citations": [],
            "validation_result": {},
            "final_answer": "",
            "is_abstained": False,
            "abstention_reason": "",
            "handoff_log": [],
            "error": None,
        }
        return self.graph.invoke(initial_state)

    def investigate(self, question: str) -> MultiAgentReport:
        """Execute investigation and return a structured MultiAgentReport."""
        result = self.run(question)
        return MultiAgentReport(
            question=result["question"],
            summary_answer=result.get("final_answer", ""),
            is_abstained=result.get("is_abstained", False),
            abstention_reason=result.get("abstention_reason", ""),
            citations=result.get("citations", []),
            task_assignment=result.get("task_assignment", {}),
            evidence_packet=result.get("evidence_packet", {}),
            audit_report=result.get("audit_report", {}),
            validation_result=result.get("validation_result", {}),
            handoff_log=result.get("handoff_log", []),
            scout_steps=result.get("scout_steps", []),
        )
