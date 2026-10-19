# Context Archaeologist 🧭

An autonomous **Agentic AI system** that investigates corporate workplace archives to reconstruct decision histories, uncover stale records and contradictions, trace cross-document dependencies, validate citations, and honestly report unresolved questions.

Unlike standard chatbots or generic RAG systems that blindly retrieve isolated chunks and guess answers, **Context Archaeologist** exhibits genuine agentic behavior:
- **Autonomous Multi-Stage Pipeline:** Plans searches, executes targeted tool calls, and performs conditional follow-up queries when evidence is incomplete or references superseded decisions.
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

### 2. Run the Evaluation Suite
Verify all 10 evaluation scenarios:
```powershell
python -m pytest tests/test_scenarios.py -v
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

---

## 🏗️ Architecture & Modules

```
ContextArchaeologist/
├── app.py                                # Modern Streamlit Interactive Workbench
├── progress.md                           # Progress log and milestone audit report
├── README.md                             # Documentation & 5-minute demo guide
├── src/
│   ├── ingestion.py                      # Clean document & passage ingestion engine
│   ├── tools.py                          # Real Python tools (search, traverse, validate)
│   ├── reasoner.py                       # Temporal & authority contradiction engine
│   └── orchestrator.py                   # Multi-stage agent orchestrator
├── tests/
│   └── test_scenarios.py                 # Automated pytest suite (10/10 scenarios)
└── context_archaeologist_dataset/        # Audited Northstar synthetic corporate archive
    ├── documents/                        # 12 workplace Markdown/TXT records
    ├── metadata/                         # Manifest, passage indices, claim graphs
    ├── evaluation/                       # 10 ground truth evaluation scenarios
    └── scripts/                          # Dataset validation script
```

---

## 🛡️ Evaluation Isolation
The live agent pipeline in `src/` loads only public document records and the manifest (`documents/`, `metadata/document_manifest.json`, `metadata/passage_index.json`). It **never** ingests or accesses `ground_truth/`, `evaluation/`, or `claim_evidence_map.json`.