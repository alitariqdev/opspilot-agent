"""Tests for incident triage functionality."""

import json
from pathlib import Path

import pytest

from src.opspilot.agents.triage import DemoTriageAgent
from src.opspilot.models import EvidenceChunk, Incident, Severity
from src.opspilot.tools.evidence_retriever import create_evidence_retriever
from src.opspilot.tools.log_parser import parse_log_file


@pytest.fixture
def sample_incident():
    """Create a sample incident for testing."""
    return Incident(
        incident_id="TEST-001",
        title="Test Incident",
        description="Test description",
        symptoms=["symptom1", "symptom2"],
        start_time="2024-03-15T14:00:00Z",
        affected_services=["service-a"],
        severity="unknown",
        status="investigating",
    )


@pytest.fixture
def http_503_evidence():
    """Create evidence showing repeated HTTP 503 errors."""
    return [
        EvidenceChunk(
            evidence_id="ev_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [order-service] Failed to create order: database connection pool exhausted",
            score=5.0,
        ),
        EvidenceChunk(
            evidence_id="ev_002",
            source_file="test.log",
            source_type="log",
            line_number=2,
            content="2024-03-15T14:20:16Z INFO [api-gateway] Upstream service order-service returned 503 for POST /api/orders/create",
            score=4.5,
        ),
        EvidenceChunk(
            evidence_id="ev_003",
            source_file="test.log",
            source_type="log",
            line_number=3,
            content="2024-03-15T14:21:34Z ERROR [order-service] Failed to create order: database connection pool exhausted",
            score=4.5,
        ),
        EvidenceChunk(
            evidence_id="ev_004",
            source_file="test.log",
            source_type="log",
            line_number=4,
            content="2024-03-15T14:21:34Z INFO [api-gateway] Upstream service order-service returned 503 for POST /api/orders/create",
            score=4.0,
        ),
        EvidenceChunk(
            evidence_id="ev_005",
            source_file="test.log",
            source_type="log",
            line_number=5,
            content="2024-03-15T14:22:01Z DEBUG [postgres] Connection pool: 20/20 connections active - pool exhausted",
            score=3.5,
        ),
    ]


def test_triage_with_http_503_evidence_is_sev2(sample_incident, http_503_evidence):
    """Test that repeated HTTP 503 errors result in SEV2 classification."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    assert result.severity == Severity.SEV2
    assert result.incident_id == sample_incident.incident_id


def test_repeated_503_contributes_to_sev2(sample_incident, http_503_evidence):
    """Test that repeated 503 responses are recognized as substantial degradation."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    assert result.severity == Severity.SEV2
    assert "503" in result.rationale.lower() or "degradation" in result.rationale.lower()


def test_affected_services_are_evidence_grounded(sample_incident, http_503_evidence):
    """Test that affected services are extracted from evidence only."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    # Services should come from evidence, not the incident object
    assert len(result.affected_services) > 0

    # Check that services found in evidence are included
    for service in result.affected_services:
        # Service should appear in at least one evidence chunk
        found = any(service in evidence.content.lower() for evidence in http_503_evidence)
        assert found, f"Service {service} not found in evidence"


def test_timeline_events_are_chronological(sample_incident, http_503_evidence):
    """Test that timeline events are sorted chronologically."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    assert len(result.timeline) > 0

    # Check that timestamps are in chronological order
    timestamps = [event.timestamp for event in result.timeline if event.timestamp]
    assert timestamps == sorted(timestamps)


def test_timeline_events_contain_valid_evidence_citations(sample_incident, http_503_evidence):
    """Test that timeline events reference actual evidence IDs."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    evidence_ids = {e.evidence_id for e in http_503_evidence}

    for event in result.timeline:
        assert event.evidence_id in evidence_ids, f"Invalid evidence ID: {event.evidence_id}"


def test_confidence_within_valid_range(sample_incident, http_503_evidence):
    """Test that confidence score is between 0.0 and 1.0."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    assert 0.0 <= result.confidence <= 1.0


