"""Context Archaeologist — Streamlit Application.

Single-engine UI powered by the LangGraph investigation agent.
Shows the complete 7-stage workflow with real tool calls, evidence,
contradictions, and validation results.
"""

from __future__ import annotations

import json
from pathlib import Path
import streamlit as st
import pandas as pd

from src.langgraph_agent import LangGraphArchaeologist, InvestigationReport
from src.reasoner import ContradictionFinding


ROOT = Path(__file__).resolve().parent
DATASET_DIR = ROOT / "context_archaeologist_dataset"

st.set_page_config(
    page_title="Context Archaeologist | Agentic AI Investigation",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .main-header {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #38bdf8, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.15rem;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }

    /* Architecture diagram nodes */
    .arch-flow {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        margin: 12px 0;
    }
    .arch-node {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 0.78rem;
        font-weight: 600;
        color: #e2e8f0;
        width: 100%;
        text-align: center;
    }
    .arch-node-active {
        border-color: #818cf8;
        box-shadow: 0 0 8px rgba(129, 140, 248, 0.3);
    }
    .arch-arrow {
        color: #475569;
        font-size: 0.9rem;
        line-height: 1;
    }
    .arch-loop {
        color: #f59e0b;
        font-size: 0.7rem;
        font-style: italic;
    }

    /* Step timeline */
    .step-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-tool { background: #164e63; color: #67e8f9; }
    .badge-eval { background: #3b0764; color: #d8b4fe; }
    .badge-valid { background: #14532d; color: #86efac; }
    .badge-synth { background: #78350f; color: #fde68a; }
    .badge-intent { background: #1e1b4b; color: #a5b4fc; }

    /* Contradiction card */
    .contra-card {
        background-color: #0f172a;
        border-left: 4px solid #f59e0b;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 12px;
    }
    /* Abstention card */
    .abstain-card {
        background-color: #1e1b4b;
        border-left: 4px solid #818cf8;
        padding: 14px 18px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------

@st.cache_resource
def get_agent():
    """Create the LangGraph agent. Falls back to require_llm=False if Ollama
    is unavailable, but shows a warning in the UI."""
    try:
        return LangGraphArchaeologist(dataset_dir=DATASET_DIR, require_llm=True), True
    except ConnectionError:
        return LangGraphArchaeologist(dataset_dir=DATASET_DIR, require_llm=False), False


@st.cache_data
def load_example_queries():
    """Load evaluation scenarios as example queries."""
    eval_file = DATASET_DIR / "evaluation" / "evaluation_questions.json"
    if eval_file.exists():
        with open(eval_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [s["question"] for s in data.get("scenarios", [])]
    return []


agent, llm_connected = get_agent()
example_queries = load_example_queries()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="main-header">🧭 Context Archaeologist</div>', unsafe_allow_html=True)
    st.caption("Agentic AI Investigation Tool")

    st.markdown("---")

    # LLM status
    if llm_connected:
        st.success("🟢 Ollama connected (llama3:latest)", icon="✅")
    else:
        st.warning("🟡 Ollama offline — using deterministic mode", icon="⚠️")

    # Archive stats
    st.metric("Documents", len(agent.archive.documents))
    st.metric("Indexed Passages", len(agent.archive.passages))

    st.markdown("---")

    # Architecture diagram
    st.markdown("##### System Architecture")
    st.markdown(
        """
        <div class="arch-flow">
            <div class="arch-node">1 · Intent Analysis</div>
            <div class="arch-arrow">↓</div>
            <div class="arch-node">2 · Planning</div>
            <div class="arch-arrow">↓</div>
            <div class="arch-node">3 · Tool Execution</div>
            <div class="arch-arrow">↓</div>
            <div class="arch-node">4 · Evidence Evaluation</div>
            <div class="arch-loop">↻ loop back if insufficient</div>
            <div class="arch-arrow">↓</div>
            <div class="arch-node">5 · Validation</div>
            <div class="arch-arrow">↓</div>
            <div class="arch-node">6 · Synthesis / Abstention</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "**LangGraph StateGraph** with conditional routing. "
        "The evaluator loops back to tool execution when evidence "
        "is insufficient. Validation checks citation grounding and "
        "epistemic abstention before synthesis."
    )

    st.markdown("---")

    # Navigation
    tab_choice = st.radio(
        "Navigation",
        ["🔍 Investigation Workbench", "📁 Archive Catalog"],
        label_visibility="collapsed",
    )


# ---------------------------------------------------------------------------
# Helper: get a badge class for a step stage
# ---------------------------------------------------------------------------
def _badge_for_stage(stage: str) -> str:
    s = stage.lower()
    if "intent" in s:
        return "badge-intent"
    if "tool" in s or "plan" in s:
        return "badge-tool"
    if "eval" in s:
        return "badge-eval"
    if "valid" in s:
        return "badge-valid"
    return "badge-synth"


# ---------------------------------------------------------------------------
# Investigation Workbench
# ---------------------------------------------------------------------------
if tab_choice == "🔍 Investigation Workbench":
    st.markdown(
        '<div class="main-header">Investigation Workbench</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">'
        "Ask any question about the Northstar project archive. "
        "The agent investigates autonomously using real tools."
        "</div>",
        unsafe_allow_html=True,
    )

    # Query input
    user_query = st.text_area(
        "Enter your investigation query:",
        height=80,
        placeholder="e.g. What is preventing Northstar from receiving a launch date?",
    )

    # Example queries
    if example_queries:
        with st.expander("💡 Example queries from the evaluation set"):
            for i, eq in enumerate(example_queries):
                if st.button(eq, key=f"eq_{i}", use_container_width=True):
                    st.session_state["prefill_query"] = eq
                    st.rerun()

    # Auto-fill from example click
    if "prefill_query" in st.session_state:
        user_query = st.session_state.pop("prefill_query")

    # Investigate button
    run_btn = st.button("🚀 Investigate", type="primary", disabled=not user_query.strip())

    # -----------------------------------------------------------------------
    # Run investigation
    # -----------------------------------------------------------------------
    report: InvestigationReport | None = None

    if run_btn and user_query.strip():
        with st.spinner("Agent investigating archive…"):
            try:
                report = agent.investigate(user_query.strip())
                st.session_state["last_report"] = report
            except TimeoutError as te:
                st.warning(
                    f"⏱️ **LLM Investigation Response Delayed**: {te}\n\n"
                    "The local model took longer than expected to complete this step. "
                    "You can re-run with deterministic heuristics or increase `OLLAMA_TIMEOUT`."
                )
            except Exception as ex:
                st.error(f"❌ **Investigation Error**: {ex}")
    elif "last_report" in st.session_state:
        report = st.session_state["last_report"]

    if report is not None:
        # --- Abstention banner ---
        if report.is_abstained:
            st.markdown(
                f"""
                <div class="abstain-card">
                    <h4 style="color:#a5b4fc; margin-top:0;">
                        🛑 Epistemic Abstention Triggered
                    </h4>
                    <p style="margin-bottom:0;">{report.abstention_reason}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # --- Tabs ---
        tab_workflow, tab_answer, tab_evidence, tab_conflicts, tab_validation = st.tabs([
            "🔄 Workflow Timeline",
            "📋 Answer",
            "📑 Evidence",
            "⚖️ Contradictions",
            "✅ Validation",
        ])

        # --- Workflow Timeline ---
        with tab_workflow:
            st.markdown("#### Agent Workflow — Sequential Execution Trace")
            st.caption(
                "Each row is a real stage executed by the LangGraph agent. "
                "Expand any step to see tool arguments and output."
            )
            for i, step in enumerate(report.steps):
                badge_cls = _badge_for_stage(step.stage)
                with st.expander(
                    f"**{step.stage}** — `{step.tool_name}`",
                    expanded=(i < 3),
                ):
                    col_in, col_out = st.columns([1, 2])
                    with col_in:
                        st.markdown("**Input:**")
                        st.json(step.input_args)
                    with col_out:
                        st.markdown("**Output:**")
                        st.markdown(f"> {step.output_summary}")

        # --- Answer ---
        with tab_answer:
            st.markdown("#### Investigation Answer")
            st.markdown(report.summary_answer)

        # --- Evidence ---
        with tab_evidence:
            st.markdown(
                f"#### Retrieved Evidence ({len(report.retrieved_passages)} passages)"
            )
            if report.citations:
                st.markdown(
                    f"**Validated citations:** `{'`, `'.join(report.citations[:20])}`"
                )
            for p in report.retrieved_passages:
                with st.expander(
                    f"📍 [{p['passage_id']}] {p['filename']} — "
                    f"{p.get('title', '')} (score: {p.get('score', 'N/A')})"
                ):
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f"**Status:** `{p.get('status', 'N/A')}`")
                    c2.markdown(f"**Authority:** `{p.get('authority', 'N/A')}`")
                    c3.markdown(f"**Created:** `{p.get('created', 'N/A')}`")
                    st.markdown(f"**Section:** {p.get('section', '')}")
                    st.text(p.get("excerpt", ""))

        # --- Contradictions ---
        with tab_conflicts:
            st.markdown("#### Detected Contradictions & Resolutions")
            if not report.contradictions:
                st.info("No conflicting claims detected for this query.")
            else:
                for c in report.contradictions:
                    st.markdown(
                        f"""
                        <div class="contra-card">
                            <h4 style="color:#f59e0b; margin-top:0;">
                                ⚠️ {c.topic}
                            </h4>
                            <p>
                                <strong>Claim A:</strong> {c.conflicting_claim_a}
                                <br><em>Source:</em> {c.evidence_a}
                            </p>
                            <p>
                                <strong>Claim B:</strong> {c.conflicting_claim_b}
                                <br><em>Source:</em> {c.evidence_b}
                            </p>
                            <div style="background:#1e293b; padding:10px;
                                        border-radius:6px; margin-top:8px;">
                                <strong>💡 Resolution:</strong><br>
                                {c.resolution}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # --- Validation ---
        with tab_validation:
            st.markdown("#### Citation & Epistemic Validation")
            val = report.validation_result
            if val:
                col_v, col_i = st.columns(2)
                col_v.metric("Valid Citations", len(val.get("valid_citations", [])))
                col_i.metric("Invalid Citations", len(val.get("invalid_citations", [])))
                if val.get("invalid_citations"):
                    st.error(
                        f"⚠️ Ungrounded citations: "
                        f"`{'`, `'.join(val['invalid_citations'])}`"
                    )
            if report.unresolved_questions:
                st.markdown("#### ❓ Unresolved Questions")
                for uq in report.unresolved_questions:
                    st.warning(uq)
            if report.is_abstained:
                st.info(f"🛑 Abstention: {report.abstention_reason}")


# ---------------------------------------------------------------------------
# Archive Catalog
# ---------------------------------------------------------------------------
elif tab_choice == "📁 Archive Catalog":
    st.markdown(
        '<div class="main-header">Archive Document Catalog</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">'
        "Browse raw documents in the Northstar corporate archive. "
        "Fields like <code>status</code>, <code>authority</code>, and "
        "<code>type</code> are <strong>document metadata</strong> — "
        "they describe the document itself, not business Decision Gates."
        "</div>",
        unsafe_allow_html=True,
    )

    docs = agent.archive.list_all_documents()
    df_docs = pd.DataFrame(
        [
            {
                "ID": d.id,
                "Title": d.title,
                "Type": d.type,
                "Author": d.author,
                "Created": d.created,
                "Status": d.status,
                "Authority": d.authority,
                "Passages": len(d.passage_ids),
            }
            for d in docs
        ]
    )
    st.dataframe(df_docs, use_container_width=True)

    st.markdown("---")
    st.caption(
        "💡 **Document metadata** (status, authority, type) describes the "
        "document's editorial state — e.g. whether it is a draft, approved, "
        "or superseded. **Business Decision Gates** (product acceptance, "
        "security approval, etc.) are derived from the *content* of these "
        "documents during investigation, not from metadata fields."
    )

    selected_doc_id = st.selectbox("Inspect document:", [d.id for d in docs])
    if selected_doc_id:
        doc_details = agent.tools.get_document_details(selected_doc_id)
        st.markdown(f"### {doc_details['title']} (`{doc_details['id']}`)")
        st.markdown(
            f"**Author:** {doc_details['author']} · "
            f"**Created:** {doc_details['created']} · "
            f"**Status:** `{doc_details['status']}` · "
            f"**Authority:** `{doc_details['authority']}`"
        )
        st.code(doc_details["content"], language="markdown")
