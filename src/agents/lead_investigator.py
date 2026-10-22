"""Lead Investigator Agent.

Responsibilities:
1. Classify the user's query intent via LLM.
2. Decompose the query into a concrete task assignment for the Evidence Scout.
3. After the Scout and Auditor complete their work, synthesize a final grounded
   answer from the assembled evidence and audit report — via LLM.

The Lead Investigator makes exactly two LLM calls per investigation:
  - Stage 1: Intent classification + task assignment
  - Stage 3: Final synthesis (after Scout and Auditor have reported back)

Both calls fall back to deterministic heuristics on timeout or LLM unavailability,
ensuring the investigation always produces a complete answer.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from src.agents.investigation_state import InvestigationState, HandoffEntry
from src.llm_client import OllamaClient


class LeadInvestigator:
    """Lead Investigator: intent classification, task delegation, final synthesis."""

    AGENT_NAME = "lead_investigator"

    def __init__(self, llm: OllamaClient, llm_available: bool = True) -> None:
        self.llm = llm
        self.llm_available = llm_available

    # ------------------------------------------------------------------
    # Node 1 — Intent classification + task assignment (entry point)
    # ------------------------------------------------------------------

    def assign_node(self, state: InvestigationState) -> Dict[str, Any]:
        """Classify intent and produce a structured task assignment for the Scout."""
        q = state["question"]
        handoff_log = list(state.get("handoff_log", []))

        intent, task_assignment = self._classify_and_plan(q)

        handoff_log.append(
            vars(HandoffEntry(
                from_agent=self.AGENT_NAME,
                to_agent="evidence_scout",
                summary=f"Assigned search task: {task_assignment.get('strategy', 'keyword search')}",
                payload_keys=["task_assignment", "intent"],
            ))
        )

        return {
            "intent": intent,
            "task_assignment": task_assignment,
            "handoff_log": handoff_log,
        }

    def _classify_and_plan(self, question: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """LLM-backed intent classification + search planning. Falls back to heuristic."""
        if self.llm_available:
            prompt = (
                "You are the Lead Investigator on a corporate archive investigation team.\n"
                f"User question: '{question}'\n\n"
                "Your job is to:\n"
                "1. Classify the question type.\n"
                "2. Define a concrete search strategy for the Evidence Scout.\n\n"
                "Respond ONLY with a JSON object:\n"
                '{"intent_type": "factual_lookup|timeline_reconstruction|gap_analysis|'
                'contradiction_check|status_assessment", '
                '"key_entities": ["list"], '
                '"requires_cross_document": true/false, '
                '"complexity": "simple|moderate|complex", '
                '"search_strategy": "one-sentence description of what to search for", '
                '"initial_keywords": ["keyword1", "keyword2"], '
                '"expected_doc_hints": ["DOC-XXX or topic hint"]}\n'
            )
            try:
                res = self.llm.generate_json(prompt)
                if isinstance(res, dict) and "intent_type" in res and "initial_keywords" in res:
                    intent = {
                        "intent_type": res.get("intent_type", "factual_lookup"),
                        "key_entities": res.get("key_entities", []),
                        "requires_cross_document": res.get("requires_cross_document", False),
                        "complexity": res.get("complexity", "moderate"),
                    }
                    task_assignment = {
                        "question": question,
                        "strategy": res.get("search_strategy", question),
                        "initial_keywords": res.get("initial_keywords", [question]),
                        "expected_doc_hints": res.get("expected_doc_hints", []),
                        "max_search_rounds": 4 if res.get("requires_cross_document") else 3,
                    }
                    return intent, task_assignment
            except (TimeoutError, Exception):
                pass  # fall through to heuristic

        return self._heuristic_plan(question)

    def _heuristic_plan(self, question: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Deterministic fallback for when Ollama is unavailable or times out."""
        q_lower = question.lower()
        intent_type = "factual_lookup"
        if any(w in q_lower for w in ["reconstruct", "timeline", "chronolog", "order", "history"]):
            intent_type = "timeline_reconstruction"
        elif any(w in q_lower for w in ["prevent", "gate", "missing", "block", "incomplete"]):
            intent_type = "gap_analysis"
        elif any(w in q_lower for w in ["contradict", "conflict", "disagree", "versus"]):
            intent_type = "contradiction_check"
        elif any(w in q_lower for w in ["status", "ready", "approved", "complete"]):
            intent_type = "status_assessment"

        cross_doc = any(w in q_lower for w in ["gate", "all", "across", "reconstruct"])
        intent = {
            "intent_type": intent_type,
            "key_entities": [],
            "requires_cross_document": cross_doc,
            "complexity": "complex" if len(question.split()) > 15 else "moderate",
        }
        task_assignment = {
            "question": question,
            "strategy": f"Keyword search for '{question}', then follow document references.",
            "initial_keywords": [question],
            "expected_doc_hints": [],
            "max_search_rounds": 4 if cross_doc else 3,
        }
        return intent, task_assignment

    # ------------------------------------------------------------------
    # Node 2 — Final synthesis (after Scout + Auditor)
    # ------------------------------------------------------------------

    def synthesize_node(self, state: InvestigationState) -> Dict[str, Any]:
        """Synthesize the final answer from Scout evidence and Auditor report."""
        q = state["question"]
        evidence = state.get("evidence_packet", {})
        audit = state.get("audit_report", {})
        handoff_log = list(state.get("handoff_log", []))

        passages = evidence.get("passages", [])
        contradictions = audit.get("contradictions", [])
        unresolved_gaps = audit.get("unresolved_gaps", [])
        abstention_required = audit.get("abstention_required", False)
        abstention_reason = audit.get("abstention_reason", "")
        audit_reasoning = audit.get("audit_reasoning", "")

        # Collect citations
        cited = sorted(set(p["passage_id"] for p in passages[:8]))

        if self.llm_available and not abstention_required:
            final_answer = self._llm_synthesize(
                q, passages, contradictions, unresolved_gaps, audit_reasoning
            )
        else:
            final_answer = self._heuristic_synthesize(
                q, passages, contradictions, abstention_required, abstention_reason
            )

        handoff_log.append(
            vars(HandoffEntry(
                from_agent=self.AGENT_NAME,
                to_agent="output",
                summary=f"Final answer synthesized from {len(passages)} passages ({len(contradictions)} contradictions resolved).",
                payload_keys=["final_answer", "citations"],
            ))
        )

        return {
            "final_answer": final_answer,
            "is_abstained": abstention_required,
            "abstention_reason": abstention_reason,
            "citations": cited,
            "handoff_log": handoff_log,
        }

    def _llm_synthesize(
        self,
        question: str,
        passages: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        unresolved_gaps: List[str],
        audit_reasoning: str,
    ) -> str:
        """LLM-driven synthesis from grounded evidence."""
        context_blocks = "\n".join([
            f"[{p['passage_id']}] ({p.get('filename','?')}, "
            f"status={p.get('status','?')}, created={p.get('created','?')}): {p['excerpt']}"
            for p in passages[:8]
        ])
        contra_summary = "\n".join([
            f"- Contradiction ({c['topic']}): {c['resolution']}"
            for c in contradictions
        ])
        gap_summary = "\n".join(f"- {g}" for g in unresolved_gaps) if unresolved_gaps else "None identified."
        prompt = (
            "You are the Lead Investigator at a workplace context investigation firm.\n"
            f"Question: {question}\n\n"
            f"Retrieved Evidence:\n{context_blocks}\n\n"
            f"Resolved Contradictions:\n{contra_summary if contra_summary else 'None.'}\n\n"
            f"Auditor Reasoning:\n{audit_reasoning}\n\n"
            f"Unresolved Gaps:\n{gap_summary}\n\n"
            "Instructions:\n"
            "1. Answer the question thoroughly based ONLY on the evidence provided.\n"
            "2. Cite specific passage IDs (e.g. DOC-001-P04) for all factual assertions.\n"
            "3. Note temporal precedence where relevant (later authoritative decision > earlier baseline).\n"
            "4. If evidence is missing, state what is missing without guessing.\n"
            "5. Do NOT invent facts. Only state what the evidence supports.\n"
        )
        try:
            return self.llm.generate(prompt=prompt)
        except (TimeoutError, Exception):
            return self._heuristic_synthesize(question, passages, contradictions, False, "")

    def _heuristic_synthesize(
        self,
        question: str,
        passages: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        is_abstained: bool,
        abstention_reason: str,
    ) -> str:
        """Deterministic evidence-based answer builder (no LLM)."""
        if is_abstained:
            parts = [
                "**Insufficient Evidence — Abstention Required**\n\n"
                f"{abstention_reason}\n\n"
                "**Supporting evidence reviewed:**"
            ]
            for p in passages[:4]:
                excerpt = p["excerpt"].strip().replace("\n", " ")[:200]
                parts.append(f"- [{p['passage_id']}] {p.get('title', p['document_id'])}: {excerpt}")
            return "\n".join(parts)

        doc_groups: Dict[str, List] = {}
        for p in passages:
            doc_groups.setdefault(p["document_id"], []).append(p)

        parts = [
            "**Investigation Findings:**\n",
            f"Based on {len(passages)} passages across {len(doc_groups)} documents:\n",
        ]
        for p in passages[:6]:
            excerpt = p["excerpt"].strip().replace("\n", " ")[:250]
            status_tag = (
                f" (status: {p.get('status')}, authority: {p.get('authority')})"
                if p.get("status") else ""
            )
            parts.append(
                f"- **[{p['passage_id']}] {p.get('title', p['document_id'])}**{status_tag}: {excerpt}"
            )

        if contradictions:
            parts.append(f"\n**Contradiction Analysis ({len(contradictions)} conflicts):**\n")
            for c in contradictions:
                parts.append(f"- **{c['topic']}:** {c['resolution']}")

        cited = sorted(set(p["passage_id"] for p in passages[:6]))
        parts.append(f"\n**Citations:** {', '.join(cited)}")
        return "\n".join(parts)
