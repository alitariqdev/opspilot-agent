"""LangGraph workflow for end-to-end incident investigation."""

from pathlib import Path
from typing import List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.opspilot.agents.diagnosis import DemoDiagnosisAgent
from src.opspilot.agents.remediation import DemoRemediationAgent
from src.opspilot.agents.triage import DemoTriageAgent
from src.opspilot.agents.verifier import EvidenceVerifier
from src.opspilot.models import (
    DiagnosisResult,
    EvidenceChunk,
    Incident,
    RemediationPlan,
    TriageResult,
    VerificationResult,
)
from src.opspilot.reporting import generate_incident_report
from src.opspilot.tools.evidence_retriever import create_evidence_retriever
from src.opspilot.tools.log_parser import parse_log_file


class InvestigationState(TypedDict):
    """State for incident investigation workflow.

    Attributes:
        incident: Incident metadata
        investigation_query: Query string for evidence retrieval
        evidence: Retrieved evidence chunks
        triage_result: Triage assessment result
        diagnosis_result: Diagnosis with hypotheses
        verification_result: Verification results
        remediation_plan: Remediation recommendations
        incident_report: Generated Markdown report
        workflow_status: Current workflow status
        errors: List of error messages
    """

    incident: Optional[Incident]
    investigation_query: Optional[str]
    evidence: List[EvidenceChunk]
    triage_result: Optional[TriageResult]
    diagnosis_result: Optional[DiagnosisResult]
    verification_result: Optional[VerificationResult]
    remediation_plan: Optional[RemediationPlan]
    incident_report: Optional[str]
    workflow_status: str
    errors: List[str]


def retrieve_evidence_node(state: InvestigationState) -> InvestigationState:
    """Retrieve evidence for the incident.

    Args:
        state: Current investigation state

    Returns:
        Updated state with evidence
    """
    try:
        if not state["incident"]:
            return {
                **state,
                "evidence": [],
                "workflow_status": "evidence_retrieval_failed",
                "errors": state.get("errors", []) + ["No incident provided"],
            }

        incident = state["incident"]
        investigation_query = state.get("investigation_query")

        if not investigation_query:
            # Build default query from incident symptoms
            query_parts = [incident.title]
            query_parts.extend(incident.symptoms[:3])  # Top 3 symptoms
            investigation_query = " ".join(query_parts)

        # Find incident log file
        incident_dir = Path("data/incidents")

        # Try multiple naming patterns
        possible_names = [
            f"{incident.incident_id}_logs.txt",  # INC-2024-001_logs.txt
            f"{incident.incident_id.lower()}_logs.txt",  # inc-2024-001_logs.txt
            f"{incident.incident_id.replace('-', '_').lower()}_logs.txt",  # inc_2024_001_logs.txt
        ]

        # Also try to find any matching log file by pattern
        if incident_dir.exists():
            # Extract numeric part from incident ID (e.g., "001" from "INC-2024-001")
            import re
            match = re.search(r'(\d+)$', incident.incident_id)
            if match:
                num = match.group(1)
                possible_names.append(f"incident_{num}_logs.txt")

        log_file = None
        for name in possible_names:
            candidate = incident_dir / name
            if candidate.exists():
                log_file = candidate
                break

        if log_file is None:
            return {
                **state,
                "evidence": [],
                "workflow_status": "evidence_retrieval_failed",
                "errors": state.get("errors", [])
                + [f"Log file not found for incident {incident.incident_id}. Tried: {', '.join(possible_names)}"],
            }

        # Parse logs
        logs = parse_log_file(log_file)

        # Find runbooks
        runbook_dir = Path("data/runbooks")

        # Create retriever and retrieve evidence
        retriever = create_evidence_retriever(logs, runbook_dir)
        evidence = retriever.retrieve(investigation_query, top_k=15)

        return {
            **state,
            "evidence": evidence,
            "workflow_status": "evidence_retrieved",
        }

    except Exception as e:
        return {
            **state,
            "evidence": [],
            "workflow_status": "evidence_retrieval_failed",
            "errors": state.get("errors", [])
            + [f"Evidence retrieval error: {str(e)}"],
        }


def triage_incident_node(state: InvestigationState) -> InvestigationState:
    """Perform incident triage.

    Args:
        state: Current investigation state

    Returns:
        Updated state with triage result
    """
    try:
        if not state["incident"]:
            return {
                **state,
                "triage_result": None,
                "workflow_status": "triage_failed",
                "errors": state.get("errors", []) + ["No incident for triage"],
            }

        if not state["evidence"]:
            return {
                **state,
                "triage_result": None,
                "workflow_status": "triage_failed",
                "errors": state.get("errors", [])
                + ["No evidence available for triage"],
            }

        triage_agent = DemoTriageAgent()
        triage_result = triage_agent.triage(state["incident"], state["evidence"])

        return {
            **state,
            "triage_result": triage_result,
            "workflow_status": "triage_complete",
        }

    except Exception as e:
        return {
            **state,
            "triage_result": None,
            "workflow_status": "triage_failed",
            "errors": state.get("errors", []) + [f"Triage error: {str(e)}"],
        }


def generate_hypotheses_node(state: InvestigationState) -> InvestigationState:
    """Generate root cause hypotheses.

    Args:
        state: Current investigation state

    Returns:
        Updated state with diagnosis result
    """
    try:
        if not state["incident"] or not state["triage_result"]:
            return {
                **state,
                "diagnosis_result": None,
                "workflow_status": "diagnosis_failed",
                "errors": state.get("errors", [])
                + ["Missing incident or triage result for diagnosis"],
            }

        diagnosis_agent = DemoDiagnosisAgent()
        diagnosis_result = diagnosis_agent.diagnose(
            state["incident"], state["triage_result"], state["evidence"]
        )

        return {
            **state,
            "diagnosis_result": diagnosis_result,
            "workflow_status": "diagnosis_complete",
        }

    except Exception as e:
        return {
            **state,
            "diagnosis_result": None,
            "workflow_status": "diagnosis_failed",
            "errors": state.get("errors", []) + [f"Diagnosis error: {str(e)}"],
        }


