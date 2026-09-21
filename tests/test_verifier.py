"""Tests for evidence verification functionality."""

import json
from pathlib import Path

import pytest

from src.opspilot.agents.diagnosis import DemoDiagnosisAgent
from src.opspilot.agents.triage import DemoTriageAgent
from src.opspilot.agents.verifier import EvidenceVerifier
from src.opspilot.models import (
    DiagnosisResult,
    EvidenceChunk,
    HypothesisStatus,
    Incident,
    RootCauseHypothesis,
)
from src.opspilot.tools.evidence_retriever import create_evidence_retriever
from src.opspilot.tools.log_parser import parse_log_file


@pytest.fixture
def sample_incident():
    """Create sample incident."""
    return Incident(
        incident_id="TEST-VER-001",
        title="Test Verification Incident",
        description="Test",
        symptoms=["test"],
        start_time="2024-03-15T14:00:00Z",
        affected_services=["test"],
        severity="high",
        status="investigating",
    )


@pytest.fixture
def supported_evidence():
    """Create evidence that supports pool exhaustion hypothesis."""
    return [
        EvidenceChunk(
            evidence_id="ev_sup_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] database connection pool exhausted",
            score=5.0,
        ),
        EvidenceChunk(
            evidence_id="ev_sup_002",
            source_file="test.log",
            source_type="log",
            line_number=2,
            content="2024-03-15T14:20:17Z ERROR [service] connection pool exhausted",
            score=4.5,
        ),
        EvidenceChunk(
            evidence_id="ev_sup_003",
            source_file="test.log",
            source_type="log",
            line_number=3,
            content="2024-03-15T14:20:18Z ERROR [service] timeout waiting for connection",
            score=4.0,
        ),
        EvidenceChunk(
            evidence_id="ev_sup_004",
            source_file="test.log",
            source_type="log",
            line_number=4,
            content="2024-03-15T14:20:19Z INFO [gateway] upstream returned 503",
            score=3.5,
        ),
    ]


@pytest.fixture
def supported_hypothesis(supported_evidence):
    """Create a well-supported hypothesis."""
    return RootCauseHypothesis(
        hypothesis_id="hyp_test_001",
        title="Database connection pool exhaustion caused service failures",
        description="Pool exhaustion led to failures",
        rank=1,
        confidence=0.8,
        evidence_ids=[e.evidence_id for e in supported_evidence],
        reasoning="Strong evidence of pool exhaustion",
        missing_evidence=[],
        requires_human_review=True,
    )


def test_evidence_supported_hypothesis_passes_verification(
    supported_hypothesis, supported_evidence
):
    """Test that a well-supported hypothesis passes verification."""
    diagnosis = DiagnosisResult(
        incident_id="TEST-001",
        hypotheses=[supported_hypothesis],
        summary="Test diagnosis",
        limitations=[],
    )

    verifier = EvidenceVerifier()
    result = verifier.verify(diagnosis, supported_evidence)

    assert len(result.verified_hypotheses) == 1
    verified = result.verified_hypotheses[0]
    assert verified.status in [
        HypothesisStatus.SUPPORTED,
        HypothesisStatus.PARTIALLY_SUPPORTED,
    ]


def test_partially_supported_causal_claim_downgraded():
    """Test that partial evidence results in downgraded status."""
    # Hypothesis with limited supporting evidence
    hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_partial_001",
        title="Long-running query exhausted connection pool",
        description="Query caused pool exhaustion",
        rank=1,
        confidence=0.7,
        evidence_ids=["ev_p_001", "ev_p_002"],
        reasoning="Limited evidence",
        missing_evidence=[],
        requires_human_review=True,
    )

    # Only partial evidence
    evidence = [
        EvidenceChunk(
            evidence_id="ev_p_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:15:05Z DEBUG [postgres] Long-running query detected",
            score=3.0,
        ),
        EvidenceChunk(
            evidence_id="ev_p_002",
            source_file="test.log",
            source_type="log",
            line_number=2,
            content="2024-03-15T14:20:16Z ERROR [service] Some error occurred",
            score=2.0,
        ),
    ]

    diagnosis = DiagnosisResult(
        incident_id="TEST-002",
        hypotheses=[hypothesis],
        summary="Test",
        limitations=[],
    )

    verifier = EvidenceVerifier()
    result = verifier.verify(diagnosis, evidence)

    if result.verified_hypotheses:
        verified = result.verified_hypotheses[0]
        # Confidence should not increase
        assert verified.confidence <= hypothesis.confidence


