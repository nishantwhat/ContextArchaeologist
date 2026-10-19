"""End-to-end evaluation suite for Context Archaeologist across 10 scenarios.

Tests compliance with:
- Required passages and claim groundings
- Stale / conflicting document handling
- Avoidance checks (no false approvals or date hallucinations)
- Epistemic abstention on missing evidence
"""

import json
from pathlib import Path
import pytest

from src.orchestrator import ContextArchaeologistOrchestrator


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "context_archaeologist_dataset"


@pytest.fixture(scope="module")
def orchestrator():
    return ContextArchaeologistOrchestrator(dataset_dir=DATASET_DIR)


@pytest.fixture(scope="module")
def eval_scenarios():
    q_file = DATASET_DIR / "evaluation" / "evaluation_questions.json"
    with open(q_file, "r", encoding="utf-8") as f:
        return json.load(f)["scenarios"]


def test_eval_01_original_launch_target(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-01")
    report = orchestrator.investigate(s["question"])

    assert "20 April" in report.summary_answer
    assert "planning target" in report.summary_answer.lower() or "not a customer commitment" in report.summary_answer.lower()
    # Avoid calling 20 April the current date
    assert "not the current" in report.summary_answer.lower() or "withdrawn" in report.summary_answer.lower()
    assert any("DOC-001" in c for c in report.citations)


def test_eval_02_preventing_launch_and_four_gates(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-02")
    report = orchestrator.investigate(s["question"])

    ans_lower = report.summary_answer.lower()
    assert "four gates" in ans_lower or "4" in ans_lower
    assert "product" in ans_lower
    assert "recovery" in ans_lower
    assert "security" in ans_lower
    assert "customer operations" in ans_lower or "support" in ans_lower
    assert "no date is authorized" in ans_lower or "no date" in ans_lower
    # Avoid treating recovery as passed or security as approved
    assert "not approved" in ans_lower or "unapproved" in ans_lower


def test_eval_03_timeline_reconstruction(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-03")
    report = orchestrator.investigate(s["question"])

    ans = report.summary_answer
    assert "20 April" in ans
    assert "11 May" in ans
    assert "withdrew" in ans.lower() or "withdrawn" in ans.lower()
    assert "DOC-008" in ans
    assert "DOC-003" in ans


def test_eval_04_draft_calendar_unapproved(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-04")
    report = orchestrator.investigate(s["question"])

    ans_lower = report.summary_answer.lower()
    assert "no" in ans_lower
    assert "draft" in ans_lower
    assert "placeholder" in ans_lower
    assert "withdrawn" in ans_lower or "superseded" in ans_lower


def test_eval_05_support_is_ready_reconciliation(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-05")
    report = orchestrator.investigate(s["question"])

    ans_lower = report.summary_answer.lower()
    assert "not complete" in ans_lower or "incomplete" in ans_lower
    assert "draft" in ans_lower
    assert "rota" in ans_lower


def test_eval_06_security_missing_artifacts(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-06")
    report = orchestrator.investigate(s["question"])

    ans_lower = report.summary_answer.lower()
    assert "recovery rehearsal run record" in ans_lower or "run record" in ans_lower
    assert "access-control export" in ans_lower
    assert "no production approval" in ans_lower or "not approved" in ans_lower


def test_eval_07_recovery_rehearsal_abstention(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-07")
    report = orchestrator.investigate(s["question"])

    assert report.is_abstained is True
    ans_lower = report.summary_answer.lower()
    assert "abstention" in ans_lower or "unknown" in ans_lower or "insufficient evidence" in ans_lower
    assert "DOC-010" in report.summary_answer


def test_eval_08_exact_future_date_abstention(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-08")
    report = orchestrator.investigate(s["question"])

    assert report.is_abstained is True
    ans_lower = report.summary_answer.lower()
    assert "cannot state" in ans_lower or "no date authorized" in ans_lower or "abstention" in ans_lower


def test_eval_09_may_launch_remains_possible(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-09")
    report = orchestrator.investigate(s["question"])

    ans_lower = report.summary_answer.lower()
    assert "not" in ans_lower
    assert "possibility" in ans_lower
    assert "DOC-008" in report.summary_answer


def test_eval_10_corroboration_baseline_vs_kickoff(orchestrator, eval_scenarios):
    s = next(x for x in eval_scenarios if x["scenario_id"] == "EVAL-10")
    report = orchestrator.investigate(s["question"])

    ans_lower = report.summary_answer.lower()
    assert "planning target" in ans_lower
    assert "not a customer commitment" in ans_lower or "not a contractual commitment" in ans_lower
    assert any("DOC-001" in c for c in report.citations)
    assert any("DOC-002" in c for c in report.citations)