def verify_hypotheses_node(state: InvestigationState) -> InvestigationState:
    """Verify generated hypotheses.

    Args:
        state: Current investigation state

    Returns:
        Updated state with verification result
    """
    try:
        if not state["diagnosis_result"]:
            return {
                **state,
                "verification_result": None,
                "workflow_status": "verification_failed",
                "errors": state.get("errors", [])
                + ["No diagnosis result for verification"],
            }

        verifier = EvidenceVerifier()
        verification_result = verifier.verify(
            state["diagnosis_result"], state["evidence"]
        )

        return {
            **state,
            "verification_result": verification_result,
            "workflow_status": "verification_complete",
        }

    except Exception as e:
        return {
            **state,
            "verification_result": None,
            "workflow_status": "verification_failed",
            "errors": state.get("errors", []) + [f"Verification error: {str(e)}"],
        }


def propose_remediation_node(state: InvestigationState) -> InvestigationState:
    """Propose safe remediation actions.

    Args:
        state: Current investigation state

    Returns:
        Updated state with remediation plan
    """
    try:
        if not state["verification_result"]:
            return {
                **state,
                "remediation_plan": None,
                "workflow_status": "remediation_failed",
                "errors": state.get("errors", [])
                + ["No verification result for remediation planning"],
            }

        remediation_agent = DemoRemediationAgent()
        remediation_plan = remediation_agent.plan_remediation(
            state["verification_result"], state["evidence"]
        )

        return {
            **state,
            "remediation_plan": remediation_plan,
            "workflow_status": "remediation_complete",
        }

    except Exception as e:
        return {
            **state,
            "remediation_plan": None,
            "workflow_status": "remediation_failed",
            "errors": state.get("errors", []) + [f"Remediation error: {str(e)}"],
        }


def generate_report_node(state: InvestigationState) -> InvestigationState:
    """Generate incident report.

    Args:
        state: Current investigation state

    Returns:
        Updated state with incident report
    """
    try:
        # Check required components
        required = [
            ("incident", state.get("incident")),
            ("triage_result", state.get("triage_result")),
            ("diagnosis_result", state.get("diagnosis_result")),
            ("verification_result", state.get("verification_result")),
            ("remediation_plan", state.get("remediation_plan")),
        ]

        missing = [name for name, value in required if value is None]

        if missing:
            return {
                **state,
                "incident_report": None,
                "workflow_status": "report_generation_failed",
                "errors": state.get("errors", [])
                + [f"Missing required data for report: {', '.join(missing)}"],
            }

        incident_report = generate_incident_report(
            incident=state["incident"],
            triage_result=state["triage_result"],
            diagnosis_result=state["diagnosis_result"],
            verification_result=state["verification_result"],
            remediation_plan=state["remediation_plan"],
            evidence=state["evidence"],
        )

        return {
            **state,
            "incident_report": incident_report,
            "workflow_status": "complete",
        }

    except Exception as e:
        return {
            **state,
            "incident_report": None,
            "workflow_status": "report_generation_failed",
            "errors": state.get("errors", [])
            + [f"Report generation error: {str(e)}"],
        }


def build_investigation_graph() -> StateGraph:
    """Build the investigation workflow graph.

    Returns:
        Compiled StateGraph for incident investigation

    Note:
        Workflow order:
        START -> retrieve_evidence -> triage_incident -> generate_hypotheses
        -> verify_hypotheses -> propose_remediation -> generate_report -> END
    """
    workflow = StateGraph(InvestigationState)

    # Add nodes
    workflow.add_node("retrieve_evidence", retrieve_evidence_node)
    workflow.add_node("triage_incident", triage_incident_node)
    workflow.add_node("generate_hypotheses", generate_hypotheses_node)
    workflow.add_node("verify_hypotheses", verify_hypotheses_node)
    workflow.add_node("propose_remediation", propose_remediation_node)
    workflow.add_node("generate_report", generate_report_node)

    # Define edges
    workflow.set_entry_point("retrieve_evidence")
    workflow.add_edge("retrieve_evidence", "triage_incident")
    workflow.add_edge("triage_incident", "generate_hypotheses")
    workflow.add_edge("generate_hypotheses", "verify_hypotheses")
    workflow.add_edge("verify_hypotheses", "propose_remediation")
    workflow.add_edge("propose_remediation", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow.compile()


def run_investigation(
    incident: Incident,
    investigation_query: Optional[str] = None,
) -> InvestigationState:
    """Run complete incident investigation workflow.

    Args:
        incident: Incident to investigate
        investigation_query: Optional custom query for evidence retrieval

    Returns:
        Final investigation state with all results

    Note:
        This is a convenience function for Streamlit integration.
        All components run in offline demo mode with no LLM calls.
    """
    # Build and compile graph
    graph = build_investigation_graph()

    # Initialize state
    initial_state: InvestigationState = {
        "incident": incident,
        "investigation_query": investigation_query,
        "evidence": [],
        "triage_result": None,
        "diagnosis_result": None,
        "verification_result": None,
        "remediation_plan": None,
        "incident_report": None,
        "workflow_status": "started",
        "errors": [],
    }

    # Run workflow
    final_state = graph.invoke(initial_state)

    return final_state
