"""Safe remediation planning agent for OpsPilot."""

import hashlib
from typing import List

from src.opspilot.models import (
    EvidenceChunk,
    RemediationAction,
    RemediationPlan,
    RiskLevel,
    VerificationResult,
)


def _generate_action_id(title: str, priority: int) -> str:
    """Generate a stable action ID.

    Args:
        title: Action title
        priority: Action priority

    Returns:
        Stable action identifier
    """
    content = f"{title}:{priority}"
    hash_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"action_{hash_digest[:16]}"


def _extract_runbook_recommendations(evidence_list: List[EvidenceChunk]) -> dict:
    """Extract runbook recommendations from evidence.

    Args:
        evidence_list: List of evidence chunks

    Returns:
        Dictionary of recommendations by category
    """
    recommendations = {
        "investigation": [],
        "containment": [],
        "recovery": [],
        "prevention": [],
    }

    for evidence in evidence_list:
        if evidence.source_type != "runbook":
            continue

        content_lower = evidence.content.lower()

        # Investigation actions
        if any(
            keyword in content_lower
            for keyword in [
                "check",
                "review",
                "identify",
                "analyze",
                "monitor",
                "query the database",
            ]
        ):
            recommendations["investigation"].append(evidence)

        # Containment actions
        if any(
            keyword in content_lower
            for keyword in ["scale", "increase", "restart", "isolate", "disable"]
        ):
            recommendations["containment"].append(evidence)

        # Recovery actions
        if any(
            keyword in content_lower
            for keyword in ["restore", "rollback", "recover", "fix"]
        ):
            recommendations["recovery"].append(evidence)

        # Prevention actions
        if any(
            keyword in content_lower
            for keyword in [
                "implement",
                "establish",
                "configure",
                "set up alerts",
                "long-term",
            ]
        ):
            recommendations["prevention"].append(evidence)

    return recommendations


