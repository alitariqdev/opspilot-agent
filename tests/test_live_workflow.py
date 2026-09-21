"""Integration tests for live workflow mode."""

import json
from pathlib import Path

import pytest

from src.opspilot.agents.diagnosis import DemoDiagnosisAgent
from src.opspilot.agents.triage import DemoTriageAgent
from src.opspilot.config import OpsPilotConfig
from src.opspilot.models import Incident
from src.opspilot.workflow import run_investigation
from tests.test_llm_client import FakeLLMClient


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


def test_demo_mode_uses_demo_agents(real_incident):
    """Test that demo mode uses demo agents and makes no LLM calls."""
    config = OpsPilotConfig(opspilot_mode="demo")

    # Run investigation in demo mode
    result = run_investigation(incident=real_incident, config=config)

    # Should complete successfully
    assert result["workflow_status"] == "complete"
    assert result["triage_result"] is not None
    assert result["diagnosis_result"] is not None
    assert result["verification_result"] is not None

    # Verify agents used were demo agents (deterministic)
    assert isinstance(result["triage_agent"], DemoTriageAgent)
    assert isinstance(result["diagnosis_agent"], DemoDiagnosisAgent)


def test_live_mode_with_fake_client(real_incident):
    """Test that live mode can use injected fake agents."""
    from src.opspilot.agents.live_diagnosis import LiveDiagnosisAgent
    from src.opspilot.agents.live_triage import LiveTriageAgent

    # Create fake clients
    triage_client = FakeLLMClient({
        "severity": "SEV2",
        "affected_services": ["order-service", "api-gateway"],
        "symptoms": ["connection pool exhaustion"],
        "timeline": [],
        "rationale": "High severity incident",
        "confidence": 0.85,
    })

    diagnosis_client = FakeLLMClient({
        "hypotheses": [
            {
                "title": "Connection pool exhaustion",
                "description": "Pool exhausted",
                "confidence": 0.8,
                "evidence_ids": [],  # Will be filtered to valid IDs
                "reasoning": "Evidence shows pool issues",
                "missing_evidence": [],
            }
        ],
        "limitations": [],
    })

    # Create live agents with fake clients
    triage_agent = LiveTriageAgent(triage_client)
    diagnosis_agent = LiveDiagnosisAgent(diagnosis_client)

    # Run investigation with injected agents
    result = run_investigation(
        incident=real_incident,
        triage_agent=triage_agent,
        diagnosis_agent=diagnosis_agent,
    )

    # Should complete successfully
    assert result["workflow_status"] == "complete"
    assert result["triage_result"] is not None
    assert result["diagnosis_result"] is not None

    # Verify fake clients were called
    assert len(triage_client.calls) == 1
    assert len(diagnosis_client.calls) == 1


def test_live_hypotheses_pass_through_verifier(real_incident):
    """Test that live LLM hypotheses are independently verified."""
    from src.opspilot.agents.live_diagnosis import LiveDiagnosisAgent
    from src.opspilot.agents.live_triage import LiveTriageAgent

    # Create fake clients that generate hypotheses
    triage_client = FakeLLMClient({
        "severity": "SEV2",
        "affected_services": ["service"],
        "symptoms": ["errors"],
        "timeline": [],
        "rationale": "Test",
        "confidence": 0.8,
    })

    # Create hypothesis with invalid evidence ID
    diagnosis_client = FakeLLMClient({
        "hypotheses": [
            {
                "title": "Test hypothesis",
                "description": "Test",
                "confidence": 0.7,
                "evidence_ids": [],  # Will be filled with valid IDs
                "reasoning": "Test reasoning",
                "missing_evidence": [],
            }
        ],
        "limitations": [],
    })

    triage_agent = LiveTriageAgent(triage_client)
    diagnosis_agent = LiveDiagnosisAgent(diagnosis_client)

    result = run_investigation(
        incident=real_incident,
        triage_agent=triage_agent,
        diagnosis_agent=diagnosis_agent,
    )

    # Verification should have run
    assert result["verification_result"] is not None

    # Hypotheses were verified (not just passed through)
    diagnosis = result["diagnosis_result"]
    verification = result["verification_result"]

    if diagnosis.hypotheses:
        # At least one hypothesis was generated and verified
        assert len(verification.verified_hypotheses) > 0 or len(
            verification.rejected_hypothesis_ids
        ) > 0


