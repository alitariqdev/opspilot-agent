"""Tests for live LLM-powered agents."""

import pytest

from src.opspilot.models import EvidenceChunk, Incident, Severity, TriageResult
from tests.test_llm_client import FakeLLMClient


@pytest.fixture
def sample_incident():
    """Create sample incident."""
    return Incident(
        incident_id="TEST-LIVE-001",
        title="Test Live Agent Incident",
        description="Test incident for live agents",
        symptoms=["errors", "timeouts"],
        start_time="2024-03-15T14:00:00Z",
        affected_services=["test-service"],
        severity="high",
        status="investigating",
    )


@pytest.fixture
def sample_evidence():
    """Create sample evidence."""
    return [
        EvidenceChunk(
            evidence_id="ev_live_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="2024-03-15T14:20:16Z ERROR [service] pool exhausted",
            score=5.0,
        ),
        EvidenceChunk(
            evidence_id="ev_live_002",
            source_file="test.log",
            source_type="log",
            line_number=2,
            content="2024-03-15T14:20:17Z ERROR [service] timeout",
            score=4.5,
        ),
        EvidenceChunk(
            evidence_id="ev_live_003",
            source_file="runbook.md",
            source_type="runbook",
            line_number=10,
            content="Check connection pool status",
            score=4.0,
        ),
    ]


def test_live_triage_agent_with_fake_client(sample_incident, sample_evidence):
    """Test live triage agent with fake LLM client."""
    from src.opspilot.agents.live_triage import LiveTriageAgent

    # Create fake client with canned response
    fake_client = FakeLLMClient({
        "severity": "SEV2",
        "affected_services": ["service"],
        "symptoms": ["pool exhaustion", "timeouts"],
        "timeline": [
            {
                "timestamp": "2024-03-15T14:20:16Z",
                "service": "service",
                "description": "Pool exhausted",
                "evidence_id": "ev_live_001",
            }
        ],
        "rationale": "High severity due to pool exhaustion",
        "confidence": 0.85,
    })

    agent = LiveTriageAgent(fake_client)
    result = agent.triage(sample_incident, sample_evidence)

    assert result.incident_id == "TEST-LIVE-001"
    assert result.severity == Severity.SEV2
    assert len(result.affected_services) > 0
    assert len(result.timeline) > 0
    assert result.confidence == 0.85
    assert result.requires_human_review is True

    # Verify fake client was called
    assert len(fake_client.calls) == 1


def test_live_triage_handles_insufficient_evidence(sample_incident, sample_evidence):
    """Test that live triage handles insufficient evidence."""
    from src.opspilot.agents.live_triage import LiveTriageAgent

    fake_client = FakeLLMClient({})
    agent = LiveTriageAgent(fake_client)

    # Only 1 evidence chunk (need at least 2)
    result = agent.triage(sample_incident, [sample_evidence[0]])

    assert result.severity == Severity.SEV4
    assert result.insufficient_evidence is True
    assert result.requires_human_review is True

    # Should not call LLM with insufficient evidence
    assert len(fake_client.calls) == 0


def test_live_diagnosis_agent_with_fake_client(sample_incident, sample_evidence):
    """Test live diagnosis agent with fake LLM client."""
    from src.opspilot.agents.live_diagnosis import LiveDiagnosisAgent

    # Create fake client
    fake_client = FakeLLMClient({
        "hypotheses": [
            {
                "title": "Connection pool exhaustion",
                "description": "Pool exhausted causing failures",
                "confidence": 0.85,
                "evidence_ids": ["ev_live_001", "ev_live_002"],
                "reasoning": "Evidence shows pool exhaustion",
                "missing_evidence": ["Database metrics"],
            }
        ],
        "limitations": ["Based on logs only"],
    })

    # Create sample triage result
    triage = TriageResult(
        incident_id="TEST-LIVE-001",
        severity=Severity.SEV2,
        affected_services=["service"],
        symptoms=["pool exhaustion"],
        timeline=[],
        rationale="Test",
        evidence_ids=["ev_live_001"],
        confidence=0.8,
        insufficient_evidence=False,
        requires_human_review=True,
    )

    agent = LiveDiagnosisAgent(fake_client)
    result = agent.diagnose(sample_incident, triage, sample_evidence)

    assert result.incident_id == "TEST-LIVE-001"
    assert len(result.hypotheses) > 0
    assert result.hypotheses[0].title == "Connection pool exhaustion"
    assert result.hypotheses[0].confidence == 0.85
    assert result.requires_human_review is True

    # Verify fake client was called
    assert len(fake_client.calls) == 1


