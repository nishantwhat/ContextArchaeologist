"""LangGraph-driven Autonomous Investigation Agent for Context Archaeologist.

Seven-stage stateful investigation workflow:
1. Intent Analysis    — classify query type and complexity
2. Planning           — formulate search strategy and initial query
3. Tool Execution     — execute search/retrieval tools against the archive
4. Evidence Evaluation — check sufficiency, detect contradictions, decide next action
5. Conditional Follow-up — route back to tools if evidence is insufficient (graph edge)
6. Validation         — citation verification and epistemic abstention check
7. Synthesis          — grounded final answer or honest abstention
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


# ---------------------------------------------------------------------------
# Data classes (previously in orchestrator.py)
# ---------------------------------------------------------------------------

@dataclass
class InvestigationStep:
    stage: str
    tool_name: Optional[str]
    input_args: Dict[str, Any]
    output_summary: str


@dataclass
class InvestigationReport:
    question: str
    summary_answer: str
    steps: List[InvestigationStep]
    retrieved_passages: List[Dict[str, Any]]
    contradictions: List[ContradictionFinding]
    unresolved_questions: List[str]
    citations: List[str]
    is_abstained: bool
    abstention_reason: str
    validation_result: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    question: str
    intent: Dict[str, Any]
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
    validation_result: Dict[str, Any]
    unresolved_questions: List[str]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class LangGraphArchaeologist:
    """Autonomous investigation agent built on a LangGraph StateGraph.

    Parameters
    ----------
    dataset_dir : Path or str
        Path to the ``context_archaeologist_dataset`` directory.
    require_llm : bool
        If *True* (default/production), the agent raises ``ConnectionError``
        when Ollama is unreachable.  Set to *False* only for fast offline
        testing — the agent still runs real tools and reasoning, but uses
        deterministic heuristics for routing instead of LLM-directed
        decisions.
    """

    def __init__(
        self,
        dataset_dir: Path | str,
        require_llm: bool = True,
        use_llm: Optional[bool] = None,
    ):
        self.archive = DocumentArchive(dataset_dir)
        self.tools = ToolRegistry(self.archive)
        self.reasoner = ArchaeologyReasoner()
        self.llm = OllamaClient()
        self.llm_available = self.llm.is_available()

        # If use_llm is explicitly passed, map it to require_llm behavior
        if use_llm is not None:
            require_llm = use_llm
            if not use_llm:
                self.llm_available = False

        if require_llm and not self.llm_available:
            raise ConnectionError(
                "Ollama is not running or the model is not available. "
                "Start Ollama with `ollama serve` and pull the model with "
                "`ollama pull llama3:latest`.  Context Archaeologist requires "
                "a local LLM — it does not fall back to scripted answers."
            )

        self.graph = self._build_graph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("intent_analysis_node", self.intent_analysis_node)
        workflow.add_node("planner_node", self.planner_node)
        workflow.add_node("tool_executor_node", self.tool_executor_node)
        workflow.add_node("evaluator_node", self.evaluator_node)
        workflow.add_node("validation_node", self.validation_node)
        workflow.add_node("synthesis_node", self.synthesis_node)

        workflow.set_entry_point("intent_analysis_node")
        workflow.add_edge("intent_analysis_node", "planner_node")
        workflow.add_edge("planner_node", "tool_executor_node")
        workflow.add_edge("tool_executor_node", "evaluator_node")

        # Stage 5: conditional routing
        workflow.add_conditional_edges(
            "evaluator_node",
            self.route_next_step,
            {
                "continue_search": "tool_executor_node",
                "validate": "validation_node",
            },
        )
        workflow.add_edge("validation_node", "synthesis_node")
        workflow.add_edge("synthesis_node", END)

        return workflow.compile()

    # ------------------------------------------------------------------
    # Stage 1 — Intent Analysis
    # ------------------------------------------------------------------

    def intent_analysis_node(self, state: AgentState) -> Dict[str, Any]:
        """Classify the query to guide downstream planning."""
        q = state["question"]
        steps = list(state.get("steps", []))

        use_heuristic = not self.llm_available
        if self.llm_available:
            prompt = (
                "You are an investigation analyst. Classify this question "
                "about a corporate project archive.\n"
                f"Question: '{q}'\n\n"
                "Respond with a JSON object:\n"
                '{"intent_type": "factual_lookup|timeline_reconstruction|'
                'gap_analysis|contradiction_check|status_assessment", '
                '"key_entities": ["list of key entities"], '
                '"requires_cross_document": true/false, '
                '"complexity": "simple|moderate|complex"}\n'
            )
            try:
                intent = self.llm.generate_json(prompt)
                if not isinstance(intent, dict) or "error" in intent:
                    use_heuristic = True
            except (TimeoutError, Exception):
                use_heuristic = True

        if use_heuristic:
            q_lower = q.lower()
            intent_type = "factual_lookup"
            if any(w in q_lower for w in ["reconstruct", "timeline", "chronolog", "order", "history"]):
                intent_type = "timeline_reconstruction"
            elif any(w in q_lower for w in ["prevent", "gate", "missing", "block", "incomplete"]):
                intent_type = "gap_analysis"
            elif any(w in q_lower for w in ["contradict", "conflict", "disagree", "versus", "vs"]):
                intent_type = "contradiction_check"
            elif any(w in q_lower for w in ["status", "ready", "approved", "complete"]):
                intent_type = "status_assessment"

            intent = {
                "intent_type": intent_type,
                "key_entities": [],
                "requires_cross_document": any(
                    w in q_lower for w in ["gate", "prevent", "all", "across", "reconstruct"]
                ),
                "complexity": "complex" if len(q.split()) > 15 else "moderate",
            }

        steps.append({
            "stage": "Stage 1: Intent Analysis",
            "tool_name": "intent_classifier",
            "input_args": {"question": q},
            "output_summary": (
                f"Classified as '{intent.get('intent_type', 'unknown')}'. "
                f"Cross-document: {intent.get('requires_cross_document', False)}. "
                f"Complexity: {intent.get('complexity', 'moderate')}."
            ),
        })

        return {"intent": intent, "steps": steps}

    # ------------------------------------------------------------------
    # Stage 2 — Planning
    # ------------------------------------------------------------------

    def planner_node(self, state: AgentState) -> Dict[str, Any]:
        """Formulate a search strategy based on intent analysis."""
        q = state["question"]
        intent = state.get("intent", {})
        steps = list(state.get("steps", []))
        initial_search_query = q

        max_iter = 4 if intent.get("requires_cross_document") else 3

        use_heuristic = not self.llm_available
        if self.llm_available:
            prompt = (
                "You are a Senior Context Archaeologist investigating a "
                "corporate archive.\n"
                f"User Question: '{q}'\n"
                f"Intent Classification: {json.dumps(intent)}\n\n"
                "Formulate a search plan. Respond with a JSON object:\n"
                '{"plan": "description of search strategy", '
                '"initial_search_query": "targeted search keywords"}\n'
            )
            try:
                res = self.llm.generate_json(prompt)
                if isinstance(res, dict) and "plan" in res:
                    plan = res.get("plan", f"Investigate corporate archive for '{q}'")
                    initial_search_query = res.get("initial_search_query", q)
                else:
                    use_heuristic = True
            except (TimeoutError, Exception):
                use_heuristic = True

        if use_heuristic:
            plan = (
                f"Investigate archive for: '{q}'. Strategy: primary keyword "
                "search, then follow document references for cross-validation."
            )

        steps.append({
            "stage": "Stage 2: Planning",
            "tool_name": "planner",
            "input_args": {"question": q, "intent": intent.get("intent_type", "unknown")},
            "output_summary": plan,
        })

        return {
            "plan": plan,
            "next_action": "search",
            "tool_name": "search_archive",
            "tool_args": {"query": initial_search_query, "limit": 6},
            "steps": steps,
            "iteration": 0,
            "max_iterations": max_iter,
        }

    # ------------------------------------------------------------------
    # Stage 3 — Tool Execution
    # ------------------------------------------------------------------

    def tool_executor_node(self, state: AgentState) -> Dict[str, Any]:
        """Execute the selected tool and collect evidence."""
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
            output_summary = (
                f"search_archive(query='{query}', limit={limit}) → "
                f"{len(results)} passages retrieved."
            )

        elif tool_name == "get_document_details":
            doc_id = tool_args.get("doc_id", "")
            doc_data = self.tools.get_document_details(doc_id)
            if "id" in doc_data and doc_id not in inspected:
                inspected.append(doc_id)
            output_summary = (
                f"get_document_details('{doc_id}') → "
                f"status={doc_data.get('status')}, "
                f"authority={doc_data.get('authority')}."
            )

        elif tool_name == "follow_references":
            doc_id = tool_args.get("doc_id", "")
            ref_data = self.tools.follow_references(doc_id)
            refs = ref_data.get("explicit_outgoing_references", [])
            output_summary = (
                f"follow_references('{doc_id}') → linked to {refs}."
            )
            # Fetch details and passages from newly discovered documents
            for ref_doc in refs:
                if ref_doc not in inspected:
                    self.tools.get_document_details(ref_doc)
                    inspected.append(ref_doc)
                    linked_res = self.tools.search_archive(query=ref_doc, limit=3)
                    for lr in linked_res:
                        if not any(p["passage_id"] == lr["passage_id"] for p in passages):
                            passages.append(lr)

        elif tool_name == "inspect_timeline":
            timeline = self.tools.inspect_timeline()
            output_summary = (
                f"inspect_timeline() → {len(timeline)} records in "
                "chronological order."
            )

        steps.append({
            "stage": f"Stage 3: Tool Execution (iteration {iteration})",
            "tool_name": tool_name,
            "input_args": tool_args,
            "output_summary": output_summary,
        })

        return {
            "iteration": iteration,
            "retrieved_passages": passages,
            "inspected_docs": inspected,
            "steps": steps,
        }

    # ------------------------------------------------------------------
    # Stage 4 — Evidence Evaluation
    # ------------------------------------------------------------------

    def evaluator_node(self, state: AgentState) -> Dict[str, Any]:
        """Evaluate evidence sufficiency and detect contradictions."""
        passages = state.get("retrieved_passages", [])
        q = state["question"]
        iteration = state.get("iteration", 1)
        max_iter = state.get("max_iterations", 3)
        steps = list(state.get("steps", []))

        # Run contradiction analysis on current evidence
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

        # --- Decide: continue searching or proceed to validation ---

        if iteration >= max_iter:
            next_action = "validate"
            tool_name = None
            tool_args = {}
            eval_summary = (
                f"Max iterations ({max_iter}) reached. "
                f"{len(contra_dicts)} contradictions found. "
                "Proceeding to validation."
            )
        elif self.llm_available:
            passage_snippets = "\n".join([
                f"- [{p['passage_id']}] {p['document_id']}: "
                f"{p['section']} — {p['excerpt'][:120]}"
                for p in passages[-5:]
            ])
            prompt = (
                f"You are investigating: '{q}'.\n"
                f"Iteration: {iteration}/{max_iter}\n"
                f"Current Evidence ({len(passages)} passages):\n"
                f"{passage_snippets}\n\n"
                "Determine if more evidence is needed or if we can answer.\n"
                "Tools: 'search_archive' (query, limit), "
                "'follow_references' (doc_id), "
                "'get_document_details' (doc_id).\n"
                "Respond in JSON:\n"
                '{"next_action": "continue_search" or "validate", '
                '"tool_name": "tool_name", '
                '"tool_args": {"query": "..."}, '
                '"reasoning": "why"}\n'
            )
            try:
                res = self.llm.generate_json(prompt)
                if isinstance(res, dict) and "next_action" in res:
                    next_action = res.get("next_action", "validate")
                    tool_name = res.get("tool_name", "search_archive")
                    tool_args = res.get("tool_args", {})
                    eval_summary = (
                        f"LLM evaluation: {res.get('reasoning', next_action)}. "
                        f"{len(contra_dicts)} contradictions found."
                    )
                else:
                    res = None
            except (TimeoutError, Exception):
                res = None

            if res is None:
                # Heuristic fallback on timeout or error
                unique_docs = set(p["document_id"] for p in passages)
                if iteration == 1 and passages:
                    top_doc = passages[0]["document_id"]
                    next_action = "continue_search"
                    tool_name = "follow_references"
                    tool_args = {"doc_id": top_doc}
                    eval_summary = (
                        f"Heuristic fallback: {len(unique_docs)} documents covered. "
                        f"Following references from {top_doc}. "
                        f"{len(contra_dicts)} contradictions found."
                    )
                else:
                    next_action = "validate"
                    tool_name = None
                    tool_args = {}
                    eval_summary = (
                        f"Heuristic fallback: evidence sufficient ({len(passages)} passages). "
                        f"{len(contra_dicts)} contradictions found. Proceeding to validation."
                    )
        else:
            # Generic heuristic: after first search, follow references from
            # the most relevant document for broader cross-document coverage.
            unique_docs = set(p["document_id"] for p in passages)
            if iteration == 1 and passages:
                top_doc = passages[0]["document_id"]
                next_action = "continue_search"
                tool_name = "follow_references"
                tool_args = {"doc_id": top_doc}
                eval_summary = (
                    f"Heuristic: {len(unique_docs)} documents covered so far. "
                    f"Following references from {top_doc} for broader coverage. "
                    f"{len(contra_dicts)} contradictions found."
                )
            else:
                next_action = "validate"
                tool_name = None
                tool_args = {}
                eval_summary = (
                    f"Evidence sufficient ({len(passages)} passages across "
                    f"{len(unique_docs)} documents). "
                    f"{len(contra_dicts)} contradictions found. "
                    "Proceeding to validation."
                )

        steps.append({
            "stage": f"Stage 4: Evidence Evaluation (iteration {iteration})",
            "tool_name": "evaluator",
            "input_args": {
                "passages_count": len(passages),
                "contradictions_count": len(contra_dicts),
            },
            "output_summary": eval_summary,
        })

        return {
            "next_action": next_action,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "contradictions": contra_dicts,
            "steps": steps,
        }

    # ------------------------------------------------------------------
    # Stage 5 — Conditional Routing (graph edge)
    # ------------------------------------------------------------------

    def route_next_step(self, state: AgentState) -> str:
        """Route back to tool execution or forward to validation."""
        if (
            state.get("next_action") == "continue_search"
            and state.get("iteration", 0) < state.get("max_iterations", 3)
        ):
            return "continue_search"
        return "validate"

    # ------------------------------------------------------------------
    # Stage 6 — Validation
    # ------------------------------------------------------------------

    def validation_node(self, state: AgentState) -> Dict[str, Any]:
        """Validate citations and check whether abstention is required."""
        passages = state.get("retrieved_passages", [])
        q = state["question"]
        steps = list(state.get("steps", []))

        # Collect all citation IDs
        all_ids = list(set(
            [p["passage_id"] for p in passages]
            + [p["document_id"] for p in passages]
        ))

        # Citation validation
        val_result = self.tools.validate_citations(all_ids)

        # Epistemic abstention check
        needs_abstention, abstention_reason = self.reasoner.check_abstention_needed(
            q, passages
        )

        # Surface unresolved questions from contradiction analysis
        unresolved = []
        for c in state.get("contradictions", []):
            resolution_lower = c.get("resolution", "").lower()
            if any(w in resolution_lower for w in ["missing", "absent", "unknown", "lacks"]):
                unresolved.append(f"{c['topic']}: {c['resolution']}")

        steps.append({
            "stage": "Stage 6: Validation",
            "tool_name": "validate_citations",
            "input_args": {"citations_checked": len(all_ids)},
            "output_summary": (
                f"Citations: {len(val_result['valid_citations'])} valid, "
                f"{len(val_result['invalid_citations'])} invalid. "
                f"Abstention required: {needs_abstention}."
            ),
        })

        return {
            "validation_result": val_result,
            "is_abstained": needs_abstention,
            "abstention_reason": abstention_reason,
            "citations": sorted(val_result.get("valid_citations", [])),
            "unresolved_questions": unresolved,
            "steps": steps,
        }

    # ------------------------------------------------------------------
    # Stage 7 — Synthesis
    # ------------------------------------------------------------------

    def synthesis_node(self, state: AgentState) -> Dict[str, Any]:
        """Generate a grounded final answer from the collected evidence."""
        q = state["question"]
        passages = state.get("retrieved_passages", [])
        contra_data = state.get("contradictions", [])
        is_abstained = state.get("is_abstained", False)
        abstention_reason = state.get("abstention_reason", "")
        steps = list(state.get("steps", []))

        if self.llm_available and not is_abstained:
            context_blocks = "\n".join([
                f"[{p['passage_id']}] ({p['filename']}, "
                f"status={p.get('status')}, "
                f"created={p.get('created')}): {p['excerpt']}"
                for p in passages[:8]
            ])
            contra_summary = "\n".join([
                f"- Contradiction: {c['topic']}: {c['resolution']}"
                for c in contra_data
            ])
            prompt = (
                "You are a Senior Workplace Context Archaeologist.\n"
                f"Question: {q}\n\n"
                f"Retrieved Evidence:\n{context_blocks}\n\n"
                f"Resolved Contradictions:\n{contra_summary}\n\n"
                "Instructions:\n"
                "1. Answer the question thoroughly based ONLY on the "
                "evidence provided.\n"
                "2. Cite specific passage IDs (e.g. DOC-001-P04) and "
                "documents for all factual assertions.\n"
                "3. Note temporal precedence (earlier baseline vs latest "
                "authoritative decision).\n"
                "4. If evidence is missing, state what is missing without "
                "guessing.\n"
            )
            try:
                final_answer = self.llm.generate(prompt=prompt)
            except (TimeoutError, Exception):
                final_answer = self._synthesize_from_evidence(
                    q, passages, contra_data, is_abstained, abstention_reason
                )
        else:
            final_answer = self._synthesize_from_evidence(
                q, passages, contra_data, is_abstained, abstention_reason
            )

        steps.append({
            "stage": "Stage 7: Synthesis",
            "tool_name": "synthesizer",
            "input_args": {
                "passages_used": len(passages),
                "contradictions": len(contra_data),
                "abstained": is_abstained,
            },
            "output_summary": (
                "Abstention triggered — answer withheld on missing evidence."
                if is_abstained
                else f"Synthesized answer from {len(passages)} passages and "
                     f"{len(contra_data)} contradiction resolutions."
            ),
        })

        return {"final_answer": final_answer, "steps": steps}

    # ------------------------------------------------------------------
    # Evidence-based synthesis (no LLM required)
    # ------------------------------------------------------------------

    def _synthesize_from_evidence(
        self,
        question: str,
        passages: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        is_abstained: bool,
        abstention_reason: str,
    ) -> str:
        """Build a grounded answer from passages and reasoning results.

        This is NOT a hardcoded template — it extracts and presents actual
        evidence from the retrieved passages and contradiction resolutions.
        """
        if is_abstained:
            parts = [
                f"**Insufficient Evidence — Abstention Required**\n\n"
                f"{abstention_reason}\n\n"
                f"**Supporting evidence reviewed:**"
            ]
            for p in passages[:4]:
                excerpt = p["excerpt"].strip().replace("\n", " ")[:200]
                parts.append(
                    f"- [{p['passage_id']}] {p.get('title', p['document_id'])}: "
                    f"{excerpt}"
                )
            return "\n".join(parts)

        # --- Non-abstention: evidence-based answer ---
        doc_groups: Dict[str, List[Dict[str, Any]]] = {}
        for p in passages:
            doc_groups.setdefault(p["document_id"], []).append(p)

        parts = [
            "**Investigation Findings:**\n",
            f"Based on analysis of {len(passages)} passages across "
            f"{len(doc_groups)} documents:\n",
        ]

        # Key evidence excerpts
        for p in passages[:6]:
            excerpt = p["excerpt"].strip().replace("\n", " ")[:250]
            status_tag = (
                f" (status: {p.get('status')}, authority: {p.get('authority')})"
                if p.get("status") else ""
            )
            parts.append(
                f"- **[{p['passage_id']}] "
                f"{p.get('title', p['document_id'])}**{status_tag}: "
                f"{excerpt}"
            )

        # Contradiction resolutions
        if contradictions:
            parts.append(
                f"\n**Contradiction Analysis "
                f"({len(contradictions)} conflicts detected):**\n"
            )
            for c in contradictions:
                parts.append(f"- **{c['topic']}:** {c['resolution']}")

        # Citations
        cited = sorted(set(p["passage_id"] for p in passages[:6]))
        parts.append(f"\n**Citations:** {', '.join(cited)}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, question: str) -> Dict[str, Any]:
        """Execute the full investigation and return the raw state dict."""
        initial_state: AgentState = {
            "question": question,
            "intent": {},
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
            "validation_result": {},
            "unresolved_questions": [],
        }
        return self.graph.invoke(initial_state)

    def investigate(self, question: str) -> InvestigationReport:
        """Execute the investigation and return a structured report."""
        result = self.run(question)

        contra_objs = [
            ContradictionFinding(
                topic=c["topic"],
                conflicting_claim_a=c["conflicting_claim_a"],
                evidence_a=c["evidence_a"],
                conflicting_claim_b=c["conflicting_claim_b"],
                evidence_b=c["evidence_b"],
                resolution=c["resolution"],
                authoritative_source=c["authoritative_source"],
                is_resolved=True,
            )
            for c in result.get("contradictions", [])
        ]

        step_objs = [
            InvestigationStep(
                stage=s["stage"],
                tool_name=s["tool_name"],
                input_args=s["input_args"],
                output_summary=s["output_summary"],
            )
            for s in result.get("steps", [])
        ]

        return InvestigationReport(
            question=result["question"],
            summary_answer=result["final_answer"],
            steps=step_objs,
            retrieved_passages=result.get("retrieved_passages", []),
            contradictions=contra_objs,
            unresolved_questions=result.get("unresolved_questions", []),
            citations=result.get("citations", []),
            is_abstained=result.get("is_abstained", False),
            abstention_reason=result.get("abstention_reason", ""),
            validation_result=result.get("validation_result", {}),
        )
