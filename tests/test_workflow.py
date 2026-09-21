"""Tests for LangGraph workflow functionality."""

import json
from pathlib import Path

import pytest

from src.opspilot.models import Incident
from src.opspilot.workflow import (
    build_investigation_graph,
    generate_hypotheses_node,
    generate_report_node,
    propose_remediation_node,
    retrieve_evidence_node,
    run_investigation,
    triage_incident_node,
    verify_hypotheses_node,
)


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


def test_workflow_graph_compiles():
    """Test that the workflow graph compiles without errors."""
    graph = build_investigation_graph()
    assert graph is not None


def test_workflow_has_expected_nodes():
    """Test that workflow contains expected node names."""
    graph = build_investigation_graph()

    # LangGraph compiled graphs have a 'nodes' attribute
    expected_nodes = {
        "retrieve_evidence",
        "triage_incident",
        "generate_hypotheses",
        "verify_hypotheses",
        "propose_remediation",
        "generate_report",
    }

    # Check nodes exist in graph structure
    graph_data = graph.get_graph().to_json()

    actual_nodes = {node["id"] for node in graph_data["nodes"]}

    for expected_node in expected_nodes:
        assert (
            expected_node in actual_nodes
        ), f"Missing expected node: {expected_node}"


def test_workflow_order_correct():
    """Test that workflow nodes are connected in correct order."""
    graph = build_investigation_graph()
    graph_data = graph.get_graph().to_json()

    # Build edge map
    edges = {}
    for edge in graph_data["edges"]:
        source = edge["source"]
        target = edge["target"]
        if source not in edges:
            edges[source] = []
        edges[source].append(target)

    # Check expected flow
    assert "__start__" in edges
    assert "retrieve_evidence" in edges["__start__"]
    assert "triage_incident" in edges["retrieve_evidence"]
    assert "generate_hypotheses" in edges["triage_incident"]
    assert "verify_hypotheses" in edges["generate_hypotheses"]
    assert "propose_remediation" in edges["verify_hypotheses"]
    assert "generate_report" in edges["propose_remediation"]


def test_retrieve_evidence_node_handles_missing_incident():
    """Test that evidence retrieval handles missing incident gracefully."""
    state = {
        "incident": None,
        "investigation_query": None,
        "evidence": [],
        "triage_result": None,
        "diagnosis_result": None,
        "verification_result": None,
        "remediation_plan": None,
        "incident_report": None,
        "workflow_status": "started",
        "errors": [],
    }

    result = retrieve_evidence_node(state)

    assert result["workflow_status"] == "evidence_retrieval_failed"
    assert len(result["errors"]) > 0


def test_triage_node_requires_evidence():
    """Test that triage node requires evidence."""
    state = {
        "incident": Incident(
            incident_id="TEST-001",
            title="Test",
            description="Test",
            symptoms=["test"],
            start_time="2024-03-15T14:00:00Z",
            affected_services=["test"],
            severity="high",
            status="investigating",
        ),
        "investigation_query": None,
        "evidence": [],
        "triage_result": None,
        "diagnosis_result": None,
        "verification_result": None,
        "remediation_plan": None,
        "incident_report": None,
        "workflow_status": "evidence_retrieved",
        "errors": [],
    }

    result = triage_incident_node(state)

    assert result["workflow_status"] == "triage_failed"
    assert "no evidence" in " ".join(result["errors"]).lower()


def test_diagnosis_node_requires_triage():
    """Test that diagnosis node requires triage result."""
    from src.opspilot.models import EvidenceChunk

    state = {
        "incident": Incident(
            incident_id="TEST-001",
            title="Test",
            description="Test",
            symptoms=["test"],
            start_time="2024-03-15T14:00:00Z",
            affected_services=["test"],
            severity="high",
            status="investigating",
        ),
        "investigation_query": None,
        "evidence": [
            EvidenceChunk(
                evidence_id="ev_001",
                source_file="test.log",
                source_type="log",
                line_number=1,
                content="test content",
                score=1.0,
            )
        ],
        "triage_result": None,
        "diagnosis_result": None,
        "verification_result": None,
        "remediation_plan": None,
        "incident_report": None,
        "workflow_status": "evidence_retrieved",
        "errors": [],
    }

    result = generate_hypotheses_node(state)

    assert result["workflow_status"] == "diagnosis_failed"
    assert "triage" in " ".join(result["errors"]).lower()


def test_verification_node_requires_diagnosis():
    """Test that verification node requires diagnosis result."""
    state = {
        "incident": Incident(
            incident_id="TEST-001",
            title="Test",
            description="Test",
            symptoms=["test"],
            start_time="2024-03-15T14:00:00Z",
            affected_services=["test"],
            severity="high",
            status="investigating",
        ),
        "investigation_query": None,
        "evidence": [],
        "triage_result": None,
        "diagnosis_result": None,
        "verification_result": None,
        "remediation_plan": None,
        "incident_report": None,
        "workflow_status": "diagnosis_complete",
        "errors": [],
    }

    result = verify_hypotheses_node(state)

    assert result["workflow_status"] == "verification_failed"
    assert "diagnosis" in " ".join(result["errors"]).lower()


