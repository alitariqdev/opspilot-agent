"""Incident report generation for OpsPilot."""

from typing import Dict, List

from src.opspilot.models import (
    DiagnosisResult,
    EvidenceChunk,
    Incident,
    RemediationPlan,
    TriageResult,
    VerificationResult,
)


def _escape_markdown(text: str) -> str:
    """Escape markdown special characters in text.

    Args:
        text: Text to escape

    Returns:
        Escaped text safe for Markdown
    """
    # Escape basic markdown characters that might appear in log content
    replacements = {
        "|": "\\|",
        "[": "\\[",
        "]": "\\]",
    }
    result = text
    for char, escaped in replacements.items():
        result = result.replace(char, escaped)
    return result


def _format_evidence_reference(evidence_id: str, evidence_map: Dict[str, EvidenceChunk]) -> str:
    """Format evidence reference with source and line number.

    Args:
        evidence_id: Evidence identifier
        evidence_map: Map of evidence IDs to chunks

    Returns:
        Formatted reference string
    """
    if evidence_id not in evidence_map:
        return f"`{evidence_id}` (not found)"

    ev = evidence_map[evidence_id]
    return f"`{evidence_id}` ({ev.source_file}:{ev.line_number})"


def generate_incident_report(
    incident: Incident,
    triage_result: TriageResult,
    diagnosis_result: DiagnosisResult,
    verification_result: VerificationResult,
    remediation_plan: RemediationPlan,
    evidence: List[EvidenceChunk],
) -> str:
    """Generate a professional Markdown incident report.

    Args:
        incident: Incident metadata
        triage_result: Triage assessment
        diagnosis_result: Diagnosis with hypotheses
        verification_result: Verification results
        remediation_plan: Remediation recommendations
        evidence: All evidence used in analysis

    Returns:
        Markdown-formatted incident report

    Note:
        - Report does not claim unsupported conclusions
        - Rejected hypotheses clearly identified
        - Suitable for download from Streamlit
        - Deterministic (no timestamps unless provided)
    """
    # Build evidence map for references
    evidence_map = {ev.evidence_id: ev for ev in evidence}

    report_lines = []

    # Header
    report_lines.append(f"# Incident Report: {incident.title}")
    report_lines.append("")
    report_lines.append(f"**Incident ID:** {incident.incident_id}")
    report_lines.append(f"**Status:** {incident.status}")
    report_lines.append("")

    # Executive Summary
    report_lines.append("## Executive Summary")
    report_lines.append("")
    report_lines.append(f"**Severity:** {triage_result.severity.value}")
    report_lines.append(
        f"**Affected Services:** {', '.join(triage_result.affected_services) if triage_result.affected_services else 'Unknown'}"
    )
    report_lines.append(f"**Start Time:** {incident.start_time}")
    report_lines.append("")
    report_lines.append(f"{_escape_markdown(incident.description)}")
    report_lines.append("")

    # Symptoms
    report_lines.append("## Observed Symptoms")
    report_lines.append("")
    if triage_result.symptoms:
        for symptom in triage_result.symptoms:
            report_lines.append(f"- {_escape_markdown(symptom)}")
    else:
        report_lines.append("- No specific symptoms extracted from evidence")
    report_lines.append("")

    # Timeline
    report_lines.append("## Evidence-Based Timeline")
    report_lines.append("")
    if triage_result.timeline:
        for event in triage_result.timeline:
            timestamp_str = event.timestamp if event.timestamp else "Unknown time"
            service_str = f"[{event.service}]" if event.service else ""
            evidence_ref = _format_evidence_reference(event.evidence_id, evidence_map)
            report_lines.append(
                f"- **{timestamp_str}** {service_str} {_escape_markdown(event.description)} "
                f"(Evidence: {evidence_ref})"
            )
    else:
        report_lines.append("- No timeline events available")
    report_lines.append("")

    # Root Cause Analysis
    report_lines.append("## Root Cause Analysis")
    report_lines.append("")

    if verification_result.verified_hypotheses:
        report_lines.append("### Verified Hypotheses")
        report_lines.append("")
        report_lines.append(
            "The following hypotheses have supporting evidence and passed verification:"
        )
        report_lines.append("")

        for hyp in verification_result.verified_hypotheses:
            report_lines.append(f"#### {hyp.rank}. {_escape_markdown(hyp.title)}")
            report_lines.append("")
            report_lines.append(f"**Status:** {hyp.status.value if hyp.status else 'Unknown'}")
            report_lines.append(f"**Confidence:** {hyp.confidence:.2f}")
            report_lines.append("")
            report_lines.append(f"{_escape_markdown(hyp.description)}")
            report_lines.append("")
            report_lines.append("**Reasoning:**")
            report_lines.append("")
            report_lines.append(_escape_markdown(hyp.reasoning))
            report_lines.append("")

            if hyp.evidence_ids:
                report_lines.append("**Supporting Evidence:**")
                report_lines.append("")
                for eid in hyp.evidence_ids[:5]:  # Limit to first 5 for readability
                    ref = _format_evidence_reference(eid, evidence_map)
                    report_lines.append(f"- {ref}")
                if len(hyp.evidence_ids) > 5:
                    report_lines.append(f"- _(and {len(hyp.evidence_ids) - 5} more)_")
                report_lines.append("")

            if hyp.missing_evidence:
                report_lines.append("**Missing Evidence:**")
                report_lines.append("")
                for missing in hyp.missing_evidence:
                    report_lines.append(f"- {_escape_markdown(missing)}")
                report_lines.append("")

    if verification_result.rejected_hypothesis_ids:
        report_lines.append("### Rejected Hypotheses")
        report_lines.append("")
        report_lines.append(
            f"The following {len(verification_result.rejected_hypothesis_ids)} hypothesis(es) "
            "were rejected during verification due to insufficient or contradicting evidence:"
        )
        report_lines.append("")

        for hyp in diagnosis_result.hypotheses:
            if hyp.hypothesis_id in verification_result.rejected_hypothesis_ids:
                report_lines.append(f"- {_escape_markdown(hyp.title)}")

        report_lines.append("")

    if not verification_result.verified_hypotheses and not verification_result.rejected_hypothesis_ids:
        report_lines.append("**Status:** No hypotheses could be generated or verified.")
        report_lines.append("")
        report_lines.append(
            "Insufficient evidence available for root cause analysis. "
            "Further investigation required."
        )
        report_lines.append("")

    # Remediation Plan
    report_lines.append("## Recommended Actions")
    report_lines.append("")

    if remediation_plan.actions:
        # Group by category
        categories = {
            "investigation": [],
            "containment": [],
            "recovery": [],
            "prevention": [],
        }

        for action in remediation_plan.actions:
            if action.category in categories:
                categories[action.category].append(action)

        for category_name, category_actions in categories.items():
            if not category_actions:
                continue

            report_lines.append(f"### {category_name.title()}")
            report_lines.append("")

            for action in category_actions:
                report_lines.append(f"#### {action.priority}. {_escape_markdown(action.title)}")
                report_lines.append("")
                report_lines.append(f"**Risk Level:** {action.risk_level.value}")
                report_lines.append(
                    f"**Requires Approval:** {'Yes' if action.requires_human_approval else 'No'}"
                )
                report_lines.append("")
                report_lines.append(f"{_escape_markdown(action.description)}")
                report_lines.append("")
                report_lines.append(f"**Rationale:** {_escape_markdown(action.rationale)}")
                report_lines.append("")
                report_lines.append(
                    f"**Validation:** {_escape_markdown(action.validation_step)}"
                )
                report_lines.append("")
                report_lines.append(
                    f"**Rollback:** {_escape_markdown(action.rollback_consideration)}"
                )
                report_lines.append("")
    else:
        report_lines.append(
            "No remediation actions could be generated. "
            "Additional investigation required before proceeding."
        )
        report_lines.append("")

    # Limitations
    report_lines.append("## Analysis Limitations")
    report_lines.append("")
    report_lines.append(
        "This analysis has the following limitations that should be considered:"
    )
    report_lines.append("")

    all_limitations = set()
    all_limitations.update(diagnosis_result.limitations)
    all_limitations.update(remediation_plan.limitations)

    if all_limitations:
        for limitation in sorted(all_limitations):
            report_lines.append(f"- {_escape_markdown(limitation)}")
    else:
        report_lines.append("- No specific limitations documented")

    report_lines.append("")

    # Evidence References
    report_lines.append("## Evidence References")
    report_lines.append("")
    report_lines.append(
        f"This analysis is based on {len(evidence)} evidence chunk(s) "
        "retrieved from logs and runbooks:"
    )
    report_lines.append("")

    # Group evidence by source file
    evidence_by_file: Dict[str, List[EvidenceChunk]] = {}
    for ev in evidence:
        if ev.source_file not in evidence_by_file:
            evidence_by_file[ev.source_file] = []
        evidence_by_file[ev.source_file].append(ev)

    for source_file in sorted(evidence_by_file.keys()):
        file_evidence = evidence_by_file[source_file]
        report_lines.append(f"### {source_file}")
        report_lines.append("")
        report_lines.append(f"- {len(file_evidence)} evidence chunk(s)")
        report_lines.append(
            f"- Lines: {min(ev.line_number for ev in file_evidence)} - "
            f"{max(ev.line_number for ev in file_evidence)}"
        )
        report_lines.append("")

    # Human Review Notice
    report_lines.append("## Human Review Required")
    report_lines.append("")
    report_lines.append(
        "⚠️ **IMPORTANT:** This analysis is generated by an automated system "
        "and requires human review before taking any action."
    )
    report_lines.append("")
    report_lines.append("Human review is required for:")
    report_lines.append("")
    report_lines.append("- Validating root cause hypotheses against domain knowledge")
    report_lines.append("- Approving any state-changing remediation actions")
    report_lines.append("- Verifying evidence interpretation is correct")
    report_lines.append("- Assessing risk and impact of proposed actions")
    report_lines.append("- Making final decisions on incident response")
    report_lines.append("")
    report_lines.append(
        "Do not execute any remediation actions without proper review, "
        "testing, and approval according to your organization's change management procedures."
    )
    report_lines.append("")

    # Footer
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("*Generated by OpsPilot Agent - Evidence-Grounded Incident Diagnosis*")
    report_lines.append("")

    return "\n".join(report_lines)
