"""Report generation for benchmark results."""

import json
from pathlib import Path
from typing import Dict

from src.opspilot.evaluation.models import BenchmarkReport


def generate_json_report(report: BenchmarkReport, output_path: Path) -> None:
    """Generate machine-readable JSON report.

    Args:
        report: Benchmark report
        output_path: Path to save JSON file

    Note:
        Output is deterministic with sorted keys.
    """
    # Convert to dict and sort keys
    report_dict = report.model_dump()

    # Ensure deterministic ordering
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, sort_keys=True)


def generate_markdown_report(report: BenchmarkReport, output_path: Path) -> None:
    """Generate human-readable Markdown report.

    Args:
        report: Benchmark report
        output_path: Path to save Markdown file

    Note:
        Output is deterministic with stable case ordering.
    """
    lines = []

    # Header
    lines.append("# OpsPilot Evaluation Benchmark Report")
    lines.append("")
    lines.append(f"**Mode:** {report.mode}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Aggregate metrics
    lines.append("## Aggregate Metrics")
    lines.append("")

    agg = report.aggregate

    lines.append(f"- **Total Cases:** {agg.total_cases}")
    lines.append(f"- **Successful Cases:** {agg.successful_cases}")
    lines.append(f"- **Severity Accuracy:** {agg.severity_accuracy:.2%}")
    lines.append("")

    lines.append("### Service Identification")
    lines.append(f"- **Average Precision:** {agg.avg_service_precision:.2%}")
    lines.append(f"- **Average Recall:** {agg.avg_service_recall:.2%}")
    lines.append(f"- **Average F1:** {agg.avg_service_f1:.2%}")
    lines.append("")

    lines.append("### Diagnosis Quality")
    lines.append(f"- **Average Precision:** {agg.avg_diagnosis_precision:.2%}")
    lines.append(f"- **Average Recall:** {agg.avg_diagnosis_recall:.2%}")
    lines.append("")

    lines.append("### Evidence & Claims")
    lines.append(f"- **Average Citation Validity:** {agg.avg_citation_validity:.2%}")
    lines.append(
        f"- **Average Rejected Claim Rate:** {agg.avg_rejected_claim_rate:.2%}"
    )
    lines.append("")

    lines.append("---")
    lines.append("")

    # Per-case results
    lines.append("## Per-Case Results")
    lines.append("")

    for result in report.results:
        lines.append(f"### {result.case_id}")
        lines.append("")

        lines.append(f"**Mode:** {result.mode}")
        exec_status = "Yes" if result.metrics.execution_success else "No"
        lines.append(f"**Execution Success:** {exec_status}")
        lines.append("")

        if result.errors:
            lines.append("**Errors:**")
            for error in result.errors:
                lines.append(f"- {error}")
            lines.append("")

        lines.append("**Severity:**")
        severity_status = "Yes" if result.metrics.severity_correct else "No"
        lines.append(
            f"- Actual: {result.actual_severity} | Correct: {severity_status}"
        )
        lines.append("")

        lines.append("**Services:**")
        lines.append(f"- Identified: {', '.join(result.actual_services) if result.actual_services else 'None'}")
        lines.append(
            f"- Precision: {result.metrics.service_metrics.precision:.2%} | Recall: {result.metrics.service_metrics.recall:.2%} | F1: {result.metrics.service_metrics.f1:.2%}"
        )
        lines.append("")

        lines.append("**Diagnosis:**")
        lines.append(
            f"- Concepts: {', '.join(result.actual_concepts[:10]) if result.actual_concepts else 'None'}{'...' if len(result.actual_concepts) > 10 else ''}"
        )
        lines.append(
            f"- Precision: {result.metrics.diagnosis_metrics.precision:.2%} | Recall: {result.metrics.diagnosis_metrics.recall:.2%}"
        )
        lines.append("")

        lines.append("**Evidence & Claims:**")
        lines.append(f"- Citations: {len(result.cited_evidence_ids)}")
        lines.append(f"- Citation Validity: {result.metrics.citation_validity:.2%}")
        lines.append(f"- Rejected Concepts: {len(result.rejected_concepts)}")
        lines.append(
            f"- Rejected Claim Rate: {result.metrics.rejected_claim_rate:.2%}"
        )
        lines.append("")

        lines.append("---")
        lines.append("")

    # Metric definitions
    lines.append("## Metric Definitions")
    lines.append("")

    lines.append("### Severity Accuracy")
    lines.append(
        "Ratio of cases where predicted severity matches expected severity."
    )
    lines.append("")

    lines.append("### Service Metrics")
    lines.append("- **Precision:** TP / (TP + FP) - Accuracy of predicted services")
    lines.append("- **Recall:** TP / (TP + FN) - Coverage of expected services")
    lines.append(
        "- **F1:** 2 × (Precision × Recall) / (Precision + Recall) - Harmonic mean"
    )
    lines.append("")

    lines.append("### Diagnosis Metrics")
    lines.append(
        "- **Precision:** Relevant concepts / Predicted concepts - Accuracy of diagnosis"
    )
    lines.append(
        "- **Recall:** Relevant concepts / Expected concepts - Coverage of expected concepts"
    )
    lines.append("")

    lines.append("### Citation Validity")
    lines.append(
        "Ratio of cited evidence IDs that exist in available evidence for the case."
    )
    lines.append("")

    lines.append("### Rejected Claim Rate")
    lines.append(
        "Ratio of expected-rejected concepts that were actually found in rejected hypotheses."
    )
    lines.append("")

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def print_console_summary(report: BenchmarkReport) -> None:
    """Print concise console summary.

    Args:
        report: Benchmark report

    Note:
        Output is deterministic and human-readable.
    """
    print()
    print("=" * 60)
    print(f"OpsPilot Evaluation Benchmark - {report.mode.upper()} MODE")
    print("=" * 60)
    print()

    agg = report.aggregate

    print(f"Total Cases: {agg.total_cases}")
    print(f"Successful: {agg.successful_cases}/{agg.total_cases}")
    print()

    print("Aggregate Metrics:")
    print(f"  Severity Accuracy:        {agg.severity_accuracy:.1%}")
    print(f"  Service Precision:        {agg.avg_service_precision:.1%}")
    print(f"  Service Recall:           {agg.avg_service_recall:.1%}")
    print(f"  Service F1:               {agg.avg_service_f1:.1%}")
    print(f"  Diagnosis Precision:      {agg.avg_diagnosis_precision:.1%}")
    print(f"  Diagnosis Recall:         {agg.avg_diagnosis_recall:.1%}")
    print(f"  Citation Validity:        {agg.avg_citation_validity:.1%}")
    print(f"  Rejected Claim Rate:      {agg.avg_rejected_claim_rate:.1%}")
    print()

    print("Per-Case Summary:")
    for result in report.results:
        status = "OK" if result.metrics.execution_success else "FAIL"
        severity_status = "OK" if result.metrics.severity_correct else "FAIL"
        print(
            f"  {result.case_id}: {status} | Severity: {severity_status} | "
            f"F1: {result.metrics.service_metrics.f1:.1%}"
        )

    if any(r.errors for r in report.results):
        print()
        print("Errors:")
        for result in report.results:
            if result.errors:
                print(f"  {result.case_id}:")
                for error in result.errors:
                    print(f"    - {error}")

    print()
    print("=" * 60)
    print()