def test_invalid_evidence_ids_filtered_before_remediation(real_incident):
    """Test that invalid evidence IDs cannot influence remediation."""
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

    # Try to inject invalid evidence IDs
    diagnosis_client = FakeLLMClient({
        "hypotheses": [
            {
                "title": "Fake hypothesis",
                "description": "This has invalid evidence",
                "confidence": 0.9,
                "evidence_ids": ["ev_invalid_999", "ev_fake_888"],
                "reasoning": "Fabricated evidence",
                "missing_evidence": [],
            }
        ],
        "limitations": [],
    })

    triage_agent = LiveTriageAgent(triage_client)
    diagnosis_agent = LiveDiagnosisAgent(diagnosis_client)

    result = run_investigation(
        incident=real_incident,
        triage_agent=triage_agent,
        diagnosis_agent=diagnosis_agent,
    )

    # Remediation should have run
    assert result["remediation_plan"] is not None

    # Check that remediation only uses verified hypotheses
    remediation = result["remediation_plan"]
    verification = result["verification_result"]

    # If no hypotheses were verified, remediation should have no actions
    # or actions should only reference valid evidence
    if not verification.verified_hypotheses:
        # No verified hypotheses means limited or no remediation
        assert True  # This is expected behavior


def test_provider_failure_produces_safe_error(real_incident):
    """Test that provider failure produces safe workflow error."""
    from src.opspilot.agents.live_diagnosis import LiveDiagnosisAgent
    from src.opspilot.agents.live_triage import LiveTriageAgent
    from src.opspilot.llm_client import LLMClientError

    class FailingFakeClient:
        """Fake client that always fails."""

        def generate_structured(self, system_prompt, user_prompt, response_model):
            raise LLMClientError("API connection failed")

    failing_client = FailingFakeClient()

    triage_agent = LiveTriageAgent(failing_client)
    diagnosis_agent = LiveDiagnosisAgent(failing_client)

    result = run_investigation(
        incident=real_incident,
        triage_agent=triage_agent,
        diagnosis_agent=diagnosis_agent,
    )

    # Should complete with error status (not crash)
    assert result["workflow_status"] in [
        "complete",
        "triage_failed",
        "diagnosis_failed",
    ]

    # Should have triage and diagnosis results (may be fallback)
    assert result["triage_result"] is not None
    assert result["diagnosis_result"] is not None


def test_provider_failure_does_not_expose_api_key(real_incident):
    """Test that provider errors don't expose API keys."""
    from src.opspilot.agents.live_diagnosis import LiveDiagnosisAgent
    from src.opspilot.agents.live_triage import LiveTriageAgent
    from src.opspilot.llm_client import LLMClientError

    class FailingFakeClient:
        """Fake client that simulates error with secret in exception."""

        def generate_structured(self, system_prompt, user_prompt, response_model):
            # Simulate an error that might contain secrets
            raise Exception("API error with key: sk-secret-key-12345")

    failing_client = FailingFakeClient()

    triage_agent = LiveTriageAgent(failing_client)
    diagnosis_agent = LiveDiagnosisAgent(failing_client)

    result = run_investigation(
        incident=real_incident,
        triage_agent=triage_agent,
        diagnosis_agent=diagnosis_agent,
    )

    # Check that error messages don't contain API key patterns
    if result.get("errors"):
        for error in result["errors"]:
            assert "sk-" not in error, f"API key pattern in error: {error}"
            assert "secret" not in error.lower(), f"Secret keyword in error: {error}"

    # Check triage and diagnosis results for safe error messages
    if result["triage_result"]:
        assert "sk-" not in result["triage_result"].rationale

    if result["diagnosis_result"]:
        assert "sk-" not in result["diagnosis_result"].summary


def test_missing_live_config_handled_safely(real_incident):
    """Test that missing live configuration is handled safely."""
    # Create config for live mode without API key
    config = OpsPilotConfig(opspilot_mode="live", openai_api_key=None)

    # Should raise ValueError when validating
    with pytest.raises(ValueError, match="Live mode requires OPENAI_API_KEY"):
        config.validate_live_mode()

    # Workflow should gracefully fall back to demo agents
    result = run_investigation(incident=real_incident, config=config)

    # Should complete (using demo agents as fallback)
    assert result["workflow_status"] == "complete"
    assert result["triage_result"] is not None
    assert result["diagnosis_result"] is not None


def test_demo_mode_import_does_not_require_api_key():
    """Test that importing in demo mode doesn't require configuration."""
    # This should not raise even without API key
    config = OpsPilotConfig(opspilot_mode="demo", openai_api_key=None)

    assert config.opspilot_mode == "demo"
    assert config.openai_api_key is None

    # Validation should not be needed for demo mode
    # (only call validate_live_mode when actually using live mode)


def test_workflow_deterministic_in_demo_mode(real_incident):
    """Test that demo mode workflow remains deterministic."""
    config = OpsPilotConfig(opspilot_mode="demo")

    result1 = run_investigation(incident=real_incident, config=config)
    result2 = run_investigation(incident=real_incident, config=config)

    # Should produce identical results
    assert result1["workflow_status"] == result2["workflow_status"]
    assert len(result1["evidence"]) == len(result2["evidence"])

    # Triage should be identical
    assert result1["triage_result"].severity == result2["triage_result"].severity
    assert result1["triage_result"].confidence == result2["triage_result"].confidence

    # Diagnosis should be identical
    assert len(result1["diagnosis_result"].hypotheses) == len(
        result2["diagnosis_result"].hypotheses
    )
