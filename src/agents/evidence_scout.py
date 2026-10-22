"""Evidence Scout Agent.

Responsibilities:
- Receive a task assignment from the Lead Investigator.
- Autonomously execute grounded retrieval tools (search_archive, get_document_details,
  follow_references, inspect_timeline) in an iterative loop.
- After each retrieval round, use LLM to decide: continue searching or declare evidence
  sufficient and return.
- Return a structured EvidencePacket to the shared state.

The Scout makes one LLM call per search round (up to max_search_rounds).
Falls back to heuristics (follow references from top document) on timeout/unavailability.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from src.agents.investigation_state import InvestigationState, EvidencePacket, HandoffEntry
from src.llm_client import OllamaClient
from src.tools import ToolRegistry


class EvidenceScout:
    """Evidence Scout: autonomous iterative retrieval with LLM-directed continuation."""

    AGENT_NAME = "evidence_scout"

    def __init__(self, tools: ToolRegistry, llm: OllamaClient, llm_available: bool = True) -> None:
        self.tools = tools
        self.llm = llm
        self.llm_available = llm_available

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    def scout_node(self, state: InvestigationState) -> Dict[str, Any]:
        """Execute multi-round retrieval and return an EvidencePacket."""
        task = state.get("task_assignment", {})
        q = state["question"]
        handoff_log = list(state.get("handoff_log", []))

        max_rounds = task.get("max_search_rounds", 3)
        initial_keywords = task.get("initial_keywords", [q])
        # Collapse keyword list into a single search query
        initial_query = " ".join(initial_keywords) if initial_keywords else q

        packet = EvidencePacket()

        # ---- Round 1: initial keyword search ----
        self._search_round(packet, "search_archive", {"query": initial_query, "limit": 7})

        # ---- Subsequent rounds: LLM-directed ----
        for _ in range(1, max_rounds):
            should_continue, tool_name, tool_args = self._should_continue(q, packet)
            if not should_continue:
                break
            self._search_round(packet, tool_name, tool_args)

        handoff_log.append(
            vars(HandoffEntry(
                from_agent=self.AGENT_NAME,
                to_agent="precedence_auditor",
                summary=(
                    f"Evidence packet: {len(packet.passages)} passages from "
                    f"{len(packet.inspected_docs)} docs in {packet.search_rounds} rounds."
                ),
                payload_keys=["evidence_packet"],
            ))
        )

        return {
            "evidence_packet": asdict(packet),
            "scout_steps": [
                {"round": i + 1, "log": entry}
                for i, entry in enumerate(packet.retrieval_log)
            ],
            "handoff_log": handoff_log,
        }

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def _search_round(
        self, packet: EvidencePacket, tool_name: str, tool_args: Dict[str, Any]
    ) -> None:
        """Execute one tool call and accumulate results into the packet."""
        packet.search_rounds += 1

        if tool_name == "search_archive":
            query = tool_args.get("query", "")
            limit = tool_args.get("limit", 5)
            results = self.tools.search_archive(query=query, limit=limit)
            new = 0
            for r in results:
                if not any(p["passage_id"] == r["passage_id"] for p in packet.passages):
                    packet.passages.append(r)
                    new += 1
            packet.retrieval_log.append(
                f"search_archive('{query}', limit={limit}) → {len(results)} hits, {new} new passages."
            )

        elif tool_name == "follow_references":
            doc_id = tool_args.get("doc_id", "")
            ref_data = self.tools.follow_references(doc_id)
            refs = ref_data.get("explicit_outgoing_references", [])
            for ref_doc in refs:
                if ref_doc not in packet.inspected_docs:
                    packet.inspected_docs.append(ref_doc)
                    linked = self.tools.search_archive(query=ref_doc, limit=3)
                    for lr in linked:
                        if not any(p["passage_id"] == lr["passage_id"] for p in packet.passages):
                            packet.passages.append(lr)
            packet.retrieval_log.append(
                f"follow_references('{doc_id}') → linked to {refs}."
            )

        elif tool_name == "get_document_details":
            doc_id = tool_args.get("doc_id", "")
            doc_data = self.tools.get_document_details(doc_id)
            if "id" in doc_data and doc_id not in packet.inspected_docs:
                packet.inspected_docs.append(doc_id)
            packet.retrieval_log.append(
                f"get_document_details('{doc_id}') → status={doc_data.get('status')}."
            )

        elif tool_name == "inspect_timeline":
            timeline = self.tools.inspect_timeline()
            packet.retrieval_log.append(
                f"inspect_timeline() → {len(timeline)} records."
            )

    # ------------------------------------------------------------------
    # LLM-directed continuation decision
    # ------------------------------------------------------------------

    def _should_continue(
        self, question: str, packet: EvidencePacket
    ) -> tuple[bool, str, Dict[str, Any]]:
        """Ask the LLM whether to continue searching; returns (continue, tool, args)."""
        if self.llm_available:
            snippet = "\n".join([
                f"- [{p['passage_id']}] {p['document_id']}: {p['excerpt'][:100]}"
                for p in packet.passages[-5:]
            ])
            prompt = (
                f"You are an Evidence Scout investigating: '{question}'.\n"
                f"Retrieved so far: {len(packet.passages)} passages from "
                f"{len(set(p['document_id'] for p in packet.passages))} documents.\n"
                f"Last passages:\n{snippet}\n\n"
                "Decide whether you have sufficient evidence to answer or need more.\n"
                "Available tools: 'search_archive' (query, limit), "
                "'follow_references' (doc_id), 'get_document_details' (doc_id).\n"
                "Respond ONLY in JSON:\n"
                '{"continue": true/false, '
                '"tool_name": "tool_name_or_null", '
                '"tool_args": {"key": "value"}, '
                '"reasoning": "one sentence"}\n'
            )
            try:
                res = self.llm.generate_json(prompt)
                if isinstance(res, dict) and "continue" in res:
                    if res.get("continue") and res.get("tool_name"):
                        return True, res["tool_name"], res.get("tool_args", {})
                    return False, "", {}
            except (TimeoutError, Exception):
                pass  # fall through to heuristic

        # Heuristic fallback: after first round, follow references from top doc
        if packet.passages and packet.search_rounds == 1:
            top_doc = packet.passages[0]["document_id"]
            if top_doc not in packet.inspected_docs:
                return True, "follow_references", {"doc_id": top_doc}
        return False, "", {}
