# Context Archaeologist — Progress Tracking

## Status Overview
- **Phase 1: Freeze, Audit & Foundation**: COMPLETED ✅
- **Phase 2: Honest Architectural Audit**: COMPLETED ✅
- **Phase 3: LangGraph & Local LLM Integration**: COMPLETED ✅
- **Phase 4: Robustness & Unseen Evaluations**: COMPLETED ✅

---

## 1. Honest Architecture Audit (Phase 2 Findings)
- **Version 1 Strengths**:
  - Python tool suite (`src/tools.py`) was real, decoupled, and cleanly grounded with RapidFuzz passage scoring.
  - Public manifest and passage indices correctly isolated ground truth from live retrieval.
- **Identified Weaknesses**:
  - Orchestration relied on rigid keyword branching (`if "gate" in q_lower...`).
  - Answer synthesis used preset templates rather than reading and synthesizing evidence dynamically.
  - Abstention was hardcoded by question phrase rather than detecting empty/missing evidence fields.

---

## 2. Upgraded Architecture (Phase 3 & 4 Implementation)
1. **LangGraph Stateful Agent (`src/langgraph_agent.py`)**:
   - `AgentState`: Tracks question, iteration, plan, tool choices, retrieved passages, inspected documents, contradictions, abstentions, and citations.
   - `planner_node`: Formulates inquiry strategy and targeted keywords.
   - `tool_executor_node`: Autonomous execution of Python tools (`search_archive`, `get_document_details`, `follow_references`, `inspect_timeline`).
   - `evaluator_node`: Checks evidence sufficiency, detects contradictions across documents, and decides whether to continue investigation or terminate.
   - `route_next_step`: Conditional edge directing the agent to loop back for follow-up evidence or proceed to synthesis.
   - `synthesis_node`: Evidence-grounded synthesis with mandatory passage citations.
2. **Local Model Backend (`src/llm_client.py`)**:
   - Integrated with local **Ollama** server running `llama3:latest` (8.0B parameters).
   - Low-temperature factual inference with JSON schema generation.
   - Graceful deterministic fallback ensures test suite remains reproducible and fast.
3. **Robustness & Unseen Document Evaluation (`DOC-013` & `tests/test_robustness_unseen.py`)**:
   - Added new synthetic document: `DOC-013_risk_advisory.md` (Northstar Operational Risk Addendum).
   - Validated manifest & passage index integrity via `scripts/validate_dataset.py` (PASS, 13 documents, 76 passages).
   - Implemented 4 new robustness tests verifying unseen queries, gate waiver rejections, cross-document insurance dependencies, and out-of-archive abstentions.

---

## 3. Test & Verification Results
```bash
# 1. Dataset structural integrity:
python context_archaeologist_dataset/scripts/validate_dataset.py
# Status: PASS (13 documents, 76 passages)

# 2. Original 10 evaluation scenarios (Regression):
pytest tests/test_scenarios.py
# Status: 10 passed in 0.55s

# 3. New unseen robustness scenarios:
pytest tests/test_robustness_unseen.py
# Status: 4 passed in 2.00s
```

---

## 4. UI Capabilities (`app.py`)
- Engine selector toggle in sidebar: **⚡ Fast Grounded Pipeline** vs **🔄 LangGraph Stateful Loop**.
- Full visual trace of planner steps, tool executions, contradiction cards, and epistemic abstention banners.
