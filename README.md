# Context Archaeologist 🧭

An autonomous **Agentic AI system** that investigates corporate workplace archives to reconstruct decision histories, uncover stale records and contradictions, trace cross-document dependencies, validate citations, and honestly report unresolved questions.

Unlike standard chatbots or generic RAG systems that blindly retrieve isolated chunks and guess answers, **Context Archaeologist** exhibits genuine agentic behavior:
- **LangGraph Stateful Agent:** Iterative investigation graph (`Planner -> Tool Execution -> Intermediate Evaluator -> Conditional Routing -> Synthesis`).
- **Autonomous Tool Selection:** The agent dynamically decides whether to search, inspect document metadata, traverse cross-document references, or inspect timelines.
- **Local LLM Backend:** Native integration with local **Ollama** running `llama3:latest` (8.0B parameters) with factual temperature and JSON schema generation.
- **Temporal & Authority Reasoner:** Reconciles formal decisions against informal chat claims, distinguishing between drafts, baseline plans, and binding Launch Council decisions.
- **Epistemic Humility & Abstention:** Detects missing artifacts (e.g. absent recovery run records) and abstains rather than hallucinating dates or pass/fail outcomes.
- **100% Citation Grounding:** Verifies cited passages against the public document manifest to eliminate hallucinated references.

---

## 🚀 Quick Start Instructions

The project uses Python (tested on Python 3.14 / 3.11+) and your local virtual environment.

### 1. Run the Streamlit Application
Launch the web interface:
```powershell
python -m streamlit run app.py
```
Open your browser at `http://localhost:8501`.
- Use the sidebar toggle to switch between **⚡ Fast Grounded Pipeline** and **🔄 LangGraph Stateful Loop**.

### 2. Run the Evaluation Suite
Verify both the original 10 evaluation scenarios and the new unseen robustness test suite:
```powershell
# Run original 10 scenarios
python -m pytest tests/test_scenarios.py -v

# Run Phase 4 unseen robustness scenarios
python -m pytest tests/test_robustness_unseen.py -v
```

---

## 🎯 Five-Minute Demo Walkthrough

### Scenario A: Complex Synthesis & Missing Gates (EVAL-02)
- **Question:** *"What is preventing Northstar from receiving a launch date now? Identify the gates and the evidence currently missing."*
- **What to look for in the UI:**
  1. Open the **Investigation Workbench** and select `EVAL-02`. Click **Run Investigation**.
  2. Inspect the **Executive Investigation Report**: The agent explains that no date is authorized under `DOC-008` and lists all 4 incomplete release gates (Product conditional in `DOC-009`, Recovery rehearsal run record missing in `DOC-004`/`DOC-010`, Security unapproved in `DOC-006`/`DOC-011`, and Customer Ops rota unfrozen in `DOC-005`).
  3. Expand **Agent Tool Calls & Reasoning Trace**: Notice the initial `search_archive` followed by the **conditional follow-up tool calls** tracing the recovery run record and security dependencies.
  4. Expand **Mandatory Gates**: See the four real-time status badges and the specific unresolved questions.

### Scenario B: Contradiction Reconciliation (EVAL-05)
- **Question:** *"One record says Support is ready, while the launch decision requires Customer Operations readiness. Is that gate complete?"*
- **What to look for in the UI:**
  1. Select `EVAL-05` and click **Run Investigation**.
  2. Switch to the **⚖️ Contradiction Reconciliation** tab.
  3. Note how the agent detects the conflict between the informal sync chat (*"Support is ready"*) in `DOC-005` and the formal gate requirement in `DOC-008` (*rota frozen and FAQ approved*).
  4. The agent resolves the conflict by contextualizing the informal remark as draft preparation, concluding that the formal gate is **not complete**.

### Scenario C: Epistemic Abstention (EVAL-07)
- **Question:** *"Did the second recovery rehearsal pass the 60-minute objective and data-integrity checks?"*
- **What to look for in the UI:**
  1. Select `EVAL-07` and click **Run Investigation**.
  2. Observe the prominent purple banner: **🛑 Epistemic Abstention Triggered**.
  3. The agent detects that although an informal chat (`DOC-010`) mentioned a restore that *"looked much faster"*, the final elapsed-time figure and integrity run record are missing from the archive (`DOC-004`, `DOC-011`).
  4. The agent explicitly abstains from declaring pass or fail, demonstrating honest epistemic bounds.

### Scenario D: Unseen Robustness & Gate Waiver Rejection (Phase 4)
- **Question:** *"Can the Customer Operations FAQ gate be waived if Support uses live white-glove chat?"*
- **What to look for in the UI:**
  1. Select **Custom User Query...** and paste the question.
  2. The agent retrieves new record `DOC-013` (Operational Risk Addendum).
  3. The agent identifies that Chief Risk Officer Marcus Vance formally evaluated and rejected the informal waiver proposal, citing that no gate waivers are permitted under Asterion Works' compliance rules.

---

## 🏗️ Architecture & Modules

```
ContextArchaeologist/
├── app.py                                # Streamlit UI with LangGraph engine toggle
├── progress.md                           # Comprehensive progress and audit log
├── README.md                             # Documentation & 5-minute demo guide
├── src/
│   ├── ingestion.py                      # Clean document & passage ingestion engine
│   ├── tools.py                          # Real Python tools (search, traverse, validate)
│   ├── reasoner.py                       # Temporal & authority contradiction engine
│   ├── llm_client.py                     # Local Ollama client (llama3:latest integration)
│   ├── langgraph_agent.py                # Stateful LangGraph investigation loop
│   └── orchestrator.py                   # Grounded multi-stage orchestrator
├── tests/
│   ├── test_scenarios.py                 # Original 10 evaluation scenarios (10/10 PASS)
│   └── test_robustness_unseen.py         # Phase 4 unseen robustness scenarios (4/4 PASS)
└── context_archaeologist_dataset/        # Northstar corporate archive
    ├── documents/                        # 13 workplace Markdown/TXT records (incl. DOC-013)
    ├── metadata/                         # Manifest, passage indices, claim graphs
    ├── evaluation/                       # 10 ground truth evaluation scenarios
    └── scripts/                          # Dataset validation script
```

---

## 🛡️ Evaluation Isolation
The live agent pipeline in `src/` loads only public document records and the manifest (`documents/`, `metadata/document_manifest.json`, `metadata/passage_index.json`). It **never** ingests or accesses `ground_truth/`, `evaluation/`, or `claim_evidence_map.json`.