class DemoRemediationAgent:
    """Deterministic demo remediation planning agent for offline operation.

    This agent generates safe remediation recommendations based on verified
    hypotheses and runbook evidence. All state-changing actions require
    human approval and are never executed automatically.
    """

    def plan_remediation(
        self,
        verification_result: VerificationResult,
        evidence: List[EvidenceChunk],
    ) -> RemediationPlan:
        """Generate safe remediation plan based on verified hypotheses.

        Args:
            verification_result: Verification result with verified hypotheses
            evidence: Available evidence including runbooks

        Returns:
            RemediationPlan with recommended actions

        Note:
            - Only generates recommendations from verified hypotheses
            - All state-changing actions require human approval
            - Never executes actions automatically
            - Actions are categorized and prioritized
        """
        # Handle insufficient verified hypotheses
        if not verification_result.verified_hypotheses:
            return RemediationPlan(
                incident_id=verification_result.incident_id,
                actions=[],
                summary="No verified hypotheses available. Cannot generate remediation plan without supported root cause analysis.",
                limitations=[
                    "No verified hypotheses to base recommendations on",
                    "Requires additional investigation before remediation",
                ],
                requires_human_approval=True,
            )

        # Extract runbook recommendations
        runbook_recs = _extract_runbook_recommendations(evidence)

        actions: List[RemediationAction] = []
        priority = 1

        # Get top verified hypothesis
        top_hypothesis = verification_result.verified_hypotheses[0]

        # === INVESTIGATION ACTIONS ===

        # Action 1: Check connection pool utilization
        if any(
            "pool" in ev.content.lower() and "check" in ev.content.lower()
            for ev in runbook_recs["investigation"]
        ):
            supporting_ids = [
                ev.evidence_id
                for ev in runbook_recs["investigation"]
                if "pool" in ev.content.lower() and "check" in ev.content.lower()
            ][:2]

            actions.append(
                RemediationAction(
                    action_id=_generate_action_id(
                        "Check connection pool utilization", priority
                    ),
                    title="Check connection pool utilization",
                    description="Review database connection pool metrics to identify current active connections vs. pool limit. Look for sustained high utilization (>90%).",
                    rationale=f"Verified hypothesis: {top_hypothesis.title}. Need to confirm current pool state.",
                    priority=priority,
                    risk_level=RiskLevel.LOW,
                    category="investigation",
                    supporting_evidence_ids=supporting_ids,
                    requires_human_approval=False,
                    validation_step="Verify that connection pool metrics are accessible and show current utilization percentage",
                    rollback_consideration="Read-only operation; no rollback needed",
                )
            )
            priority += 1

        # Action 2: Identify long-running queries
        if any(
            "long-running" in ev.content.lower() and "query" in ev.content.lower()
            for ev in runbook_recs["investigation"]
        ):
            supporting_ids = [
                ev.evidence_id
                for ev in runbook_recs["investigation"]
                if "long-running" in ev.content.lower()
                or "query" in ev.content.lower()
            ][:2]

            actions.append(
                RemediationAction(
                    action_id=_generate_action_id(
                        "Identify long-running queries", priority
                    ),
                    title="Identify long-running queries",
                    description="Query the database for active queries and their duration. Check for queries running longer than expected (>60 seconds). Identify the source application or worker.",
                    rationale="Evidence shows potential long-running query impact. Need to identify specific queries and their sources.",
                    priority=priority,
                    risk_level=RiskLevel.LOW,
                    category="investigation",
                    supporting_evidence_ids=supporting_ids,
                    requires_human_approval=False,
                    validation_step="Confirm query list is retrieved and duration information is accurate",
                    rollback_consideration="Read-only database query; no rollback needed",
                )
            )
            priority += 1

        # === CONTAINMENT ACTIONS ===

        # Action 3: Contact application owners (for long-running queries)
        if "query" in top_hypothesis.title.lower():
            actions.append(
                RemediationAction(
                    action_id=_generate_action_id(
                        "Contact application owners", priority
                    ),
                    title="Contact application owners of long-running queries",
                    description="Locate the team responsible for the source application generating long-running queries. Coordinate with them to understand if the queries are expected or can be safely terminated.",
                    rationale="Safety requirement: Do not automatically terminate queries without approval from application owners. Queries may be critical batch operations.",
                    priority=priority,
                    risk_level=RiskLevel.LOW,
                    category="containment",
                    supporting_evidence_ids=top_hypothesis.evidence_ids[:2],
                    requires_human_approval=True,
                    validation_step="Confirm contact has been made and response received from application owners",
                    rollback_consideration="Communication action; no technical rollback needed",
                )
            )
            priority += 1

        # Action 4: Scale connection pool (if infrastructure allows)
        if any(
            "scale" in ev.content.lower() or "increase" in ev.content.lower()
            for ev in runbook_recs["containment"]
        ):
            supporting_ids = [
                ev.evidence_id
                for ev in runbook_recs["containment"]
                if "scale" in ev.content.lower() or "increase" in ev.content.lower()
            ][:2]

            actions.append(
                RemediationAction(
                    action_id=_generate_action_id(
                        "Scale connection pool", priority
                    ),
                    title="Temporarily increase connection pool size",
                    description="Increase connection pool size if infrastructure allows. Monitor database server resource utilization (CPU, memory, connections) to ensure server can handle additional connections.",
                    rationale="Pool exhaustion verified. Temporarily increasing pool size can provide immediate relief while root cause is addressed.",
                    priority=priority,
                    risk_level=RiskLevel.MEDIUM,
                    category="containment",
                    supporting_evidence_ids=supporting_ids,
                    requires_human_approval=True,
                    validation_step="Verify connection pool size increased and services can acquire connections. Monitor database server resources.",
                    rollback_consideration="Revert connection pool size to original value if database performance degrades",
                )
            )
            priority += 1

        # === RECOVERY ACTIONS ===

        # Action 5: Restart affected services (last resort)
        if any(
            "restart" in ev.content.lower()
            for ev in runbook_recs["containment"] + runbook_recs["recovery"]
        ):
            supporting_ids = [
                ev.evidence_id
                for ev in runbook_recs["containment"] + runbook_recs["recovery"]
                if "restart" in ev.content.lower()
            ][:2]

            actions.append(
                RemediationAction(
                    action_id=_generate_action_id(
                        "Restart affected services", priority
                    ),
                    title="Restart affected services (last resort)",
                    description="If connection leaks are suspected and pool cannot be expanded, perform rolling restart of affected services to release leaked connections. Coordinate with on-call team.",
                    rationale="Last resort option if investigation reveals connection leaks and pool scaling is not viable.",
                    priority=priority,
                    risk_level=RiskLevel.HIGH,
                    category="recovery",
                    supporting_evidence_ids=supporting_ids,
                    requires_human_approval=True,
                    validation_step="Confirm services restarted successfully and are accepting traffic. Verify connection pool utilization decreases.",
                    rollback_consideration="If restart causes additional issues, may need to rollback recent deployments or route traffic to backup instances",
                )
            )
            priority += 1

        # === PREVENTION ACTIONS ===

        # Action 6: Implement connection pool monitoring
        if any(
            "monitoring" in ev.content.lower() or "alerts" in ev.content.lower()
            for ev in runbook_recs["prevention"]
        ):
            supporting_ids = [
                ev.evidence_id
                for ev in runbook_recs["prevention"]
                if "monitoring" in ev.content.lower()
                or "alerts" in ev.content.lower()
            ][:2]

            actions.append(
                RemediationAction(
                    action_id=_generate_action_id(
                        "Implement connection pool monitoring", priority
                    ),
                    title="Implement connection pool monitoring and alerts",
                    description="Set up alerts for high connection pool utilization (>80%). Track connection acquisition times and monitor per-service connection usage.",
                    rationale="Prevent future incidents by detecting connection pool issues before they cause service outages.",
                    priority=priority,
                    risk_level=RiskLevel.LOW,
                    category="prevention",
                    supporting_evidence_ids=supporting_ids,
                    requires_human_approval=True,
                    validation_step="Verify monitoring alerts are configured and triggering correctly in test scenarios",
                    rollback_consideration="Monitoring is non-intrusive; can be disabled if alerts are too noisy",
                )
            )
            priority += 1

        # Action 7: Establish query governance
        if any(
            "query timeout" in ev.content.lower() or "governance" in ev.content.lower()
            for ev in runbook_recs["prevention"]
        ):
            supporting_ids = [
                ev.evidence_id
                for ev in runbook_recs["prevention"]
                if "query timeout" in ev.content.lower()
                or "governance" in ev.content.lower()
            ][:2]

            actions.append(
                RemediationAction(
                    action_id=_generate_action_id("Establish query governance", priority),
                    title="Establish query governance and timeout limits",
                    description="Implement query timeout limits. Require performance testing for new reporting queries. Use read replicas for analytical workloads.",
                    rationale="Prevent long-running queries from exhausting connection pool in the future.",
                    priority=priority,
                    risk_level=RiskLevel.MEDIUM,
                    category="prevention",
                    supporting_evidence_ids=supporting_ids,
                    requires_human_approval=True,
                    validation_step="Verify query timeout policies are documented and enforced in application configuration",
                    rollback_consideration="Query timeouts can be adjusted or disabled if they interfere with legitimate long-running operations",
                )
            )
            priority += 1

        # Build summary
        investigation_count = sum(1 for a in actions if a.category == "investigation")
        containment_count = sum(1 for a in actions if a.category == "containment")
        recovery_count = sum(1 for a in actions if a.category == "recovery")
        prevention_count = sum(1 for a in actions if a.category == "prevention")
        high_risk_count = sum(
            1 for a in actions if a.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        )

        summary = (
            f"Generated {len(actions)} remediation action(s) based on verified hypothesis: "
            f"{top_hypothesis.title}. "
            f"Actions: {investigation_count} investigation, {containment_count} containment, "
            f"{recovery_count} recovery, {prevention_count} prevention. "
        )

        if high_risk_count > 0:
            summary += f"{high_risk_count} high-risk action(s) require careful review. "

        summary += "All actions require human review and approval before execution."

        limitations = [
            "Recommendations based only on verified hypotheses",
            "Does not execute any actions automatically",
            "Effectiveness depends on accurate hypothesis verification",
            "High-risk actions require change control approval",
            "Some recommendations may not apply to specific infrastructure",
        ]

        return RemediationPlan(
            incident_id=verification_result.incident_id,
            actions=actions,
            summary=summary,
            limitations=limitations,
            requires_human_approval=True,
        )