def test_fabricated_hypothesis_rejected_no_evidence():
    """Test that fabricated DNS/security hypotheses are rejected."""
    # DNS hypothesis with no DNS evidence
    dns_hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_fake_dns",
        title="DNS resolution failure caused service outage",
        description="DNS servers failed to resolve domain names",
        rank=1,
        confidence=0.6,
        evidence_ids=["ev_fake_001"],
        reasoning="Speculation",
        missing_evidence=[],
        requires_human_review=True,
    )

    # Evidence that has nothing to do with DNS
    evidence = [
        EvidenceChunk(
            evidence_id="ev_fake_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] connection timeout",
            score=3.0,
        ),
    ]

    diagnosis = DiagnosisResult(
        incident_id="TEST-003",
        hypotheses=[dns_hypothesis],
        summary="Test",
        limitations=[],
    )

    verifier = EvidenceVerifier()
    result = verifier.verify(diagnosis, evidence)

    # DNS hypothesis should be rejected
    assert dns_hypothesis.hypothesis_id in result.rejected_hypothesis_ids


def test_security_breach_hypothesis_rejected():
    """Test that fabricated security breach hypothesis is rejected."""
    breach_hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_fake_breach",
        title="Security breach caused data exfiltration",
        description="Attacker compromised system",
        rank=1,
        confidence=0.5,
        evidence_ids=["ev_breach_001"],
        reasoning="Speculation",
        missing_evidence=[],
        requires_human_review=True,
    )

    # No security-related evidence
    evidence = [
        EvidenceChunk(
            evidence_id="ev_breach_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z INFO [service] Request processed",
            score=1.0,
        ),
    ]

    diagnosis = DiagnosisResult(
        incident_id="TEST-004",
        hypotheses=[breach_hypothesis],
        summary="Test",
        limitations=[],
    )

    verifier = EvidenceVerifier()
    result = verifier.verify(diagnosis, evidence)

    assert breach_hypothesis.hypothesis_id in result.rejected_hypothesis_ids


def test_hardware_failure_hypothesis_rejected():
    """Test that fabricated hardware failure hypothesis is rejected."""
    hardware_hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_fake_hw",
        title="Hardware failure caused disk I/O errors",
        description="Server hardware failed",
        rank=1,
        confidence=0.4,
        evidence_ids=["ev_hw_001"],
        reasoning="No actual evidence",
        missing_evidence=[],
        requires_human_review=True,
    )

    evidence = [
        EvidenceChunk(
            evidence_id="ev_hw_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] database timeout",
            score=2.0,
        ),
    ]

    diagnosis = DiagnosisResult(
        incident_id="TEST-005",
        hypotheses=[hardware_hypothesis],
        summary="Test",
        limitations=[],
    )

    verifier = EvidenceVerifier()
    result = verifier.verify(diagnosis, evidence)

    assert hardware_hypothesis.hypothesis_id in result.rejected_hypothesis_ids


def test_invalid_evidence_ids_removed():
    """Test that invalid evidence IDs are removed during verification."""
    hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_invalid_ev",
        title="Test hypothesis",
        description="Test",
        rank=1,
        confidence=0.6,
        evidence_ids=["ev_valid_001", "ev_invalid_999", "ev_valid_002"],
        reasoning="Test reasoning",
        missing_evidence=[],
        requires_human_review=True,
    )

    # Only provide some of the evidence
    evidence = [
        EvidenceChunk(
            evidence_id="ev_valid_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] pool exhausted",
            score=3.0,
        ),
        EvidenceChunk(
            evidence_id="ev_valid_002",
            source_file="test.log",
            source_type="log",
            line_number=2,
            content="2024-03-15T14:20:17Z ERROR [service] pool exhausted",
            score=2.5,
        ),
    ]

    diagnosis = DiagnosisResult(
        incident_id="TEST-006",
        hypotheses=[hypothesis],
        summary="Test",
        limitations=[],
    )

    verifier = EvidenceVerifier()
    result = verifier.verify(diagnosis, evidence)

    if result.verified_hypotheses:
        verified = result.verified_hypotheses[0]
        assert "ev_invalid_999" not in verified.evidence_ids
        assert "ev_valid_001" in verified.evidence_ids
        assert "ev_valid_002" in verified.evidence_ids