def test_live_diagnosis_validates_evidence_ids(sample_incident, sample_evidence):
    """Test that live diagnosis validates evidence IDs."""
    from src.opspilot.agents.live_diagnosis import LiveDiagnosisAgent

    # Create fake client that returns invalid evidence ID
    fake_client = FakeLLMClient({
        "hypotheses": [
            {
                "title": "Test hypothesis",
                "description": "Test",
                "confidence": 0.7,
                "evidence_ids": ["ev_invalid_999", "ev_live_001"],  # One invalid
                "reasoning": "Test reasoning",
                "missing_evidence": [],
            }
        ],
        "limitations": [],
    })

    triage = TriageResult(
        incident_id="TEST-LIVE-001",
        severity=Severity.SEV2,
        affected_services=[],
        symptoms=[],
        timeline=[],
        rationale="Test",
        evidence_ids=[],
        confidence=0.8,
        insufficient_evidence=False,
        requires_human_review=True,
    )

    agent = LiveDiagnosisAgent(fake_client)
    result = agent.diagnose(sample_incident, triage, sample_evidence)

    # Should only include valid evidence ID
    assert len(result.hypotheses) > 0
    assert "ev_live_001" in result.hypotheses[0].evidence_ids
    assert "ev_invalid_999" not in result.hypotheses[0].evidence_ids


def test_live_diagnosis_respects_max_confidence(sample_incident, sample_evidence):
    """Test that live diagnosis respects max confidence of 0.95."""
    from src.opspilot.agents.live_diagnosis import LiveDiagnosisAgent

    # Create fake client that returns max valid confidence
    fake_client = FakeLLMClient({
        "hypotheses": [
            {
                "title": "Test hypothesis",
                "description": "Test",
                "confidence": 0.95,  # Max allowed
                "evidence_ids": ["ev_live_001"],
                "reasoning": "Test reasoning",
                "missing_evidence": [],
            }
        ],
        "limitations": [],
    })

    triage = TriageResult(
        incident_id="TEST-LIVE-001",
        severity=Severity.SEV2,
        affected_services=[],
        symptoms=[],
        timeline=[],
        rationale="Test",
        evidence_ids=[],
        confidence=0.8,
        insufficient_evidence=False,
        requires_human_review=True,
    )

    agent = LiveDiagnosisAgent(fake_client)
    result = agent.diagnose(sample_incident, triage, sample_evidence)

    # Should maintain confidence at or below 0.95
    assert len(result.hypotheses) > 0
    assert result.hypotheses[0].confidence <= 0.95


def test_live_agents_require_human_review(sample_incident, sample_evidence):
    """Test that all live agent outputs require human review."""
    from src.opspilot.agents.live_diagnosis import LiveDiagnosisAgent
    from src.opspilot.agents.live_triage import LiveTriageAgent

    triage_client = FakeLLMClient({
        "severity": "SEV2",
        "affected_services": [],
        "symptoms": [],
        "timeline": [],
        "rationale": "Test",
        "confidence": 0.8,
    })

    diagnosis_client = FakeLLMClient({
        "hypotheses": [
            {
                "title": "Test",
                "description": "Test",
                "confidence": 0.7,
                "evidence_ids": ["ev_live_001"],
                "reasoning": "Test",
                "missing_evidence": [],
            }
        ],
        "limitations": [],
    })

    triage_agent = LiveTriageAgent(triage_client)
    triage_result = triage_agent.triage(sample_incident, sample_evidence)
    assert triage_result.requires_human_review is True

    diagnosis_agent = LiveDiagnosisAgent(diagnosis_client)
    diagnosis_result = diagnosis_agent.diagnose(sample_incident, triage_result, sample_evidence)
    assert diagnosis_result.requires_human_review is True
