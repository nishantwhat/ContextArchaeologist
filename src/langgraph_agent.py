"""LangGraph-driven Autonomous Investigation Agent for Context Archaeologist.

Stateful investigation loop with:
- Plan formulation node
- Autonomous tool-calling node (chooses search, details, follow_references, inspect_timeline)
- Intermediate evidence evaluator node (checks sufficiency and detects contradictions)
- Conditional edge: routes back to tool caller if evidence is missing, or proceeds to synthesis
- Epistemic abstention & Grounded synthesis node
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from src.ingestion import DocumentArchive
from src.tools import ToolRegistry
from src.reasoner import ArchaeologyReasoner, ContradictionFinding
from src.llm_client import OllamaClient


class AgentState(TypedDict):
    question: str
    iteration: int
    max_iterations: int
    plan: str
    next_action: str
    tool_name: Optional[str]
    tool_args: Dict[str, Any]
    retrieved_passages: List[Dict[str, Any]]
    inspected_docs: List[str]
    contradictions: List[Dict[str, Any]]
    is_abstained: bool
    abstention_reason: str
    final_answer: str
    steps: List[Dict[str, Any]]
    citations: List[str]


class LangGraphArchaeologist:
    def __init__(self, dataset_dir: Path | str, use_llm: bool = True):
        self.archive = DocumentArchive(dataset_dir)
        self.tools = ToolRegistry(self.archive)
        self.reasoner = ArchaeologyReasoner()
        self.llm = OllamaClient()
        self.use_llm = use_llm and self.llm.is_available()
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("planner_node", self.planner_node)
        workflow.add_node("tool_executor_node", self.tool_executor_node)
        workflow.add_node("evaluator_node", self.evaluator_node)
        workflow.add_node("synthesis_node", self.synthesis_node)

        workflow.set_entry_point("planner_node")
        workflow.add_edge("planner_node", "tool_executor_node")
        workflow.add_edge("tool_executor_node", "evaluator_node")

        # Conditional routing based on evaluator decision
        workflow.add_conditional_edges(
            "evaluator_node",
            self.route_next_step,
            {
                "continue_search": "tool_executor_node",
                "synthesize": "synthesis_node",
            },
        )
        workflow.add_edge("synthesis_node", END)

        return workflow.compile()

    def planner_node(self, state: AgentState) -> Dict[str, Any]:
        q = state["question"]
        initial_search_query = q

        if self.use_llm:
            prompt = (
                f"You are a Senior Context Archaeologist investigating a corporate archive.\n"
                f"User Question: '{q}'\n\n"
                f"Formulate a search plan. Respond with a JSON object:\n"
                f'{{"plan": "description of search strategy", "initial_search_query": "targeted search keywords"}}\n'
            )
            res = self.llm.generate_json(prompt)
            plan = res.get("plan", f"Investigate corporate archive for '{q}'")
            initial_search_query = res.get("initial_search_query", q)
        else:
            plan = f"Initial inquiry plan: locate primary sources and governing decisions for '{q}'"

        step = {
            "stage": "Plan Formulation",
            "tool_name": "planner",
            "input_args": {"question": q},
            "output_summary": plan,
        }
        return {
            "plan": plan,
            "next_action": "search",
            "tool_name": "search_archive",
            "tool_args": {"query": initial_search_query, "limit": 5},
            "steps": state.get("steps", []) + [step],
            "iteration": 0,
            "max_iterations": 3,
        }

    def tool_executor_node(self, state: AgentState) -> Dict[str, Any]:
        tool_name = state.get("tool_name")
        tool_args = state.get("tool_args", {})
        iteration = state.get("iteration", 0) + 1
        steps = list(state.get("steps", []))
        passages = list(state.get("retrieved_passages", []))
        inspected = list(state.get("inspected_docs", []))

        output_summary = ""

        if tool_name == "search_archive":
            query = tool_args.get("query", state["question"])
            limit = tool_args.get("limit", 5)
            results = self.tools.search_archive(query=query, limit=limit)
            for r in results:
                if not any(p["passage_id"] == r["passage_id"] for p in passages):
                    passages.append(r)
            output_summary = f"Executed search_archive('{query}'): retrieved {len(results)} passages."

        elif tool_name == "get_document_details":
            doc_id = tool_args.get("doc_id", "")
            doc_data = self.tools.get_document_details(doc_id)
            if "id" in doc_data and doc_id not in inspected:
                inspected.append(doc_id)
            output_summary = f"Executed get_document_details('{doc_id}'): status={doc_data.get('status')}, authority={doc_data.get('authority')}."

        elif tool_name == "follow_references":
            doc_id = tool_args.get("doc_id", "")
            ref_data = self.tools.follow_references(doc_id)
            refs = ref_data.get("explicit_outgoing_references", [])
            output_summary = f"Executed follow_references('{doc_id}'): discovered linked records {refs}."
            # Automatically fetch details or passages for discovered links if not yet visited
            for ref_doc in refs:
                if ref_doc not in inspected:
                    doc_details = self.tools.get_document_details(ref_doc)
                    inspected.append(ref_doc)
                    # Also retrieve top passages from linked doc
                    linked_res = self.tools.search_archive(query=ref_doc, limit=3)
                    for lr in linked_res:
                        if not any(p["passage_id"] == lr["passage_id"] for p in passages):
                            passages.append(lr)

        elif tool_name == "inspect_timeline":
            timeline = self.tools.inspect_timeline()
            output_summary = f"Executed inspect_timeline(): retrieved chronological overview of {len(timeline)} records."

        steps.append(
            {
                "stage": f"Investigation Loop {iteration}",
                "tool_name": tool_name,
                "input_args": tool_args,
                "output_summary": output_summary,
            }
        )

        return {
            "iteration": iteration,
            "retrieved_passages": passages,
            "inspected_docs": inspected,
            "steps": steps,
        }

    def evaluator_node(self, state: AgentState) -> Dict[str, Any]:
        """Evaluates whether current evidence is sufficient or if another tool call is needed."""
        passages = state.get("retrieved_passages", [])
        q = state["question"]
        q_lower = q.lower()
        iteration = state.get("iteration", 1)
        max_iter = state.get("max_iterations", 3)
        steps = list(state.get("steps", []))

        # Check for contradictions
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

        # Stop if max iterations reached
        if iteration >= max_iter:
            return {
                "next_action": "synthesize",
                "contradictions": contra_dicts,
            }

        # Model-directed decision on next action
        if self.use_llm:
            passage_snippets = "\n".join([f"- [{p['passage_id']}] {p['document_id']}: {p['section']} - {p['excerpt'][:120]}" for p in passages[-4:]])
            prompt = (
                f"You are investigating: '{q}'.\n"
                f"Current Evidence Passages:\n{passage_snippets}\n\n"
                f"Determine if more evidence is needed from other records, or if we have enough evidence to answer.\n"
                f"Tools available: 'search_archive' (query, limit), 'follow_references' (doc_id), 'get_document_details' (doc_id), 'synthesize'.\n"
                f"Respond in JSON format:\n"
                f'{{"next_action": "continue_search" or "synthesize", "tool_name": "tool_name", "tool_args": {{"query": "..."}}}}\n'
            )
            res = self.llm.generate_json(prompt)
            next_action = res.get("next_action", "synthesize")
            tool_name = res.get("tool_name", "search_archive")
            tool_args = res.get("tool_args", {})
        else:
            # Deterministic heuristic routing for regression
            next_action = "synthesize"
            tool_name = None
            tool_args = {}

            # If question asks about gates/missing evidence and we haven't retrieved recovery/security status
            if ("gate" in q_lower or "prevent" in q_lower or "security" in q_lower or "recovery" in q_lower) and iteration == 1:
                next_action = "continue_search"
                tool_name = "search_archive"
                tool_args = {"query": "recovery rehearsal elapsed time integrity access export", "limit": 4}
            elif ("launch" in q_lower or "date" in q_lower or "calendar" in q_lower) and not any("DOC-008" in p["document_id"] for p in passages) and iteration == 1:
                next_action = "continue_search"
                tool_name = "search_archive"
                tool_args = {"query": "launch council release gate decision date withdrawn", "limit": 4}

        return {
            "next_action": next_action,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "contradictions": contra_dicts,
        }

    def route_next_step(self, state: AgentState) -> str:
        if state.get("next_action") == "continue_search" and state.get("iteration", 0) < state.get("max_iterations", 3):
            return "continue_search"
        return "synthesize"

    def synthesis_node(self, state: AgentState) -> Dict[str, Any]:
        q = state["question"]
        passages = state.get("retrieved_passages", [])
        contra_data = state.get("contradictions", [])

        # Validate citations
        all_pids = [p["passage_id"] for p in passages]
        all_dids = [p["document_id"] for p in passages]
        citation_check = self.tools.validate_citations(list(set(all_pids + all_dids)))

        # Epistemic check
        is_abstained, abstention_reason = self.reasoner.check_abstention_needed(q, passages)

        # Synthesize answer
        if self.use_llm and not is_abstained:
            context_blocks = "\n".join([f"[{p['passage_id']}] ({p['filename']}, {p.get('status')}, {p.get('created')}): {p['excerpt']}" for p in passages[:8]])
            contra_summary = "\n".join([f"- Contradiction: {c['topic']}: {c['resolution']}" for c in contra_data])
            prompt = (
                f"You are a Senior Workplace Context Archaeologist.\n"
                f"Question: {q}\n\n"
                f"Retrieved Evidence:\n{context_blocks}\n\n"
                f"Resolved Contradictions:\n{contra_summary}\n\n"
                f"Instructions:\n"
                f"1. Answer the question thoroughly based ONLY on the evidence provided.\n"
                f"2. Cite specific passage IDs (e.g. DOC-001-P04) and documents for all factual assertions.\n"
                f"3. Note temporal precedence (earlier baseline vs latest authoritative decision).\n"
                f"4. If evidence is missing, state what is missing without guessing.\n"
            )
            final_answer = self.llm.generate(prompt=prompt)
        else:
            # High-fidelity synthesis using reasoning engine
            final_answer = self.reasoner_synthesis(q, passages, contra_data, is_abstained, abstention_reason)

        return {
            "final_answer": final_answer,
            "is_abstained": is_abstained,
            "abstention_reason": abstention_reason,
            "citations": citation_check.get("valid_citations", []),
        }

    def reasoner_synthesis(
        self,
        q: str,
        passages: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        is_abstained: bool,
        abstention_reason: str,
    ) -> str:
        # Calls the verified synthesis logic from the orchestrator
        from src.orchestrator import ContextArchaeologistOrchestrator
        temp_orc = ContextArchaeologistOrchestrator(dataset_dir=self.archive.dataset_dir)
        report = temp_orc.investigate(q)
        return report.summary_answer

    def run(self, question: str) -> Dict[str, Any]:
        initial_state: AgentState = {
            "question": question,
            "iteration": 0,
            "max_iterations": 3,
            "plan": "",
            "next_action": "",
            "tool_name": None,
            "tool_args": {},
            "retrieved_passages": [],
            "inspected_docs": [],
            "contradictions": [],
            "is_abstained": False,
            "abstention_reason": "",
            "final_answer": "",
            "steps": [],
            "citations": [],
        }
        return self.graph.invoke(initial_state)
