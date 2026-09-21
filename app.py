"""OpsPilot - Evidence-Grounded Incident Diagnosis

Main Streamlit application entry point.
"""

import json
from pathlib import Path

import streamlit as st

from src.opspilot.config import get_config
from src.opspilot.models import Incident
from src.opspilot.ui import (
    format_severity_badge,
    render_evidence_table,
    render_hypothesis_card,
    render_remediation_action,
    render_timeline_table,
    render_workflow_sidebar,
)
from src.opspilot.workflow import run_investigation


def get_app_root() -> Path:
    """Get application root directory.

    Returns:
        Path to app root directory
    """
    return Path(__file__).parent


def load_sample_incident() -> Incident:
    """Load the sample incident from data directory.

    Returns:
        Sample incident object
    """
    app_root = get_app_root()
    incident_file = app_root / "data" / "incidents" / "incident_001.json"

    with open(incident_file, "r") as f:
        incident_data = json.load(f)

    return Incident(**incident_data)


def main():
    """Render the OpsPilot application."""
    config = get_config()

    st.set_page_config(
        page_title="OpsPilot - Incident Diagnosis",
        page_icon="🔍",
        layout="wide",
    )

    # Sidebar
    with st.sidebar:
        st.title("OpsPilot")

        mode = config.opspilot_mode.upper()
        if mode == "DEMO":
            st.info("**Mode:** Offline Demo")
        else:
            st.success("**Mode:** Live")

        st.markdown("---")
        render_workflow_sidebar()

        st.markdown("---")
        st.caption("v1.0.0 - Development")

    # Main content
    st.title("OpsPilot - Evidence-Grounded Incident Diagnosis")
    st.markdown(
        "Automated incident analysis using logs, runbooks, and evidence-based reasoning"
    )

    st.warning(
        "⚠️ **Human Review Required** — All findings require validation before action. "
        "Never execute remediation without proper review and approval."
    )

    st.markdown("---")

    # Initialize session state
    if "investigation_result" not in st.session_state:
        st.session_state.investigation_result = None
    if "investigation_error" not in st.session_state:
        st.session_state.investigation_error = None

    # Incident selection
    st.header("Incident Selection")

    incident = load_sample_incident()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"Incident: {incident.incident_id}")
        st.markdown(f"**Title:** {incident.title}")
        st.markdown(f"**Start Time:** {incident.start_time}")
        st.markdown(f"**Status:** {incident.status}")

    with col2:
        st.markdown("**Affected Services:**")
        for service in incident.affected_services:
            st.markdown(f"- {service}")

    with st.expander("Incident Description"):
        st.markdown(incident.description)

    with st.expander("Reported Symptoms"):
        for symptom in incident.symptoms:
            st.markdown(f"- {symptom}")

    # Available data files
    with st.expander("Available Data Files"):
        app_root = get_app_root()
        log_file = app_root / "data" / "incidents" / "incident_001_logs.txt"
        runbook_dir = app_root / "data" / "runbooks"

        st.markdown(f"**Log File:** `{log_file.name}`")
        st.markdown(f"**Runbook Directory:** `{runbook_dir.name}/`")

        if runbook_dir.exists():
            runbooks = list(runbook_dir.glob("*.md"))
            for rb in runbooks:
                st.markdown(f"- `{rb.name}`")

    st.markdown("---")

    # Investigation controls
    st.header("Investigation Controls")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        investigation_query = st.text_input(
            "Investigation Query",
            value="database connection pool exhausted 503 errors",
            help="Keywords to guide evidence retrieval from logs and runbooks",
        )

    with col2:
        top_k = st.number_input(
            "Evidence Limit",
            min_value=5,
            max_value=30,
            value=15,
            help="Number of evidence chunks to retrieve",
        )

    with col3:
        st.markdown("")  # Spacing
        st.markdown("")  # Spacing

    col1, col2, col3 = st.columns([1, 1, 4])

    with col1:
        run_button = st.button("🔍 Run Investigation", type="primary", use_container_width=True)

    with col2:
        reset_button = st.button("🔄 Reset", use_container_width=True)

    if reset_button:
        st.session_state.investigation_result = None
        st.session_state.investigation_error = None
        st.rerun()

    if run_button:
        st.session_state.investigation_error = None

        with st.spinner("Running investigation workflow..."):
            try:
                # Run investigation
                result = run_investigation(
                    incident=incident,
                    investigation_query=investigation_query,
                )

                st.session_state.investigation_result = result

                if result["workflow_status"] == "complete":
                    st.success("✓ Investigation complete")
                else:
                    st.warning(
                        f"Investigation completed with status: {result['workflow_status']}"
                    )

                    if result.get("errors"):
                        st.session_state.investigation_error = result["errors"]

            except Exception as e:
                st.session_state.investigation_error = [
                    f"Investigation failed: {str(e)}"
                ]
                st.error("Investigation encountered an error. See details below.")

    # Display errors if any
    if st.session_state.investigation_error:
        with st.expander("⚠️ Errors", expanded=True):
            for error in st.session_state.investigation_error:
                st.error(error)

    # Display results
    if st.session_state.investigation_result:
        result = st.session_state.investigation_result

        if result["workflow_status"] == "complete":
            st.markdown("---")
            st.header("Investigation Results")

            # Create tabs
            tabs = st.tabs(
                [
                    "Overview",
                    "Timeline & Evidence",
                    "Root Cause Hypotheses",
                    "Remediation Plan",
                    "Incident Report",
                ]
            )

            # Tab 1: Overview
            with tabs[0]:
                st.subheader("Investigation Overview")

                triage = result["triage_result"]

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Severity", format_severity_badge(triage.severity))
                    st.metric("Confidence", f"{triage.confidence:.2f}")

                with col2:
                    st.metric("Evidence Chunks", len(result["evidence"]))
                    st.metric("Timeline Events", len(triage.timeline))

                with col3:
                    st.metric("Hypotheses Generated", len(result["diagnosis_result"].hypotheses))
                    st.metric(
                        "Hypotheses Verified",
                        len(result["verification_result"].verified_hypotheses),
                    )

                st.markdown("---")

                st.markdown("**Affected Services:**")
                for service in triage.affected_services:
                    st.markdown(f"- {service}")

                st.markdown("**Symptoms:**")
                for symptom in triage.symptoms:
                    st.markdown(f"- {symptom}")

                st.markdown("---")

                with st.expander("Triage Rationale"):
                    st.markdown(triage.rationale)

                if triage.requires_human_review:
                    st.warning(
                        "⚠️ This incident requires human review before proceeding with remediation."
                    )

            # Tab 2: Timeline & Evidence
            with tabs[1]:
                st.subheader("Evidence-Based Timeline")
                render_timeline_table(triage.timeline)

                st.markdown("---")

                st.subheader("Retrieved Evidence")
                st.caption(
                    f"Showing {len(result['evidence'])} evidence chunks from logs and runbooks"
                )
                render_evidence_table(result["evidence"])

            # Tab 3: Root Cause Hypotheses
            with tabs[2]:
                st.subheader("Root Cause Hypotheses")

                verification = result["verification_result"]
                diagnosis = result["diagnosis_result"]

                if verification.verified_hypotheses:
                    st.markdown(f"**Verified:** {len(verification.verified_hypotheses)} hypotheses")

                    for hyp in verification.verified_hypotheses:
                        render_hypothesis_card(hyp)
                else:
                    st.info("No verified hypotheses available")

                if verification.rejected_hypothesis_ids:
                    st.markdown("---")
                    st.markdown("### Rejected Hypotheses")
                    st.caption(
                        f"{len(verification.rejected_hypothesis_ids)} hypotheses were rejected during verification"
                    )

                    for hyp in diagnosis.hypotheses:
                        if hyp.hypothesis_id in verification.rejected_hypothesis_ids:
                            st.markdown(f"- {hyp.title}")

                if diagnosis.limitations:
                    st.markdown("---")
                    st.markdown("### Analysis Limitations")
                    for limitation in diagnosis.limitations:
                        st.markdown(f"- {limitation}")

            # Tab 4: Remediation Plan
            with tabs[3]:
                st.subheader("Remediation Plan")

                remediation = result["remediation_plan"]

                if remediation.actions:
                    st.markdown(f"**Total Actions:** {len(remediation.actions)}")
                    st.caption(remediation.summary)

                    st.markdown("---")

                    # Group by category
                    categories = {
                        "investigation": [],
                        "containment": [],
                        "recovery": [],
                        "prevention": [],
                    }

                    for action in remediation.actions:
                        if action.category in categories:
                            categories[action.category].append(action)

                    # Render by category
                    if categories["investigation"]:
                        st.markdown("## Investigation Actions")
                        for action in categories["investigation"]:
                            render_remediation_action(action)

                    if categories["containment"]:
                        st.markdown("## Containment Actions")
                        for action in categories["containment"]:
                            render_remediation_action(action)

                    if categories["recovery"]:
                        st.markdown("## Recovery Actions")
                        for action in categories["recovery"]:
                            render_remediation_action(action)

                    if categories["prevention"]:
                        st.markdown("## Prevention Actions")
                        for action in categories["prevention"]:
                            render_remediation_action(action)

                    if remediation.limitations:
                        st.markdown("---")
                        st.markdown("### Plan Limitations")
                        for limitation in remediation.limitations:
                            st.markdown(f"- {limitation}")

                    st.warning(
                        "⚠️ **Do not execute these actions without proper review and approval.** "
                        "All remediation requires human validation and change management."
                    )
                else:
                    st.info("No remediation actions generated")

            # Tab 5: Incident Report
            with tabs[4]:
                st.subheader("Incident Report")

                report = result["incident_report"]

                if report:
                    st.markdown(report)

                    st.markdown("---")

                    # Download button
                    safe_filename = incident.incident_id.replace("/", "_").replace("\\", "_")
                    filename = f"incident_report_{safe_filename}.md"

                    st.download_button(
                        label="📥 Download Report (Markdown)",
                        data=report.encode("utf-8"),
                        file_name=filename,
                        mime="text/markdown",
                    )
                else:
                    st.error("Report generation failed")


if __name__ == "__main__":
    main()
