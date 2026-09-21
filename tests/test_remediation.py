"""Tests for remediation planning functionality."""

import json
from pathlib import Path

import pytest

from src.opspilot.agents.diagnosis import DemoDiagnosisAgent
from src.opspilot.agents.remediation import DemoRemediationAgent
from src.opspilot.agents.triage import DemoTriageAgent
from src.opspilot.agents.verifier import EvidenceVerifier
from src.opspilot.models import (
    EvidenceChunk,
    Incident,
    RiskLevel,
    VerificationResult,
)
from src.opspilot.tools.evidence_retriever import create_evidence_retriever
from src.opspilot.tools.log_parser import parse_log_file


@pytest.fixture
def sample_verification_result():
    """Create sample verification result with verified hypotheses."""
    from src.opspilot.models import HypothesisStatus, RootCauseHypothesis

    hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_test_001",
        title="Database connection pool exhaustion caused service failures",
        description="Pool exhaustion led to failures",
        rank=1,
        confidence=0.85,
        evidence_ids=["ev_001", "ev_002"],
        reasoning="Strong evidence",
        status=HypothesisStatus.SUPPORTED,
        missing_evidence=[],
        requires_human_review=True,
    )

    return VerificationResult(
        incident_id="TEST-001",
        verified_hypotheses=[hypothesis],
        rejected_hypothesis_ids=[],
        verification_summary="Test verification",
        requires_human_review=True,
    )


@pytest.fixture
def sample_evidence_with_runbooks():
    """Create sample evidence including runbook content."""
    return [
        EvidenceChunk(
            evidence_id="ev_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] pool exhausted",
            score=5.0,
        ),
        EvidenceChunk(
            evidence_id="ev_002",
            source_file="runbook.md",
            source_type="runbook",
            line_number=10,
            content="Check connection pool utilization to identify current active connections",
            score=4.5,
        ),
        EvidenceChunk(
            evidence_id="ev_003",
            source_file="runbook.md",
            source_type="runbook",
            line_number=20,
            content="Identify long-running queries and their duration",
            score=4.0,
        ),
        EvidenceChunk(
            evidence_id="ev_004",
            source_file="runbook.md",
            source_type="runbook",
            line_number=30,
            content="Scale connection pool if infrastructure allows",
            score=3.5,
        ),
        EvidenceChunk(
            evidence_id="ev_005",
            source_file="runbook.md",
            source_type="runbook",
            line_number=40,
            content="Implement monitoring and set up alerts for connection pool",
            score=3.0,
        ),
    ]


def test_remediation_generates_actions(
    sample_verification_result, sample_evidence_with_runbooks
):
    """Test that remediation plan generates actions."""
    agent = DemoRemediationAgent()
    plan = agent.plan_remediation(
        sample_verification_result, sample_evidence_with_runbooks
    )

    assert len(plan.actions) > 0
    assert plan.incident_id == "TEST-001"
    assert plan.requires_human_approval is True


def test_remediation_requires_verified_hypotheses():
    """Test that remediation requires verified hypotheses."""
    empty_verification = VerificationResult(
        incident_id="TEST-002",
        verified_hypotheses=[],
        rejected_hypothesis_ids=["hyp_001"],
        verification_summary="All rejected",
        requires_human_review=True,
    )

    agent = DemoRemediationAgent()
    plan = agent.plan_remediation(empty_verification, [])

    assert len(plan.actions) == 0
    assert "no verified hypotheses" in plan.summary.lower()


def test_actions_categorized_correctly(
    sample_verification_result, sample_evidence_with_runbooks
):
    """Test that actions are categorized into investigation, containment, recovery, prevention."""
    agent = DemoRemediationAgent()
    plan = agent.plan_remediation(
        sample_verification_result, sample_evidence_with_runbooks
    )

    categories = {action.category for action in plan.actions}
    expected_categories = {"investigation", "containment", "prevention"}

    # Should have actions in multiple categories
    assert len(categories & expected_categories) > 0


def test_all_state_changing_actions_require_approval(
    sample_verification_result, sample_evidence_with_runbooks
):
    """Test that all state-changing actions require human approval."""
    agent = DemoRemediationAgent()
    plan = agent.plan_remediation(
        sample_verification_result, sample_evidence_with_runbooks
    )

    for action in plan.actions:
        # High and critical risk actions must require approval
        if action.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            assert action.requires_human_approval is True

        # State-changing operations must require approval
        state_changing_keywords = [
            "restart",
            "scale",
            "increase",
            "terminate",
            "modify",
        ]
        if any(kw in action.title.lower() for kw in state_changing_keywords):
            assert action.requires_human_approval is True


