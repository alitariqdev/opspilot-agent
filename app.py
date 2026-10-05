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
from src.opspilot.upload_handler import (
    create_evidence_retriever_from_uploads,
    process_uploaded_logs,
    process_uploaded_runbooks,
)
from src.opspilot.upload_validator import validate_evidence_availability
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
            # Live mode
            try:
                config.validate_live_mode()
                st.success("**Mode:** Live LLM")
                st.caption(f"Model: {config.openai_model}")
            except ValueError as e:
                st.warning("**Mode:** Live (Incomplete)")
                st.caption("⚠️ Configuration required")
                with st.expander("Setup Instructions"):
                    st.markdown("""
                    Live mode requires:
                    1. Set `OPENAI_API_KEY` in .env file
                    2. Optionally set `OPENAI_MODEL`
                    3. For OpenRouter, set `OPENAI_BASE_URL`

                    See README.md for details.
                    """)

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
    if "evidence_mode" not in st.session_state:
        st.session_state.evidence_mode = "sample"
    if "uploaded_log_entries" not in st.session_state:
        st.session_state.uploaded_log_entries = []
    if "uploaded_runbook_lines" not in st.session_state:
        st.session_state.uploaded_runbook_lines = []

    # Evidence source selection
    st.header("Evidence Source")

    evidence_mode = st.radio(
        "Choose evidence source:",
        ["Sample Incident (Demo)", "Upload Your Own Files"],
        index=0 if st.session_state.evidence_mode == "sample" else 1,
        key="evidence_mode_radio",
        help="Use the included sample for demo, or upload your own logs and runbooks",
    )

    # Update session state
    st.session_state.evidence_mode = "sample" if "Sample" in evidence_mode else "upload"

    # Reset investigation when mode changes
    if "last_evidence_mode" not in st.session_state:
        st.session_state.last_evidence_mode = st.session_state.evidence_mode
    elif st.session_state.last_evidence_mode != st.session_state.evidence_mode:
        st.session_state.investigation_result = None
        st.session_state.investigation_error = None
        st.session_state.last_evidence_mode = st.session_state.evidence_mode

    st.markdown("---")

    # Incident selection (sample or custom)
    if st.session_state.evidence_mode == "sample":
        st.header("Sample Incident")
        incident = load_sample_incident()
    else:
        st.header("Custom Incident")
        # User must provide basic incident info
        col1, col2 = st.columns(2)
        with col1:
            incident_id = st.text_input("Incident ID", value="CUSTOM-001", key="custom_incident_id")
            incident_title = st.text_input(
                "Incident Title",
                value="Custom Incident Investigation",
                key="custom_incident_title"
            )
        with col2:
            incident_start_time = st.text_input(
                "Start Time (ISO 8601)",
                value="2024-03-15T14:00:00Z",
                key="custom_start_time"
            )
            incident_status = st.selectbox(
                "Status",
                ["investigating", "identified", "monitoring", "resolved"],
                key="custom_status"
            )

        incident_description = st.text_area(
            "Incident Description",
            value="Custom incident requiring investigation",
            key="custom_description",
            height=100
        )

        # Create custom incident object
        incident = Incident(
            incident_id=incident_id,
            title=incident_title,
            description=incident_description,
            symptoms=[],  # Will be extracted from logs
            start_time=incident_start_time,
            affected_services=[],  # Will be extracted from logs
            severity="unknown",
            status=incident_status,
        )

    # Display incident info based on mode
    if st.session_state.evidence_mode == "sample":
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
    else:
        # Upload mode
        st.subheader("Upload Evidence Files")

        st.info(
            "📁 Upload your log files and runbooks for incident analysis. "
            "All processing happens in-memory and files are never saved to disk."
        )

        # Upload logs
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Log Files")
            st.caption("Accepted formats: .log, .txt")
            st.caption("Maximum size per file: 10 MB")

            uploaded_logs = st.file_uploader(
                "Choose log files",
                type=["log", "txt"],
                accept_multiple_files=True,
                key="log_uploader",
                help="Upload one or more log files. Supports plain text, Docker JSON, and Kubernetes formats.",
            )

        with col2:
            st.markdown("### Runbooks")
            st.caption("Accepted formats: .md, .txt")
            st.caption("Maximum size per file: 10 MB")

            uploaded_runbooks = st.file_uploader(
                "Choose runbook files",
                type=["md", "txt"],
                accept_multiple_files=True,
                key="runbook_uploader",
                help="Upload operational runbooks or documentation files",
            )

        # Process uploads
        upload_errors = []

        if uploaded_logs or uploaded_runbooks:
            st.markdown("---")
            st.subheader("Upload Status")

            # Process log files
            if uploaded_logs:
                with st.spinner("Processing log files..."):
                    log_entries, log_filenames, log_errors = process_uploaded_logs(
                        uploaded_logs
                    )
                    st.session_state.uploaded_log_entries = log_entries
                    upload_errors.extend(log_errors)

                    if log_entries:
                        st.success(
                            f"✓ Loaded {len(log_entries)} log entries from {len(log_filenames)} file(s)"
                        )
                        with st.expander("Log Files"):
                            for filename in log_filenames:
                                st.markdown(f"- `{filename}`")
                    elif log_errors:
                        st.error("❌ No valid log entries could be loaded")

            # Process runbook files
            if uploaded_runbooks:
                with st.spinner("Processing runbook files..."):
                    (
                        runbook_lines,
                        runbook_filenames,
                        runbook_errors,
                    ) = process_uploaded_runbooks(uploaded_runbooks)
                    st.session_state.uploaded_runbook_lines = runbook_lines
                    upload_errors.extend(runbook_errors)

                    if runbook_lines:
                        st.success(
                            f"✓ Loaded {len(runbook_lines)} runbook lines from {len(runbook_filenames)} file(s)"
                        )
                        with st.expander("Runbook Files"):
                            for filename in runbook_filenames:
                                st.markdown(f"- `{filename}`")
                    elif runbook_errors:
                        st.error("❌ No valid runbook content could be loaded")

            # Show validation errors
            if upload_errors:
                with st.expander("⚠️ Upload Errors", expanded=True):
                    for error in upload_errors:
                        st.warning(error)

            # Validate that we have at least some evidence
            log_count = len(st.session_state.uploaded_log_entries)
            runbook_count = len(st.session_state.uploaded_runbook_lines)

            is_valid, validation_error = validate_evidence_availability(
                log_count, runbook_count
            )

            if not is_valid:
                st.error(validation_error)
        else:
            st.info("👆 Please upload at least one log file or runbook to begin investigation")

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

        # Validate evidence for upload mode
        if st.session_state.evidence_mode == "upload":
            log_count = len(st.session_state.uploaded_log_entries)
            runbook_count = len(st.session_state.uploaded_runbook_lines)

            is_valid, validation_error = validate_evidence_availability(
                log_count, runbook_count
            )

            if not is_valid:
                st.session_state.investigation_error = [validation_error]
                st.error(validation_error)
            else:
                with st.spinner("Running investigation workflow..."):
                    try:
                        # Create evidence retriever from uploads
                        evidence_retriever = create_evidence_retriever_from_uploads(
                            st.session_state.uploaded_log_entries,
                            st.session_state.uploaded_runbook_lines,
                        )

                        # Run investigation with custom evidence
                        result = run_investigation(
                            incident=incident,
                            investigation_query=investigation_query,
                            evidence_retriever=evidence_retriever,
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
        else:
            # Sample mode - use default workflow
            with st.spinner("Running investigation workflow..."):
                try:
                    # Run investigation with sample data
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
