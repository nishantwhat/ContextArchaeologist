"""Context Archaeologist — Interactive Streamlit Application.

Demonstrates genuine agentic behavior:
- Tool execution timeline and reasoning step inspection
- Dynamic cross-document dependency and citation graph
- Epistemic clarity: Contradiction resolution, status checks, and honest abstention
"""

from __future__ import annotations

import json
from pathlib import Path
import streamlit as st
import pandas as pd

from src.orchestrator import ContextArchaeologistOrchestrator


ROOT = Path(__file__).resolve().parent
DATASET_DIR = ROOT / "context_archaeologist_dataset"

st.set_page_config(
    page_title="Context Archaeologist | Agentic AI Workplace Investigation",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for modern dark / polished feel
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .badge-gate {
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        margin-bottom: 4px;
    }
    .gate-conditional { background-color: #713f12; color: #fde047; }
    .gate-unproven { background-color: #831843; color: #f472b6; }
    .gate-unapproved { background-color: #450a0a; color: #f87171; }
    .gate-incomplete { background-color: #1e293b; color: #cbd5e1; border: 1px solid #475569; }
    .contra-card {
        background-color: #0f172a;
        border-left: 4px solid #f59e0b;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 12px;
    }
    .abstain-card {
        background-color: #1e1b4b;
        border-left: 4px solid #818cf8;
        padding: 14px 18px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 16px;
    }
    .step-box {
        background-color: #020617;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_orchestrator():
    return ContextArchaeologistOrchestrator(dataset_dir=DATASET_DIR)


@st.cache_data
def load_sample_scenarios():
    eval_file = DATASET_DIR / "evaluation" / "evaluation_questions.json"
    if eval_file.exists():
        with open(eval_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("scenarios", [])
    return []


orchestrator = get_orchestrator()
scenarios = load_sample_scenarios()

# Sidebar Navigation & Archive Inspector
with st.sidebar:
    st.image("https://api.iconify.design/lucide:compass.svg?color=%23818cf8&width=48", width=48)
    st.title("Archive Controls")

    tab_choice = st.radio("Navigation", ["🔍 Investigation Workbench", "📁 Archive Catalog", "📊 Decision Gates"])

    st.markdown("---")
    st.caption("⚡ **Context Archaeologist v1.0**")
    st.caption("Agentic Investigation & Decision Reconstruction")
    st.caption(f"Archived Documents: **{len(orchestrator.archive.documents)}**")
    st.caption(f"Indexed Passages: **{len(orchestrator.archive.passages)}**")

    st.markdown("---")
    st.subheader("💡 Core Agent Features")
    st.markdown("- **Multi-Stage Investigation**: Plan -> Retrieve -> Follow-up -> Reconcile -> Validate")
    st.markdown("- **Conditional Retrieval**: Dynamic tool calls on superseded records")
    st.markdown("- **Contradiction Resolution**: Weighs formal decision vs chat")
    st.markdown("- **Epistemic Abstention**: Refuses to hallucinate missing facts")


if tab_choice == "🔍 Investigation Workbench":
    st.markdown('<div class="main-header">Context Archaeologist</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Autonomous Agentic System for Reconstructing Workplace Decisions & Uncovering Contradictions</div>',
        unsafe_allow_html=True,
    )

    # Question selection or custom input
    scenario_titles = [f"{s['scenario_id']}: {s['question']}" for s in scenarios]
    scenario_titles.insert(0, "Custom User Query...")

    selected_option = st.selectbox("Select an Investigation Scenario or enter your own query:", scenario_titles)

    if selected_option == "Custom User Query...":
        user_query = st.text_area("Enter corporate question to investigate:", value="What is preventing Northstar from receiving a launch date now? Identify the gates and the evidence currently missing.")
    else:
        chosen_scen = next(s for s in scenarios if f"{s['scenario_id']}: {s['question']}" == selected_option)
        user_query = chosen_scen["question"]
        st.info(f"**Scenario Type:** `{chosen_scen['type']}` | **Expected Behavior:** {', '.join(chosen_scen.get('observable_checks', []))}")

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        run_investigation = st.button("🚀 Run Investigation", type="primary", use_container_width=True)

    if run_investigation or ("last_report" in st.session_state and st.session_state.get("last_query") == user_query):
        with st.spinner("Agent investigating archive across documents, dependencies, and gates..."):
            report = orchestrator.investigate(user_query)
            st.session_state["last_report"] = report
            st.session_state["last_query"] = user_query

        # Render Main Investigation Results
        st.markdown("### 📋 Executive Investigation Report")

        if report.is_abstained:
            st.markdown(
                f"""
                <div class="abstain-card">
                    <h4 style="color:#a5b4fc; margin-top:0;">🛑 Epistemic Abstention Triggered</h4>
                    <p style="margin-bottom:0;">{report.abstention_reason}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(report.summary_answer)

        # Tabs for Agent Deep-Dive
        tab_reasoning, tab_contradictions, tab_passages, tab_gates = st.tabs(
            ["🛠️ Agent Tool Calls & Reasoning Trace", "⚖️ Contradiction Reconciliation", "📑 Grounded Passages & Citations", "🚦 Mandatory Gates"]
        )

        with tab_reasoning:
            st.markdown("#### Autonomous Tool Calls & Pipeline Execution")
            st.caption("Context Archaeologist operates in verifiable stages, executing real Python tool calls and conditional follow-up queries.")

            for i, step in enumerate(report.steps):
                with st.expander(f"**{step.stage}** — Tool: `{step.tool_name}`", expanded=(i in [1, 2, 3])):
                    col_in, col_out = st.columns([1, 2])
                    with col_in:
                        st.markdown("**Arguments passed:**")
                        st.json(step.input_args)
                    with col_out:
                        st.markdown("**Execution Output:**")
                        st.markdown(f"> {step.output_summary}")

        with tab_contradictions:
            st.markdown("#### Detected Contradictions & Temporal Reconciliation")
            if not report.contradictions:
                st.write("No direct contradictory claims detected for this specific focus.")
            else:
                for c in report.contradictions:
                    st.markdown(
                        f"""
                        <div class="contra-card">
                            <h4 style="color:#f59e0b; margin-top:0;">⚠️ {c.topic}</h4>
                            <p><strong>Claim A:</strong> {c.conflicting_claim_a} <br><em>Source:</em> {c.evidence_a}</p>
                            <p><strong>Claim B:</strong> {c.conflicting_claim_b} <br><em>Source:</em> {c.evidence_b}</p>
                            <div style="background:#1e293b; padding:10px; border-radius:6px; margin-top:8px;">
                                <strong>💡 Resolution & Authority Precedence:</strong><br>{c.resolution}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        with tab_passages:
            st.markdown(f"#### Grounded Passages ({len(report.retrieved_passages)} retrieved)")
            st.write(f"**Verified Citations:** `{'`, `'.join(report.citations)}`")
            for p in report.retrieved_passages:
                with st.expander(f"📍 [{p['passage_id']}] {p['filename']} — {p['title']} (Score: {p.get('score', 'N/A')})"):
                    st.markdown(f"**Section:** {p['section']}")
                    st.markdown(f"**Date:** {p.get('created', 'N/A')} | **Status:** `{p.get('status', 'N/A')}`")
                    st.markdown(f"**Authority:** `{p.get('authority', 'N/A')}`")
                    st.text(p.get("excerpt", ""))

        with tab_gates:
            st.markdown("#### Mandatory Release Gates Status (Governed by DOC-008)")
            for g_name, g_desc in report.gate_status_summary.items():
                st.markdown(f"**{g_name}**")
                st.info(g_desc)

            if report.unresolved_questions:
                st.markdown("#### ❓ Unresolved Archival Questions")
                for uq in report.unresolved_questions:
                    st.warning(uq)


elif tab_choice == "📁 Archive Catalog":
    st.markdown('<div class="main-header">Archive Document Catalog</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Application-facing Workplace Archive (Northstar Project)</div>', unsafe_allow_html=True)

    docs = orchestrator.archive.list_all_documents()
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
    selected_doc_id = st.selectbox("Inspect Full Document Content:", [d.id for d in docs])
    if selected_doc_id:
        doc_details = orchestrator.tools.get_document_details(selected_doc_id)
        st.markdown(f"### {doc_details['title']} (`{doc_details['id']}`)")
        st.markdown(f"**Author:** {doc_details['author']} | **Created:** {doc_details['created']} | **Status:** `{doc_details['status']}`")
        st.code(doc_details["content"], language="markdown")


elif tab_choice == "📊 Decision Gates":
    st.markdown('<div class="main-header">Northstar Decision & Gate Tracker</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Timeline Analysis & Cross-Document Precedence</div>', unsafe_allow_html=True)

    timeline_items = orchestrator.tools.inspect_timeline()
    for item in timeline_items:
        with st.container():
            col_t1, col_t2 = st.columns([1, 4])
            with col_t1:
                st.markdown(f"### 📅 {item['date']}")
                st.caption(f"ID: `{item['document_id']}`")
            with col_t2:
                st.markdown(f"**{item['title']}**")
                st.markdown(f"Status: `{item['status']}` | Authority: `{item['authority']}`")
                st.caption(f"Author: {item['author']} | Type: {item['type']}")
            st.markdown("---")
