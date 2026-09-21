"""Tests for diagnosis agent functionality."""

import json
from pathlib import Path

import pytest

from src.opspilot.agents.diagnosis import DemoDiagnosisAgent
from src.opspilot.agents.triage import DemoTriageAgent
from src.opspilot.models import EvidenceChunk, Incident
from src.opspilot.tools.evidence_retriever import create_evidence_retriever
from src.opspilot.tools.log_parser import parse_log_file


@pytest.fixture
def sample_incident():
    """Create a sample incident."""
    return Incident(
        incident_id="TEST-DIAG-001",
        title="Test Diagnostic Incident",
        description="Test incident for diagnosis",
        symptoms=["errors", "timeouts"],
        start_time="2024-03-15T14:00:00Z",
        affected_services=["test-service"],
        severity="high",
        status="investigating",
    )


@pytest.fixture
def pool_exhaustion_evidence():
    """Create evidence showing pool exhaustion pattern."""
    return [
        EvidenceChunk(
            evidence_id="ev_pe_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [order-service] database connection pool exhausted",
            score=5.0,
        ),
        EvidenceChunk(
            evidence_id="ev_pe_002",
            source_file="test.log",
            source_type="log",
            line_number=2,
            content="2024-03-15T14:20:17Z WARN [order-service] connection timeout after 1000ms",
            score=4.5,
        ),
        EvidenceChunk(
            evidence_id="ev_pe_003",
            source_file="test.log",
            source_type="log",
            line_number=3,
            content="2024-03-15T14:20:18Z INFO [api-gateway] upstream returned 503",
            score=4.0,
        ),
        EvidenceChunk(
            evidence_id="ev_pe_004",
            source_file="test.log",
            source_type="log",
            line_number=4,
            content="2024-03-15T14:20:19Z ERROR [order-service] Failed to process request: connection pool exhausted",
            score=4.0,
        ),
        EvidenceChunk(
            evidence_id="ev_pe_005",
            source_file="test.log",
            source_type="log",
            line_number=5,
            content="2024-03-15T14:15:05Z DEBUG [postgres] Long-running query detected: duration=622s",
            score=3.5,
        ),
    ]


def test_sample_incident_produces_pool_exhaustion_hypothesis(
    sample_incident, pool_exhaustion_evidence
):
    """Test that pool exhaustion evidence produces appropriate hypothesis."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, pool_exhaustion_evidence)
    result = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)

    assert len(result.hypotheses) > 0

    # Check for pool exhaustion hypothesis
    pool_hyp = None
    for hyp in result.hypotheses:
        if "pool exhaustion" in hyp.title.lower():
            pool_hyp = hyp
            break

    assert pool_hyp is not None, "Should generate pool exhaustion hypothesis"
    assert "connection" in pool_hyp.description.lower()


def test_long_running_query_recognized_as_contributor(
    sample_incident, pool_exhaustion_evidence
):
    """Test that long-running query is recognized as possible contributor."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, pool_exhaustion_evidence)
    result = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)

    # Check for query-related hypothesis
    query_hyp = None
    for hyp in result.hypotheses:
        if "query" in hyp.title.lower() or "query" in hyp.description.lower():
            query_hyp = hyp
            break

    assert query_hyp is not None, "Should recognize long-running query pattern"


def test_hypotheses_sorted_by_confidence(sample_incident, pool_exhaustion_evidence):
    """Test that hypotheses are sorted by confidence (highest first)."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, pool_exhaustion_evidence)
    result = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)

    if len(result.hypotheses) > 1:
        for i in range(len(result.hypotheses) - 1):
            assert (
                result.hypotheses[i].confidence
                >= result.hypotheses[i + 1].confidence
            ), "Hypotheses should be sorted by confidence"


def test_hypotheses_have_unique_ids(sample_incident, pool_exhaustion_evidence):
    """Test that all hypotheses have unique IDs."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, pool_exhaustion_evidence)
    result = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)

    hypothesis_ids = [h.hypothesis_id for h in result.hypotheses]
    assert len(hypothesis_ids) == len(set(hypothesis_ids)), "IDs must be unique"