def test_empty_evidence_produces_insufficient_evidence_result(sample_incident):
    """Test that empty evidence list produces safe insufficient-evidence result."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, [])

    assert result.severity == Severity.SEV4
    assert result.insufficient_evidence is True
    assert result.confidence == 0.0
    assert len(result.timeline) == 0
    assert len(result.evidence_ids) == 0


def test_agent_does_not_claim_root_cause(sample_incident, http_503_evidence):
    """Test that the triage agent does not claim a final root cause."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    # Rationale should mention this is triage only
    assert "triage" in result.rationale.lower()
    # Should not claim to have found root cause
    assert "root cause" not in result.rationale.lower() or "requires further investigation" in result.rationale.lower()


def test_deterministic_behavior(sample_incident, http_503_evidence):
    """Test that identical input produces identical output."""
    agent = DemoTriageAgent()

    result1 = agent.triage(sample_incident, http_503_evidence)
    result2 = agent.triage(sample_incident, http_503_evidence)

    # Compare all key fields
    assert result1.severity == result2.severity
    assert result1.affected_services == result2.affected_services
    assert result1.symptoms == result2.symptoms
    assert result1.confidence == result2.confidence
    assert result1.insufficient_evidence == result2.insufficient_evidence
    assert len(result1.timeline) == len(result2.timeline)


def test_triage_extracts_symptoms_from_evidence(sample_incident, http_503_evidence):
    """Test that symptoms are extracted from evidence content."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    assert len(result.symptoms) > 0
    # Should find connection pool or 503 symptoms
    symptom_text = " ".join(result.symptoms).lower()
    assert "503" in symptom_text or "pool" in symptom_text or "timeout" in symptom_text


def test_timeline_events_have_descriptions(sample_incident, http_503_evidence):
    """Test that timeline events have non-empty descriptions."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    for event in result.timeline:
        assert event.description
        assert len(event.description) > 0


def test_evidence_ids_are_tracked(sample_incident, http_503_evidence):
    """Test that all evidence IDs are tracked in the result."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    provided_ids = {e.evidence_id for e in http_503_evidence}
    result_ids = set(result.evidence_ids)

    assert result_ids == provided_ids


def test_sev2_requires_human_review(sample_incident, http_503_evidence):
    """Test that SEV2 incidents are flagged for human review."""
    agent = DemoTriageAgent()
    result = agent.triage(sample_incident, http_503_evidence)

    if result.severity == Severity.SEV2:
        assert result.requires_human_review is True


def test_low_evidence_count_affects_confidence(sample_incident):
    """Test that fewer evidence chunks result in lower confidence."""
    agent = DemoTriageAgent()

    # Single evidence
    single_evidence = [
        EvidenceChunk(
            evidence_id="ev_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] Error occurred",
            score=5.0,
        )
    ]

    result = agent.triage(sample_incident, single_evidence)
    assert result.confidence < 0.5


@pytest.fixture
def project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def real_incident(project_root):
    """Load the real incident from incident_001.json."""
    incident_file = project_root / "data" / "incidents" / "incident_001.json"
    with open(incident_file, "r") as f:
        data = json.load(f)
    return Incident(**data)


@pytest.fixture
def real_incident_logs(project_root):
    """Parse the real incident logs."""
    log_file = project_root / "data" / "incidents" / "incident_001_logs.txt"
    return parse_log_file(log_file)


@pytest.fixture
def real_evidence(project_root, real_incident_logs):
    """Create evidence retriever with real incident data."""
    runbook_dir = project_root / "data" / "runbooks"
    retriever = create_evidence_retriever(real_incident_logs, runbook_dir)
    return retriever.retrieve("database connection pool exhausted 503", top_k=10)


def test_real_incident_classified_as_substantial(real_incident, real_evidence):
    """Test that the real incident is classified as substantial user-facing issue."""
    agent = DemoTriageAgent()
    result = agent.triage(real_incident, real_evidence)

    # Should be SEV2 or higher due to multiple 503s and pool exhaustion
    assert result.severity in [Severity.SEV1, Severity.SEV2]


def test_real_incident_has_timeline(real_incident, real_evidence):
    """Test that real incident produces a timeline."""
    agent = DemoTriageAgent()
    result = agent.triage(real_incident, real_evidence)

    assert len(result.timeline) > 0
    assert result.timeline[0].evidence_id is not None


def test_real_incident_identifies_multiple_services(real_incident, real_evidence):
    """Test that real incident identifies affected services from evidence."""
    agent = DemoTriageAgent()
    result = agent.triage(real_incident, real_evidence)

    # Should identify at least order-service, api-gateway, postgres
    assert len(result.affected_services) >= 2