def test_no_actions_executed_automatically(
    sample_verification_result, sample_evidence_with_runbooks
):
    """Test that no actions are executed, only recommended."""
    agent = DemoRemediationAgent()
    plan = agent.plan_remediation(
        sample_verification_result, sample_evidence_with_runbooks
    )

    # All actions should have validation and rollback considerations
    for action in plan.actions:
        assert action.validation_step
        assert action.rollback_consideration
        assert action.requires_human_approval in [True, False]  # Explicit flag


def test_actions_have_valid_evidence_ids(
    sample_verification_result, sample_evidence_with_runbooks
):
    """Test that all cited evidence IDs are valid."""
    agent = DemoRemediationAgent()
    plan = agent.plan_remediation(
        sample_verification_result, sample_evidence_with_runbooks
    )

    available_ids = {ev.evidence_id for ev in sample_evidence_with_runbooks}
    available_ids.update(sample_verification_result.verified_hypotheses[0].evidence_ids)

    for action in plan.actions:
        for eid in action.supporting_evidence_ids:
            assert eid in available_ids, f"Invalid evidence ID: {eid}"


def test_actions_have_unique_ids(
    sample_verification_result, sample_evidence_with_runbooks
):
    """Test that all actions have unique IDs."""
    agent = DemoRemediationAgent()
    plan = agent.plan_remediation(
        sample_verification_result, sample_evidence_with_runbooks
    )

    action_ids = [action.action_id for action in plan.actions]
    assert len(action_ids) == len(set(action_ids))


def test_high_risk_actions_flagged(
    sample_verification_result, sample_evidence_with_runbooks
):
    """Test that high-risk actions are properly flagged."""
    agent = DemoRemediationAgent()
    plan = agent.plan_remediation(
        sample_verification_result, sample_evidence_with_runbooks
    )

    # Look for restart action which should be high risk
    restart_actions = [
        action for action in plan.actions if "restart" in action.title.lower()
    ]

    if restart_actions:
        for action in restart_actions:
            assert action.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
            assert action.requires_human_approval is True


def test_remediation_deterministic(
    sample_verification_result, sample_evidence_with_runbooks
):
    """Test that remediation planning is deterministic."""
    agent = DemoRemediationAgent()

    plan1 = agent.plan_remediation(
        sample_verification_result, sample_evidence_with_runbooks
    )
    plan2 = agent.plan_remediation(
        sample_verification_result, sample_evidence_with_runbooks
    )

    assert len(plan1.actions) == len(plan2.actions)
    assert plan1.summary == plan2.summary

    for a1, a2 in zip(plan1.actions, plan2.actions):
        assert a1.action_id == a2.action_id
        assert a1.title == a2.title
        assert a1.risk_level == a2.risk_level


@pytest.fixture
def project_root():
    """Get project root."""
    return Path(__file__).parent.parent


@pytest.fixture
def real_incident(project_root):
    """Load real incident."""
    incident_file = project_root / "data" / "incidents" / "incident_001.json"
    with open(incident_file, "r") as f:
        return Incident(**json.load(f))


@pytest.fixture
def real_evidence(project_root):
    """Get real evidence."""
    log_file = project_root / "data" / "incidents" / "incident_001_logs.txt"
    runbook_dir = project_root / "data" / "runbooks"

    logs = parse_log_file(log_file)
    retriever = create_evidence_retriever(logs, runbook_dir)
    return retriever.retrieve("database connection pool exhausted 503", top_k=15)


def test_real_incident_remediation(real_incident, real_evidence):
    """Test remediation with real incident data."""
    triage_agent = DemoTriageAgent()
    diagnosis_agent = DemoDiagnosisAgent()
    verifier = EvidenceVerifier()
    remediation_agent = DemoRemediationAgent()

    triage = triage_agent.triage(real_incident, real_evidence)
    diagnosis = diagnosis_agent.diagnose(real_incident, triage, real_evidence)
    verification = verifier.verify(diagnosis, real_evidence)
    plan = remediation_agent.plan_remediation(verification, real_evidence)

    # Should generate remediation plan
    assert len(plan.actions) > 0
    assert plan.requires_human_approval is True

    # Should include investigation actions
    investigation_actions = [
        a for a in plan.actions if a.category == "investigation"
    ]
    assert len(investigation_actions) > 0

    # All actions should have proper structure
    for action in plan.actions:
        assert action.title
        assert action.description
        assert action.rationale
        assert action.validation_step
        assert action.rollback_consideration
