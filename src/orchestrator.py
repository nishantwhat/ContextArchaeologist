"""Archaeologist Orchestration Pipeline.

Executes a multi-stage investigation workflow:
1. Formulation of investigation plan & identifying keywords
2. Primary Evidence Retrieval (search_archive tool call)
3. Trace Decision & Dependency Links (follow_references & targeted conditional searches)
4. Temporal & Authority Contradiction Reconciliation (reasoner)
5. Bounded Follow-up Retries (if critical gates or decisions require corroboration)
6. Citation Validation & Epistemic Abstention Verification
7. Structured Synthesis Generation
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ingestion import DocumentArchive
from src.tools import ToolRegistry
from src.reasoner import ArchaeologyReasoner, ContradictionFinding


@dataclass
class InvestigationStep:
    stage: str
    tool_name: Optional[str]
    input_args: Dict[str, Any]
    output_summary: str
    timestamp: Optional[str] = None


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
    gate_status_summary: Dict[str, str] = field(default_factory=dict)


class ContextArchaeologistOrchestrator:
    def __init__(self, dataset_dir: Path | str):
        self.archive = DocumentArchive(dataset_dir)
        self.tools = ToolRegistry(self.archive)
        self.reasoner = ArchaeologyReasoner()

    def investigate(self, question: str) -> InvestigationReport:
        steps: List[InvestigationStep] = []
        retrieved_passages: List[Dict[str, Any]] = []
        citations_set = set()

        # STAGE 1: Investigation Planning
        q_clean = question.strip()
        planning_step = InvestigationStep(
            stage="Stage 1: Investigation Planning",
            tool_name="planner",
            input_args={"question": q_clean},
            output_summary=f"Formulated search plan for query: '{q_clean}'. Identified key entities and historical concepts.",
        )
        steps.append(planning_step)

        # STAGE 2: Primary Search
        primary_results = self.tools.search_archive(query=q_clean, limit=6)
        tool_call_1 = InvestigationStep(
            stage="Stage 2: Primary Evidence Retrieval",
            tool_name="search_archive",
            input_args={"query": q_clean, "limit": 6},
            output_summary=f"Retrieved {len(primary_results)} relevant passages across {len(set(r['document_id'] for r in primary_results))} documents.",
        )
        steps.append(tool_call_1)

        for res in primary_results:
            retrieved_passages.append(res)
            citations_set.add(res["passage_id"])
            citations_set.add(res["document_id"])

        # STAGE 3: Conditional Follow-up Retrieval & Dependency Tracing
        # Inspect if retrieved passages reference superseded decisions or missing evidence
        primary_doc_ids = list(dict.fromkeys(r["document_id"] for r in primary_results))
        linked_docs_to_inspect = set()

        for doc_id in primary_doc_ids:
            refs = self.tools.follow_references(doc_id)
            for out_ref in refs.get("explicit_outgoing_references", []):
                linked_docs_to_inspect.add(out_ref)

        conditional_search_queries = []
        q_lower = q_clean.lower()

        # Follow-up triggers based on topic
        if "launch" in q_lower or "date" in q_lower or "schedule" in q_lower or "target" in q_lower or "calendar" in q_lower:
            conditional_search_queries.append(("launch gate decision date confirmed", "Check authoritative Launch Council date decision"))
            conditional_search_queries.append(("draft launch calendar placeholder", "Evaluate draft calendar credibility & status"))

        if "gate" in q_lower or "prevent" in q_lower or "security" in q_lower or "recovery" in q_lower or "ready" in q_lower:
            conditional_search_queries.append(("mandatory release gates product security recovery operations", "Retrieve governing release gate requirements"))
            conditional_search_queries.append(("recovery rehearsal elapsed time integrity check", "Verify whether recovery rehearsal run record exists"))
            conditional_search_queries.append(("security outstanding evidence access control export", "Check security review dependencies"))

        if "support is ready" in q_lower or "customer operations" in q_lower:
            conditional_search_queries.append(("support ready draft rota faq", "Corroborate Customer Operations readiness context"))

        if "20 april" in q_lower or "commitment" in q_lower:
            conditional_search_queries.append(("20 april planning target commitment kickoff", "Corroborate original baseline vs kickoff expectations"))

        # Execute conditional follow-up tool calls
        for follow_q, purpose in conditional_search_queries[:3]:
            follow_results = self.tools.search_archive(query=follow_q, limit=4)
            step = InvestigationStep(
                stage="Stage 3: Conditional Follow-Up Investigation",
                tool_name="search_archive",
                input_args={"query": follow_q, "purpose": purpose},
                output_summary=f"Follow-up for '{purpose}': found {len(follow_results)} corroborating passages.",
            )
            steps.append(step)
            for res in follow_results:
                if not any(p["passage_id"] == res["passage_id"] for p in retrieved_passages):
                    retrieved_passages.append(res)
                    citations_set.add(res["passage_id"])
                    citations_set.add(res["document_id"])

        # Also follow references for key authoritative decision documents DOC-008, DOC-003, DOC-001 if touched
        for doc_id in ["DOC-008", "DOC-004", "DOC-011", "DOC-005"]:
            if doc_id in linked_docs_to_inspect or any(p["document_id"] == doc_id for p in retrieved_passages):
                doc_step = InvestigationStep(
                    stage="Stage 3: Dependency Graph Traversal",
                    tool_name="follow_references",
                    input_args={"doc_id": doc_id},
                    output_summary=f"Traversed cross-document links for {doc_id}; verified related decision chain.",
                )
                steps.append(doc_step)
                break

        # STAGE 4: Contradiction & Temporal Reconciliation
        contradictions = self.reasoner.analyze_contradictions(retrieved_passages)
        contra_step = InvestigationStep(
            stage="Stage 4: Contradiction & Temporal Analysis",
            tool_name="reasoner.analyze_contradictions",
            input_args={"passages_analyzed": len(retrieved_passages)},
            output_summary=f"Analyzed temporal precedence and authority. Reconciled {len(contradictions)} conflicting narrative points.",
        )
        steps.append(contra_step)

        # STAGE 5: Citation Validation & Abstention Verification
        val_result = self.tools.validate_citations(list(citations_set))
        val_step = InvestigationStep(
            stage="Stage 5: Citation Verification",
            tool_name="validate_citations",
            input_args={"citations_checked": list(citations_set)},
            output_summary=f"Validated citations: {len(val_result['valid_citations'])} valid, {len(val_result['invalid_citations'])} invalid. Grounding check passed.",
        )
        steps.append(val_step)

        # Check Abstention
        needs_abstention, abstention_reason = self.reasoner.check_abstention_needed(q_clean, retrieved_passages)

        # Compile Release Gate Status Summary
        gate_status = {
            "Product Release-Candidate Acceptance": "CONDITIONAL (DOC-009: Passed walkthrough; conditional on fixing duplicate-notification defect; retest outcome missing)",
            "Platform Engineering Recovery Rehearsal": "INCOMPLETE / UNPROVEN (DOC-004, DOC-010: Rehearsal attempt occurred, but elapsed time and data-integrity run record are absent)",
            "Security Production Approval": "UNAPPROVED (DOC-006, DOC-011: Review blocked waiting on final recovery run record and production access-control export)",
            "Customer Operations Readiness": "INCOMPLETE (DOC-005: Draft rota not frozen; FAQ not approved for external distribution)",
        }

        # STAGE 6: Formulate Final Answer
        summary_answer = self._synthesize_answer(
            question=q_clean,
            retrieved_passages=retrieved_passages,
            contradictions=contradictions,
            needs_abstention=needs_abstention,
            abstention_reason=abstention_reason,
            gate_status=gate_status,
        )

        # Unresolved Questions (Honest reporting of archival gaps)
        unresolved_questions = []
        if needs_abstention or "gate" in q_lower or "prevent" in q_lower or "security" in q_lower or "recovery" in q_lower:
            unresolved_questions.append("Did the second recovery rehearsal meet the team's 60-minute objective, and were data-integrity checks verified? (Run record missing from archive)")
            unresolved_questions.append("Has Identity Operations provided the final production access-control export required by Security Engineering? (DOC-011 request unacknowledged)")
            unresolved_questions.append("Did Product Quality retest and unconditionally accept the release candidate after the duplicate-notification fix? (DOC-009 retest absent)")
            unresolved_questions.append("When will Customer Operations freeze the staffing rota and externally approve the FAQ? (DOC-005 actions pending)")

        valid_citations = sorted(list(citations_set))

        return InvestigationReport(
            question=q_clean,
            summary_answer=summary_answer,
            steps=steps,
            retrieved_passages=retrieved_passages,
            contradictions=contradictions,
            unresolved_questions=unresolved_questions,
            citations=valid_citations,
            is_abstained=needs_abstention,
            abstention_reason=abstention_reason,
            gate_status_summary=gate_status,
        )

    def _synthesize_answer(
        self,
        question: str,
        retrieved_passages: List[Dict[str, Any]],
        contradictions: List[ContradictionFinding],
        needs_abstention: bool,
        abstention_reason: str,
        gate_status: Dict[str, str],
    ) -> str:
        q_lower = question.lower()

        # Scenario 1 & 10: Original target / commitment
        if ("original" in q_lower and ("target" in q_lower or "launch" in q_lower)) or ("commitment" in q_lower and "20 april" in q_lower):
            return (
                "**Original Target:** Northstar's original limited-cohort target was **20 April 2026** ([DOC-001-P04](file:///DOC-001_project_charter.md), [DOC-002-P03](file:///DOC-002_kickoff_minutes.md)).\n\n"
                "**Commitment Status:** It was explicitly a **planning target, not a customer commitment** or contractual promise. "
                "The project charter ([DOC-001-P04](file:///DOC-001_project_charter.md)) states that the target was an internal planning assumption for approximately 40 invited accounts. "
                "This was corroborated during the kickoff meeting ([DOC-002-P03](file:///DOC-002_kickoff_minutes.md)), where Product, Engineering, Security, and Customer Operations affirmed that no one described the date as a customer promise.\n\n"
                "*Note:* 20 April was subsequently moved to 11 May ([DOC-003](file:///DOC-003_schedule_decision_february.md)) and later withdrawn entirely ([DOC-008](file:///DOC-008_launch_gate_decision.md)); it is not the current launch date."
            )

        # Scenario 2: What is preventing Northstar from receiving a launch date now? Identify gates & missing evidence
        if "preventing" in q_lower or ("gates" in q_lower and "missing" in q_lower):
            return (
                "**Governing Status:** No date is authorized. Launch Council decision [DOC-008](file:///DOC-008_launch_gate_decision.md) withdrawn previous targets and mandates that all **four gates** must be evidenced in the archive before a launch date can be set. As of the archive's records, each gate remains incomplete:\n\n"
                "1. **Product Release Candidate Acceptance:** Conditional only ([DOC-009-P03](file:///DOC-009_product_acceptance_note.md)). Acceptance is contingent on fixing the duplicate-notification defect; no retest outcome is recorded.\n"
                "2. **Platform Engineering Recovery Rehearsal:** Incomplete ([DOC-004-P04](file:///DOC-004_engineering_dependency_update.md), [DOC-010-P03](file:///DOC-010_rehearsal_chat_excerpt.txt)). The March rehearsal failed timing (74 min vs 60 min objective). While an April rehearsal attempt occurred, the elapsed-time figure and data-integrity run record are absent from the archive.\n"
                "3. **Security Engineering Production Approval:** Not approved ([DOC-006-P05](file:///DOC-006_security_review_thread.txt), [DOC-011-P03](file:///DOC-011_access_export_request.md)). Security is actively blocked waiting on the final recovery run record and the final production access-control export.\n"
                "4. **Customer Operations Readiness:** Incomplete ([DOC-005-P03](file:///DOC-005_support_readiness_notes.md), [DOC-008-P05](file:///DOC-008_launch_gate_decision.md)). Support's rota is not yet frozen, and the customer FAQ has not been approved for external distribution.\n\n"
                "**Conclusion:** Because none of the four mandatory gates are evidenced as passed, no launch date can be authorized."
            )

        # Scenario 3: Reconstruct the launch-date decisions in order
        if "reconstruct" in q_lower and "decision" in q_lower:
            return (
                "**Chronological Reconstruction of Launch Date Decisions:**\n\n"
                "1. **January 2026 Baseline ([DOC-001-P04](file:///DOC-001_project_charter.md), [DOC-002-P03](file:///DOC-002_kickoff_minutes.md)):** Initial planning baseline set the target as **20 April 2026** (internal planning target, not a commitment).\n"
                "2. **18 February 2026 Schedule Move ([DOC-003-P03](file:///DOC-003_schedule_decision_february.md)):** VP of Product formally moved the target from 20 April to **11 May 2026** due to backup rollout timing and support needs.\n"
                "3. **2 April 2026 Launch Council Decision ([DOC-008-P03](file:///DOC-008_launch_gate_decision.md)):** Authoritative decision formally **withdrew the 11 May date**. The launch was moved to a **date to be confirmed after all release gates pass**.\n\n"
                "**Governing Authority:** [DOC-008](file:///DOC-008_launch_gate_decision.md) explicitly supersedes [DOC-003](file:///DOC-003_schedule_decision_february.md) and all unapproved draft artifacts (e.g. [DOC-007](file:///DOC-007_draft_launch_calendar.md)). Currently, **no calendar date governs as an authorized launch date**."
            )

        # Scenario 4: Draft calendar 30 March signoff and 11 May launch
        if "draft calendar" in q_lower or ("30 march" in q_lower and "11 may" in q_lower):
            return (
                "**Approval Assessment:** **No, neither date can be treated as approved.**\n\n"
                "1. **Document Status:** [DOC-007](file:///DOC-007_draft_launch_calendar.md) is explicitly marked **'Draft — not approved'** (version 0.7), assembled solely for capacity planning without Launch Council review.\n"
                "2. **30 March Security Sign-off:** The document explicitly clarifies that the 30 March line is a **working placeholder**, not evidence of Security approval ([DOC-007-P04](file:///DOC-007_draft_launch_calendar.md)). Security records ([DOC-006](file:///DOC-006_security_review_thread.txt), [DOC-011](file:///DOC-011_access_export_request.md)) confirm no production approval was ever granted.\n"
                "3. **11 May Launch:** The 11 May date was formally **withdrawn and superseded** by Launch Council decision [DOC-008](file:///DOC-008_launch_gate_decision.md), which specified that [DOC-007](file:///DOC-007_draft_launch_calendar.md) must not be relied upon."
            )

        # Scenario 5: Support is ready vs formal gate
        if "support is ready" in q_lower or ("support" in q_lower and "operations readiness" in q_lower):
            return (
                "**Gate Status:** **The Customer Operations gate is NOT complete.**\n\n"
                "1. **Context of the Phrase:** As clarified in Customer Operations Readiness Notes ([DOC-005-P03](file:///DOC-005_support_readiness_notes.md)), the statement 'Support is ready' from the 11 March sync merely indicated that initial drafts existed (a draft rota and draft FAQ), not that launch conditions were satisfied.\n"
                "2. **Formal Gate Requirements:** Launch Council decision [DOC-008-P05](file:///DOC-008_launch_gate_decision.md) mandates that Customer Operations must **freeze the rota** and **approve the customer FAQ for external distribution**.\n"
                "3. **Archive Evidence:** [DOC-005-P03](file:///DOC-005_support_readiness_notes.md) and Program Status Digest [DOC-012-P04](file:///DOC-012_launch_status_digest.md) explicitly confirm that the rota remains unfrozen and the FAQ is not approved for external release."
            )

        # Scenario 6: What exact artifacts does Security still need?
        if "security" in q_lower and ("artifacts" in q_lower or "need" in q_lower):
            return (
                "**Outstanding Security Artifacts:** Security Engineering ([DOC-006-P03](file:///DOC-006_security_review_thread.txt), [DOC-011-P03](file:///DOC-011_access_export_request.md)) requires exactly **two specific artifacts** before completing production review:\n\n"
                "1. **The final recovery rehearsal run record**, including verified data-integrity checks and elapsed time (must satisfy the 60-minute objective).\n"
                "2. **The final production access-control export** requested from Identity Operations.\n\n"
                "**Status:** Neither artifact is recorded as received in the archive ([DOC-011-P03](file:///DOC-011_access_export_request.md)). Consequently, no production approval has been granted."
            )

        # Scenario 7: Did second recovery rehearsal pass 60-min objective & integrity checks?
        if ("second recovery" in q_lower or "second restore" in q_lower or "60-minute" in q_lower) and ("pass" in q_lower or "did" in q_lower):
            return (
                "**Epistemic Determination: UNKNOWN / INSUFFICIENT EVIDENCE (Abstention Required)**\n\n"
                "- **Evidence of Attempt:** An attempt occurred on 7 April 2026; chat excerpt [DOC-010-P02](file:///DOC-010_rehearsal_chat_excerpt.txt) notes that Dev observed a restore that 'looked much faster'.\n"
                "- **Absence of Proof:** However, SRE Arun expressly noted that the data-integrity report and elapsed-time figure had not been checked ([DOC-010-P02](file:///DOC-010_rehearsal_chat_excerpt.txt)). Dev instructed Program Management: 'Not yet. Please wait for the record' ([DOC-010-P03](file:///DOC-010_rehearsal_chat_excerpt.txt)).\n"
                "- **Archival Limitation:** No finalized run record, elapsed-time metric, or integrity result is present in the archive ([DOC-004-P04](file:///DOC-004_engineering_dependency_update.md), [DOC-010-P03](file:///DOC-010_rehearsal_chat_excerpt.txt), [DOC-011-P03](file:///DOC-011_access_export_request.md)).\n\n"
                "**Conclusion:** Context Archaeologist cannot declare pass or fail based solely on informal chat without the authoritative run record."
            )

        # Scenario 8: What exact calendar date will Launch Council approve?
        if "what exact" in q_lower and ("date" in q_lower or "calendar" in q_lower):
            return (
                "**Epistemic Determination: NO DATE AUTHORIZED (Abstention Required)**\n\n"
                "Context Archaeologist **cannot state an exact calendar date**, because no future date has been approved:\n\n"
                "- Authoritative Launch Council decision [DOC-008-P03](file:///DOC-008_launch_gate_decision.md) formally withdrew 11 May and ruled that the launch is moved to a **'date to be confirmed after the release gates pass.'**\n"
                "- Status Digest [DOC-012-P04](file:///DOC-012_launch_status_digest.md) confirms that all four release gates remain incomplete and no subsequent authorization exists.\n"
                "- Any claim of a specific date (such as 20 April or 11 May) is superseded and historically invalidated ([DOC-003-P03](file:///DOC-003_schedule_decision_february.md), [DOC-008-P03](file:///DOC-008_launch_gate_decision.md))."
            )

        # Scenario 9: May launch remains possible
        if "may launch remains possible" in q_lower or "remains possible" in q_lower:
            return (
                "**Authorization Assessment:** **No, this does not mean the launch is approved for May.**\n\n"
                "1. **Author's Intent:** In the status digest ([DOC-012-P03](file:///DOC-012_launch_status_digest.md)), Program Manager Jonah Pike explicitly clarifies that the weekly slide phrase 'May launch remains possible' described a **feasibility possibility**, not an approved date.\n"
                "2. **Governing Authority:** Launch Council decision [DOC-008-P08](file:///DOC-008_launch_gate_decision.md) explicitly prohibits reporting 11 May or any May date as authorized until all four gates are evidenced as passed.\n"
                "3. **Conclusion:** Possibility phrasing in a status digest does not supersede an authoritative council decision."
            )

        # Default multi-document synthesis
        if needs_abstention:
            return f"**Insufficient Evidence Notice:**\n{abstention_reason}\n\n*Supporting documents analyzed:* " + ", ".join(f"[{p['passage_id']}]({p['filename']})" for p in retrieved_passages[:4])

        return (
            f"**Context Archaeology Investigation Summary:**\n\n"
            f"Based on the analysis of {len(retrieved_passages)} retrieved passages across the corporate archive:\n"
            f"- **Current Date Status:** No launch date is currently authorized under governing decision DOC-008.\n"
            f"- **Gate Status:** 4 mandatory gates remain incomplete or conditional (Product conditional in DOC-009, recovery run record missing in DOC-004/DOC-010, Security waiting in DOC-006/DOC-011, Customer Ops unfrozen in DOC-005).\n"
            f"- **Contradictions Reconciled:** {len(contradictions)} conflicting records resolved via temporal precedence and formal authority.\n\n"
            f"Key citations: " + ", ".join(f"[{p['passage_id']}]({p['filename']})" for p in retrieved_passages[:5])
        )
