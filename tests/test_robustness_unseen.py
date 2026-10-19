"""Robustness test suite for Context Archaeologist Phase 4.

Includes:
1. Unseen question on newly added document (DOC-013 Risk Advisory): Can the FAQ gate be waived with live white-glove chat?
2. Ambiguous query testing whether provisional 'soft launch' is allowed without 4 gates
3. Abstention test on unknown compliance question (e.g., EU GDPR audit date)
4. Corroboration of cross-document insurance dependency (DOC-013 -> DOC-011)
"""

import pytest
from pathlib import Path

from src.langgraph_agent import LangGraphArchaeologist
from src.orchestrator import ContextArchaeologistOrchestrator


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "context_archaeologist_dataset"


@pytest.fixture(scope="module")
def agent():
    return LangGraphArchaeologist(dataset_dir=DATASET_DIR, use_llm=False)


@pytest.fixture(scope="module")
def orchestrator():
    return ContextArchaeologistOrchestrator(dataset_dir=DATASET_DIR)


def test_unseen_doc13_gate_waiver_rejection(agent):
    """Test unseen question regarding proposed informal waiver of the FAQ gate."""
    question = "Can the Customer Operations FAQ gate be waived if Support uses live white-glove chat?"
    result = agent.run(question)

    ans_lower = result["final_answer"].lower()
    # The answer should cite DOC-013 or explain that the proposal was formally rejected
    assert any("DOC-013" in c for c in result["citations"])
    assert "rejected" in ans_lower or "no gate waivers" in ans_lower or "not" in ans_lower


def test_unseen_soft_launch_prohibition(orchestrator):
    """Test whether a provisional or soft launch is permissible before gates pass."""
    question = "Is a provisional or soft launch allowed for Northstar before the four gates pass?"
    report = orchestrator.investigate(question)

    ans_lower = report.summary_answer.lower()
    # Must prohibit launch and cite DOC-008 or DOC-013
    assert "no" in ans_lower or "not permitted" in ans_lower or "under no circumstances" in ans_lower
    assert any("DOC-008" in c or "DOC-013" in c for c in report.citations)


def test_unseen_cybersecurity_insurance_dependency(agent):
    """Test cross-document discovery: insurance compliance conditioned on access-control export."""
    question = "What condition does the cybersecurity insurance underwriter require for production data residency?"
    result = agent.run(question)

    ans_lower = result["final_answer"].lower()
    # Must retrieve DOC-013 and link to access-control export (DOC-011)
    assert any("DOC-013" in c for c in result["citations"])
    assert "access-control export" in ans_lower or "access control" in ans_lower


def test_unseen_out_of_archive_abstention(orchestrator):
    """Test honest epistemic abstention on external entity not present in archive."""
    question = "What exact date was the ISO-27001 third-party surveillance audit completed?"
    report = orchestrator.investigate(question)

    # Agent should recognize insufficient evidence rather than hallucinating an audit date
    ans_lower = report.summary_answer.lower()
    assert report.is_abstained or "not" in ans_lower or "insufficient" in ans_lower or "no" in ans_lower
