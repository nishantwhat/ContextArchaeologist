"""Context Archaeologist — Multi-Agent Streamlit Application.

Demonstrating genuine multi-agent collaborative investigation:
  1. Lead Investigator: Query intent analysis, task delegation & final synthesis
  2. Evidence Scout: Autonomous multi-round tool-backed retrieval
  3. Precedence Auditor: Contradiction analysis, authority ranking & epistemic abstention
"""

from __future__ import annotations

import json
from pathlib import Path
import streamlit as st
import pandas as pd

from src.multi_agent_graph import MultiAgentArchaeologist, MultiAgentReport


ROOT = Path(__file__).resolve().parent
DATASET_DIR = ROOT / "context_archaeologist_dataset"

st.set_page_config(
    page_title="Context Archaeologist | Multi-Agent Investigation",
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
        font-size: 0.95rem;
        margin-bottom: 1.2rem;
    }

    /* Architecture diagram nodes */
    .arch-flow {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 3px;
        margin: 12px 0;
    }
    .arch-node {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 0.8rem;
        font-weight: 600;
        color: #e2e8f0;
        width: 100%;
        text-align: center;
    }
    .arch-node-lead { border-color: #818cf8; color: #c7d2fe; }
    .arch-node-scout { border-color: #38bdf8; color: #bae6fd; }
    .arch-node-auditor { border-color: #f59e0b; color: #fde68a; }
    .arch-arrow {
        color: #64748b;
        font-size: 0.85rem;
        line-height: 1;
    }

    /* Handoff Trace Card */
    .handoff-card {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
        border-left: 4px solid #6366f1;
    }
    .handoff-card.lead_investigator { border-left-color: #818cf8; }
    .handoff-card.evidence_scout { border-left-color: #38bdf8; }
    .handoff-card.precedence_auditor { border-left-color: #f59e0b; }

    .handoff-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .agent-pill {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .pill-lead { background: #312e81; color: #c7d2fe; }
    .pill-scout { background: #0c4a6e; color: #bae6fd; }
    .pill-auditor { background: #78350f; color: #fde68a; }
    .pill-output { background: #064e3b; color: #a7f3d0; }

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
    """Create the MultiAgentArchaeologist.
    Falls back gracefully to require_llm=False if Ollama is unavailable.
    """
    try:
        return MultiAgentArchaeologist(dataset_dir=DATASET_DIR, require_llm=True), True
    except ConnectionError:
        return MultiAgentArchaeologist(dataset_dir=DATASET_DIR, require_llm=False), False


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
    st.caption("LLM-Backed Multi-Agent Investigation")

    st.markdown("---")

    # LLM status
    if llm_connected:
        st.success("🟢 Ollama connected (llama3:latest)", icon="✅")
    else:
        st.warning("🟡 Ollama offline — running deterministic heuristics", icon="⚠️")

    # Archive stats
    st.metric("Corporate Archive Documents", len(agent.archive.documents))
    st.metric("Indexed Passages", len(agent.archive.passages))

    st.markdown("---")

    # Architecture diagram
    st.markdown("##### Multi-Agent Architecture")
    st.markdown(
        """
        <div class="arch-flow">
            <div class="arch-node arch-node-lead">
                <strong>1. Lead Investigator</strong><br>
                <span style="font-size:0.7rem; font-weight:normal;">Intent &amp; Search Mission Delegation</span>
            </div>
            <div class="arch-arrow">↓ <em>task_assignment</em></div>
            <div class="arch-node arch-node-scout">
                <strong>2. Evidence Scout</strong><br>
                <span style="font-size:0.7rem; font-weight:normal;">Autonomous Multi-Round Tool Retrieval</span>
            </div>
            <div class="arch-arrow">↓ <em>evidence_packet</em></div>
            <div class="arch-node arch-node-auditor">
                <strong>3. Precedence Auditor</strong><br>
                <span style="font-size:0.7rem; font-weight:normal;">Contradiction &amp; Authority Evaluation</span>
            </div>
            <div class="arch-arrow">↓ <em>audit_report</em></div>
            <div class="arch-node arch-node-lead">
                <strong>4. Lead Investigator</strong><br>
                <span style="font-size:0.7rem; font-weight:normal;">Grounded Synthesis &amp; Abstention</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Each agent operates with genuine responsibilities over shared "
        "`InvestigationState`, backed by local Ollama LLM calls."
    )

    st.markdown("---")

    # Navigation
    tab_choice = st.radio(
        "Navigation",
        ["🔍 Multi-Agent Workbench", "📁 Archive Catalog"],
        label_visibility="collapsed",
    )


# ---------------------------------------------------------------------------
# Helpers for agent labels
# ---------------------------------------------------------------------------
def _agent_pill(name: str) -> str:
    n = name.lower()
    if "lead" in n:
        return '<span class="agent-pill pill-lead">Lead Investigator</span>'
    elif "scout" in n:
        return '<span class="agent-pill pill-scout">Evidence Scout</span>'
    elif "auditor" in n or "precedence" in n:
        return '<span class="agent-pill pill-auditor">Precedence Auditor</span>'
    elif "output" in n:
        return '<span class="agent-pill pill-output">Final Output</span>'
    return f'<span class="agent-pill">{name}</span>'


# ---------------------------------------------------------------------------
# Investigation Workbench
# ---------------------------------------------------------------------------
if tab_choice == "🔍 Multi-Agent Workbench":
    st.markdown(
        '<div class="main-header">Multi-Agent Investigation Workbench</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">'
        "Ask any question about Project Northstar. Three specialized agents collaborate "
        "autonomously over the document archive to uncover facts, reconcile conflicts, and report findings."
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
        with st.expander("💡 Example queries from evaluation benchmark"):
            for i, eq in enumerate(example_queries):
                if st.button(eq, key=f"eq_{i}", use_container_width=True):
                    st.session_state["prefill_query"] = eq
                    st.rerun()

    # Auto-fill from example click
    if "prefill_query" in st.session_state:
        user_query = st.session_state.pop("prefill_query")

    run_btn = st.button("🚀 Run Multi-Agent Investigation", type="primary", disabled=not user_query.strip())

    # -----------------------------------------------------------------------
    # Run investigation
    # -----------------------------------------------------------------------
    report: MultiAgentReport | None = None

    if run_btn and user_query.strip():
        with st.spinner("Lead Investigator, Evidence Scout, and Precedence Auditor collaborating…"):
            try:
                report = agent.investigate(user_query.strip())
                st.session_state["last_report"] = report
            except TimeoutError as te:
                st.warning(
                    f"⏱️ **LLM Investigation Response Delayed**: {te}\n\n"
                    "The local Ollama model took longer than expected to complete this step. "
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
        tab_handoffs, tab_answer, tab_evidence, tab_conflicts, tab_validation = st.tabs([
            "🤝 Agent Handoffs",
            "📋 Lead Synthesis",
            "📑 Scout Evidence",
            "⚖️ Auditor Contradictions",
            "✅ Validation & Citations",
        ])

        # --- Tab 1: Agent Handoffs & Inter-Agent Coordination ---
        with tab_handoffs:
            st.markdown("#### Inter-Agent Handoffs & Observable Workflow")
            st.caption(
                "Observable trace showing state transfers across agent boundaries in LangGraph."
            )

            # Display handoff progression
            for i, h in enumerate(report.handoff_log):
                from_pill = _agent_pill(h.get("from_agent", ""))
                to_pill = _agent_pill(h.get("to_agent", ""))
                summary = h.get("summary", "")
                keys = h.get("payload_keys", [])

                css_class = h.get("from_agent", "")
                st.markdown(
                    f"""
                    <div class="handoff-card {css_class}">
                        <div class="handoff-header">
                            <div><strong>Step {i + 1}:</strong> {from_pill} ➔ {to_pill}</div>
                            <span style="font-size:0.8rem; color:#94a3b8;">State keys: <code>{', '.join(keys)}</code></span>
                        </div>
                        <div style="font-size:0.95rem; color:#e2e8f0; margin-top:4px;">
                            {summary}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Detailed per-agent breakdown expander
            st.markdown("---")
            st.markdown("##### Agent Delegation & Discovery Breakdown")

            col_lead, col_scout, col_auditor = st.columns(3)

            with col_lead:
                st.markdown("**Lead Investigator Assignment**")
                if report.task_assignment:
                    st.json(report.task_assignment)
                else:
                    st.caption("No task assignment recorded.")

            with col_scout:
                st.markdown("**Evidence Scout Tool Steps**")
                if report.scout_steps:
                    for s in report.scout_steps:
                        st.markdown(f"• **Round {s.get('round')}:** `{s.get('log')}`")
                else:
                    st.caption("No scout steps recorded.")

            with col_auditor:
                st.markdown("**Precedence Auditor Reasoning**")
                reasoning = report.audit_report.get("audit_reasoning", "")
                if reasoning:
                    st.info(reasoning)
                else:
                    st.caption("Deterministic evaluation passed without additional reasoning remarks.")

        # --- Tab 2: Lead Investigator Final Synthesis ---
        with tab_answer:
            st.markdown("#### Grounded Synthesis (Lead Investigator)")
            st.markdown(report.summary_answer)

            if report.citations:
                st.markdown("---")
                st.markdown(f"**Verified Supporting Citations:** `{'`, `'.join(report.citations)}`")

        # --- Tab 3: Scout Evidence ---
        with tab_evidence:
            passages = report.evidence_packet.get("passages", [])
            st.markdown(
                f"#### Retrieved Evidence ({len(passages)} passages)"
            )
            inspected_docs = report.evidence_packet.get("inspected_docs", [])
            if inspected_docs:
                st.markdown(f"**Inspected Reference Documents:** `{'`, `'.join(inspected_docs)}`")

            for p in passages:
                with st.expander(
                    f"📍 [{p.get('passage_id')}] {p.get('filename')} — "
                    f"{p.get('title', '')} (score: {p.get('score', 'N/A')})"
                ):
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f"**Status:** `{p.get('status', 'N/A')}`")
                    c2.markdown(f"**Authority:** `{p.get('authority', 'N/A')}`")
                    c3.markdown(f"**Created:** `{p.get('created', 'N/A')}`")
                    st.markdown(f"**Section:** {p.get('section', '')}")
                    st.text(p.get("excerpt", ""))

        # --- Tab 4: Auditor Contradictions ---
        with tab_conflicts:
            st.markdown("#### Detected Precedence Contradictions & Temporal Resolutions")
            contradictions = report.audit_report.get("contradictions", [])
            if not contradictions:
                st.info("No conflicting claims or superseded decisions detected in the retrieved evidence.")
            else:
                for c in contradictions:
                    st.markdown(
                        f"""
                        <div class="contra-card">
                            <h4 style="color:#f59e0b; margin-top:0;">
                                ⚠️ {c.get('topic', 'Contradiction')}
                            </h4>
                            <p>
                                <strong>Claim A:</strong> {c.get('conflicting_claim_a')}
                                <br><em>Source:</em> {c.get('evidence_a')}
                            </p>
                            <p>
                                <strong>Claim B:</strong> {c.get('conflicting_claim_b')}
                                <br><em>Source:</em> {c.get('evidence_b')}
                            </p>
                            <div style="background:#1e293b; padding:10px;
                                        border-radius:6px; margin-top:8px;">
                                <strong>💡 Precedence Resolution:</strong><br>
                                {c.get('resolution')}
                                <br><small style="color:#94a3b8;">Authoritative source: <code>{c.get('authoritative_source')}</code></small>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            gaps = report.audit_report.get("unresolved_gaps", [])
            if gaps:
                st.markdown("##### 🔍 Identified Information Gaps")
                for gap in gaps:
                    st.warning(gap)

        # --- Tab 5: Validation & Citations ---
        with tab_validation:
            st.markdown("#### Citation Grounding & Epistemic Abstention")
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

            if report.is_abstained:
                st.error(f"🛑 Epistemic Abstention: {report.abstention_reason}")
            else:
                st.success("✅ Synthesis grounded within available archive records.")


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
        "<code>type</code> are <strong>document metadata</strong> describing editorial status."
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
