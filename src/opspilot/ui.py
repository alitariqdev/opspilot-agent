"""UI presentation helpers for OpsPilot Streamlit application."""

from typing import List

import streamlit as st

from src.opspilot.models import (
    EvidenceChunk,
    HypothesisStatus,
    RemediationAction,
    RootCauseHypothesis,
    Severity,
    TimelineEvent,
)


def format_severity_badge(severity: Severity) -> str:
    """Format severity as a colored badge.

    Args:
        severity: Severity level

    Returns:
        Formatted severity string with emoji indicator
    """
    severity_map = {
        Severity.SEV1: "🔴 SEV1 (Critical)",
        Severity.SEV2: "🟠 SEV2 (High)",
        Severity.SEV3: "🟡 SEV3 (Medium)",
        Severity.SEV4: "⚪ SEV4 (Low)",
    }
    return severity_map.get(severity, str(severity.value))


def format_hypothesis_status(status: HypothesisStatus) -> str:
    """Format hypothesis status with indicator.

    Args:
        status: Hypothesis status

    Returns:
        Formatted status string
    """
    status_map = {
        HypothesisStatus.SUPPORTED: "✓ Supported",
        HypothesisStatus.PARTIALLY_SUPPORTED: "◐ Partially Supported",
        HypothesisStatus.UNSUPPORTED: "✗ Unsupported",
    }
    return status_map.get(status, str(status.value))


def render_timeline_table(timeline: List[TimelineEvent]) -> None:
    """Render timeline events as a table.

    Args:
        timeline: List of timeline events
    """
    if not timeline:
        st.info("No timeline events available")
        return

    data = []
    for event in timeline:
        data.append(
            {
                "Timestamp": event.timestamp or "Unknown",
                "Service": event.service or "Unknown",
                "Description": event.description,
                "Evidence ID": event.evidence_id,
            }
        )

    st.dataframe(data, use_container_width=True, hide_index=True)


def render_evidence_table(evidence: List[EvidenceChunk]) -> None:
    """Render evidence chunks as a table.

    Args:
        evidence: List of evidence chunks
    """
    if not evidence:
        st.info("No evidence available")
        return

    data = []
    for ev in evidence:
        data.append(
            {
                "Evidence ID": ev.evidence_id,
                "Source": ev.source_file,
                "Type": ev.source_type,
                "Line": ev.line_number,
                "Score": f"{ev.score:.2f}",
                "Content": ev.content[:100] + "..." if len(ev.content) > 100 else ev.content,
            }
        )

    st.dataframe(data, use_container_width=True, hide_index=True)


def render_hypothesis_card(hypothesis: RootCauseHypothesis) -> None:
    """Render a single hypothesis as a card.

    Args:
        hypothesis: Root cause hypothesis
    """
    # Determine styling based on status
    if hypothesis.status == HypothesisStatus.SUPPORTED:
        status_color = "green"
    elif hypothesis.status == HypothesisStatus.PARTIALLY_SUPPORTED:
        status_color = "orange"
    elif hypothesis.status == HypothesisStatus.UNSUPPORTED:
        status_color = "red"
    else:
        status_color = "gray"

    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            st.metric("Rank", f"#{hypothesis.rank}")

        with col2:
            if hypothesis.status:
                st.markdown(
                    f"**Status:** :{status_color}[{format_hypothesis_status(hypothesis.status)}]"
                )
            else:
                st.markdown("**Status:** Unknown")

        with col3:
            st.metric("Confidence", f"{hypothesis.confidence:.2f}")

        st.markdown(f"### {hypothesis.title}")
        st.markdown(hypothesis.description)

        with st.expander("Reasoning"):
            st.markdown(hypothesis.reasoning)

        if hypothesis.evidence_ids:
            with st.expander(f"Supporting Evidence ({len(hypothesis.evidence_ids)} chunks)"):
                for eid in hypothesis.evidence_ids:
                    st.code(eid, language=None)

        if hypothesis.missing_evidence:
            with st.expander("Missing Evidence"):
                for missing in hypothesis.missing_evidence:
                    st.markdown(f"- {missing}")

        st.markdown("---")


def render_remediation_action(action: RemediationAction) -> None:
    """Render a single remediation action.

    Args:
        action: Remediation action
    """
    # Risk level indicators
    risk_colors = {
        "low": "green",
        "medium": "orange",
        "high": "red",
        "critical": "red",
    }

    risk_color = risk_colors.get(action.risk_level.value, "gray")

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.markdown(f"### {action.priority}. {action.title}")

        with col2:
            st.markdown(f"**Risk:** :{risk_color}[{action.risk_level.value.upper()}]")

        with col3:
            approval_text = "✓ Required" if action.requires_human_approval else "Not Required"
            st.markdown(f"**Approval:** {approval_text}")

        st.markdown(f"**Rationale:** {action.rationale}")
        st.markdown(f"**Description:** {action.description}")

        with st.expander("Validation & Rollback"):
            st.markdown(f"**Validation:** {action.validation_step}")
            st.markdown(f"**Rollback:** {action.rollback_consideration}")

        if action.supporting_evidence_ids:
            with st.expander(f"Supporting Evidence ({len(action.supporting_evidence_ids)} chunks)"):
                for eid in action.supporting_evidence_ids:
                    st.code(eid, language=None)

        st.markdown("---")


def render_workflow_sidebar() -> None:
    """Render workflow stages in sidebar."""
    with st.sidebar:
        st.markdown("### Workflow Stages")

        stages = [
            "1. Evidence Retrieval",
            "2. Incident Triage",
            "3. Hypothesis Generation",
            "4. Hypothesis Verification",
            "5. Remediation Planning",
            "6. Report Generation",
        ]

        for stage in stages:
            st.markdown(f"- {stage}")

        st.markdown("---")
        st.markdown("### Safety Boundary")
        st.markdown("""
        **Automated:**
        - Analysis
        - Evidence retrieval
        - Report generation

        **Human Approval:**
        - All remediation actions
        - Production changes
        """)