def test_all_cited_evidence_ids_exist(sample_incident, pool_exhaustion_evidence):
    """Test that all cited evidence IDs actually exist in provided evidence."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, pool_exhaustion_evidence)
    result = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)

    available_ids = {e.evidence_id for e in pool_exhaustion_evidence}

    for hyp in result.hypotheses:
        for eid in hyp.evidence_ids:
            assert (
                eid in available_ids
            ), f"Evidence ID {eid} not in available evidence"


def test_confidence_values_in_valid_range(sample_incident, pool_exhaustion_evidence):
    """Test that all confidence values are between 0 and 1."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, pool_exhaustion_evidence)
    result = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)

    for hyp in result.hypotheses:
        assert 0.0 <= hyp.confidence <= 1.0, f"Confidence {hyp.confidence} out of range"


def test_diagnosis_with_empty_evidence_handled_safely(sample_incident):
    """Test that diagnosis with empty evidence produces safe result."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, [])
    result = agent.diagnose(sample_incident, triage, [])

    assert result.insufficient_evidence is True
    assert len(result.hypotheses) == 0
    assert "insufficient" in result.summary.lower()


def test_deterministic_behavior(sample_incident, pool_exhaustion_evidence):
    """Test that identical input produces identical output."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, pool_exhaustion_evidence)

    result1 = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)
    result2 = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)

    assert len(result1.hypotheses) == len(result2.hypotheses)
    assert result1.summary == result2.summary

    for h1, h2 in zip(result1.hypotheses, result2.hypotheses):
        assert h1.hypothesis_id == h2.hypothesis_id
        assert h1.title == h2.title
        assert h1.confidence == h2.confidence


def test_diagnosis_includes_limitations(sample_incident, pool_exhaustion_evidence):
    """Test that diagnosis result includes limitations."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, pool_exhaustion_evidence)
    result = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)

    assert len(result.limitations) > 0
    assert any("correlation" in lim.lower() for lim in result.limitations)


def test_hypothesis_requires_human_review(sample_incident, pool_exhaustion_evidence):
    """Test that hypotheses are flagged for human review."""
    agent = DemoDiagnosisAgent()
    triage_agent = DemoTriageAgent()

    triage = triage_agent.triage(sample_incident, pool_exhaustion_evidence)
    result = agent.diagnose(sample_incident, triage, pool_exhaustion_evidence)

    assert result.requires_human_review is True
    for hyp in result.hypotheses:
        assert hyp.requires_human_review is True


@pytest.fixture
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def real_incident(project_root):
    """Load real incident data."""
    incident_file = project_root / "data" / "incidents" / "incident_001.json"
    with open(incident_file, "r") as f:
        return Incident(**json.load(f))


@pytest.fixture
def real_evidence(project_root):
    """Get real incident evidence."""
    log_file = project_root / "data" / "incidents" / "incident_001_logs.txt"
    runbook_dir = project_root / "data" / "runbooks"

    logs = parse_log_file(log_file)
    retriever = create_evidence_retriever(logs, runbook_dir)
    return retriever.retrieve("database connection pool exhausted 503", top_k=10)


def test_real_incident_diagnosis(real_incident, real_evidence):
    """Test diagnosis with real incident data."""
    triage_agent = DemoTriageAgent()
    diagnosis_agent = DemoDiagnosisAgent()

    triage = triage_agent.triage(real_incident, real_evidence)
    result = diagnosis_agent.diagnose(real_incident, triage, real_evidence)

    assert len(result.hypotheses) > 0
    assert not result.insufficient_evidence

    # Should identify connection pool issue
    has_pool_hypothesis = any(
        "pool" in h.title.lower() for h in result.hypotheses
    )
    assert has_pool_hypothesis