def test_remediation_node_requires_verification():
    """Test that remediation node requires verification result."""
    state = {
        "incident": Incident(
            incident_id="TEST-001",
            title="Test",
            description="Test",
            symptoms=["test"],
            start_time="2024-03-15T14:00:00Z",
            affected_services=["test"],
            severity="high",
            status="investigating",
        ),
        "investigation_query": None,
        "evidence": [],
        "triage_result": None,
        "diagnosis_result": None,
        "verification_result": None,
        "remediation_plan": None,
        "incident_report": None,
        "workflow_status": "verification_complete",
        "errors": [],
    }

    result = propose_remediation_node(state)

    assert result["workflow_status"] == "remediation_failed"
    assert "verification" in " ".join(result["errors"]).lower()


def test_report_node_requires_all_components():
    """Test that report generation requires all upstream components."""
    state = {
        "incident": Incident(
            incident_id="TEST-001",
            title="Test",
            description="Test",
            symptoms=["test"],
            start_time="2024-03-15T14:00:00Z",
            affected_services=["test"],
            severity="high",
            status="investigating",
        ),
        "investigation_query": None,
        "evidence": [],
        "triage_result": None,
        "diagnosis_result": None,
        "verification_result": None,
        "remediation_plan": None,
        "incident_report": None,
        "workflow_status": "remediation_complete",
        "errors": [],
    }

    result = generate_report_node(state)

    assert result["workflow_status"] == "report_generation_failed"
    assert len(result["errors"]) > 0


def test_workflow_handles_errors_safely():
    """Test that workflow captures errors safely without exposing stack traces."""
    # Create invalid state that will trigger errors
    state = {
        "incident": None,
        "investigation_query": None,
        "evidence": [],
        "triage_result": None,
        "diagnosis_result": None,
        "verification_result": None,
        "remediation_plan": None,
        "incident_report": None,
        "workflow_status": "started",
        "errors": [],
    }

    # Run through nodes
    result = retrieve_evidence_node(state)

    assert "errors" in result
    assert len(result["errors"]) > 0

    # Errors should be user-friendly, not raw exceptions
    for error in result["errors"]:
        assert isinstance(error, str)
        assert len(error) < 500  # Reasonable error message length


def test_real_incident_workflow_end_to_end(real_incident):
    """Test complete workflow with real incident data."""
    result = run_investigation(real_incident)

    # Workflow should complete
    assert result["workflow_status"] == "complete"
    assert len(result["errors"]) == 0

    # Should have all components
    assert result["evidence"] is not None
    assert len(result["evidence"]) > 0
    assert result["triage_result"] is not None
    assert result["diagnosis_result"] is not None
    assert result["verification_result"] is not None
    assert result["remediation_plan"] is not None
    assert result["incident_report"] is not None


def test_workflow_produces_markdown_report(real_incident):
    """Test that workflow produces valid Markdown report."""
    result = run_investigation(real_incident)

    assert result["incident_report"] is not None
    report = result["incident_report"]

    # Check for required report sections
    assert "# Incident Report" in report
    assert "## Executive Summary" in report
    assert "## Evidence-Based Timeline" in report
    assert "## Root Cause Analysis" in report
    assert "## Recommended Actions" in report
    assert "## Human Review Required" in report


def test_report_contains_evidence_references(real_incident):
    """Test that report contains evidence references with filenames and line numbers."""
    result = run_investigation(real_incident)

    report = result["incident_report"]

    # Should contain evidence references in format: filename:line_number
    assert "incident_001_logs.txt:" in report or ".md:" in report


def test_report_identifies_unsupported_hypotheses(real_incident):
    """Test that report clearly identifies rejected/unsupported hypotheses."""
    result = run_investigation(real_incident)

    report = result["incident_report"]
    verification = result["verification_result"]

    if verification.rejected_hypothesis_ids:
        # Report should have rejected section
        assert "Rejected Hypotheses" in report or "rejected" in report.lower()


def test_workflow_deterministic(real_incident):
    """Test that identical inputs produce deterministic results."""
    result1 = run_investigation(real_incident)
    result2 = run_investigation(real_incident)

    # Status should be same
    assert result1["workflow_status"] == result2["workflow_status"]

    # Evidence count should be same
    assert len(result1["evidence"]) == len(result2["evidence"])

    # Triage severity should be same
    assert result1["triage_result"].severity == result2["triage_result"].severity

    # Hypothesis count should be same
    assert len(result1["diagnosis_result"].hypotheses) == len(
        result2["diagnosis_result"].hypotheses
    )


def test_all_remediation_actions_require_human_approval(real_incident):
    """Test that all state-changing actions require human approval."""
    result = run_investigation(real_incident)

    plan = result["remediation_plan"]

    # Check all high-risk actions
    for action in plan.actions:
        if action.risk_level.value in ["high", "critical"]:
            assert action.requires_human_approval is True


def test_no_commands_executed_in_workflow(real_incident):
    """Test that workflow generates recommendations but executes nothing."""
    result = run_investigation(real_incident)

    # Workflow should complete without executing any actions
    assert result["workflow_status"] == "complete"

    # Remediation plan should exist but actions not executed
    plan = result["remediation_plan"]
    assert len(plan.actions) > 0

    # All actions should have validation steps (meaning not executed yet)
    for action in plan.actions:
        assert action.validation_step
        assert "verify" in action.validation_step.lower() or "confirm" in action.validation_step.lower()