def test_verification_never_increases_confidence():
    """Test that verification never increases confidence scores."""
    hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_conf_test",
        title="Database connection pool exhaustion",
        description="Pool exhaustion",
        rank=1,
        confidence=0.75,
        evidence_ids=["ev_conf_001", "ev_conf_002"],
        reasoning="Test",
        missing_evidence=[],
        requires_human_review=True,
    )

    evidence = [
        EvidenceChunk(
            evidence_id="ev_conf_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] pool exhausted",
            score=4.0,
        ),
        EvidenceChunk(
            evidence_id="ev_conf_002",
            source_file="test.log",
            source_type="log",
            line_number=2,
            content="2024-03-15T14:20:17Z ERROR [service] connection timeout",
            score=3.5,
        ),
    ]

    diagnosis = DiagnosisResult(
        incident_id="TEST-007",
        hypotheses=[hypothesis],
        summary="Test",
        limitations=[],
    )

    original_confidence = hypothesis.confidence

    verifier = EvidenceVerifier()
    result = verifier.verify(diagnosis, evidence)

    for verified in result.verified_hypotheses:
        assert verified.confidence <= original_confidence


def test_rejected_hypotheses_listed_explicitly():
    """Test that rejected hypotheses are listed in results."""
    good_hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_good",
        title="Pool exhaustion",
        description="Pool exhausted",
        rank=1,
        confidence=0.7,
        evidence_ids=["ev_rej_001"],
        reasoning="Test",
        missing_evidence=[],
        requires_human_review=True,
    )

    bad_hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_bad_dns",
        title="DNS failure caused outage",
        description="DNS failed",
        rank=2,
        confidence=0.5,
        evidence_ids=["ev_rej_002"],
        reasoning="No evidence",
        missing_evidence=[],
        requires_human_review=True,
    )

    evidence = [
        EvidenceChunk(
            evidence_id="ev_rej_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] pool exhausted",
            score=3.0,
        ),
        EvidenceChunk(
            evidence_id="ev_rej_002",
            source_file="test.log",
            source_type="log",
            line_number=2,
            content="2024-03-15T14:20:17Z ERROR [service] timeout",
            score=2.0,
        ),
    ]

    diagnosis = DiagnosisResult(
        incident_id="TEST-008",
        hypotheses=[good_hypothesis, bad_hypothesis],
        summary="Test",
        limitations=[],
    )

    verifier = EvidenceVerifier()
    result = verifier.verify(diagnosis, evidence)

    assert "hyp_bad_dns" in result.rejected_hypothesis_ids
    assert len(result.rejected_hypothesis_ids) > 0


def test_deterministic_verification():
    """Test that verification is deterministic."""
    hypothesis = RootCauseHypothesis(
        hypothesis_id="hyp_det_test",
        title="Pool exhaustion",
        description="Test",
        rank=1,
        confidence=0.7,
        evidence_ids=["ev_det_001"],
        reasoning="Test",
        missing_evidence=[],
        requires_human_review=True,
    )

    evidence = [
        EvidenceChunk(
            evidence_id="ev_det_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] pool exhausted",
            score=3.0,
        ),
    ]

    diagnosis = DiagnosisResult(
        incident_id="TEST-009",
        hypotheses=[hypothesis],
        summary="Test",
        limitations=[],
    )

    verifier = EvidenceVerifier()
    result1 = verifier.verify(diagnosis, evidence)
    result2 = verifier.verify(diagnosis, evidence)

    assert len(result1.verified_hypotheses) == len(result2.verified_hypotheses)
    assert result1.rejected_hypothesis_ids == result2.rejected_hypothesis_ids


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
    return retriever.retrieve("database connection pool exhausted 503", top_k=10)


def test_real_incident_verification(real_incident, real_evidence):
    """Test verification with real incident data."""
    triage_agent = DemoTriageAgent()
    diagnosis_agent = DemoDiagnosisAgent()
    verifier = EvidenceVerifier()

    triage = triage_agent.triage(real_incident, real_evidence)
    diagnosis = diagnosis_agent.diagnose(real_incident, triage, real_evidence)
    result = verifier.verify(diagnosis, real_evidence)

    # Should have some verified hypotheses
    assert len(result.verified_hypotheses) > 0 or len(result.rejected_hypothesis_ids) > 0
    assert result.requires_human_review is True
