"""Tests for evaluation benchmark execution."""

import json
from pathlib import Path

import pytest

from src.opspilot.evaluation.executor import load_benchmark_cases, run_benchmark
from src.opspilot.evaluation.models import BenchmarkCase, ExpectedValues
from src.opspilot.evaluation.reporter import generate_json_report, generate_markdown_report


class TestBenchmarkCaseLoading:
    """Tests for loading benchmark cases."""

    def test_load_benchmark_cases(self):
        """Test loading real benchmark cases."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        cases = load_benchmark_cases(cases_file)

        assert len(cases) >= 4
        assert all(isinstance(c, BenchmarkCase) for c in cases)

        # Check required fields
        for case in cases:
            assert case.case_id
            assert case.name
            assert case.incident_id
            assert case.log_file
            assert isinstance(case.expected, ExpectedValues)

    def test_cases_sorted_by_id(self):
        """Test that cases are sorted by case_id."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        cases = load_benchmark_cases(cases_file)

        case_ids = [c.case_id for c in cases]
        assert case_ids == sorted(case_ids)

    def test_expected_values_structure(self):
        """Test that expected values have correct structure."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        cases = load_benchmark_cases(cases_file)

        for case in cases:
            # Should have severity
            assert case.expected.severity in ["SEV1", "SEV2", "SEV3", "SEV4"]

            # Should have sets for services, concepts, rejected claims
            assert isinstance(case.expected.affected_services, set)
            assert isinstance(case.expected.diagnosis_concepts, set)
            assert isinstance(case.expected.rejected_claims, set)


class TestBenchmarkExecution:
    """Tests for benchmark execution."""

    def test_run_benchmark_demo_mode(self):
        """Test running benchmark in demo mode (offline, no API key)."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        # Run in demo mode (deterministic, no API key required)
        report = run_benchmark(cases_file, data_dir, mode="demo")

        # Check report structure
        assert report.mode == "demo"
        assert report.aggregate.total_cases >= 4

        # Check that at least some cases succeeded
        assert report.aggregate.successful_cases > 0

        # Check results exist
        assert len(report.results) == report.aggregate.total_cases

        # Check all results have required fields
        for result in report.results:
            assert result.case_id
            assert result.mode == "demo"
            assert result.metrics
            assert result.actual_severity

    def test_benchmark_deterministic(self):
        """Test that benchmark produces deterministic results."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        # Run twice
        report1 = run_benchmark(cases_file, data_dir, mode="demo")
        report2 = run_benchmark(cases_file, data_dir, mode="demo")

        # Aggregate metrics should be identical
        assert report1.aggregate.total_cases == report2.aggregate.total_cases
        assert (
            report1.aggregate.successful_cases == report2.aggregate.successful_cases
        )
        assert (
            report1.aggregate.severity_accuracy == report2.aggregate.severity_accuracy
        )

        # Per-case results should be identical
        for r1, r2 in zip(report1.results, report2.results):
            assert r1.case_id == r2.case_id
            assert r1.actual_severity == r2.actual_severity
            assert r1.metrics.severity_correct == r2.metrics.severity_correct

    def test_benchmark_no_api_key_required(self):
        """Test that benchmark runs without API key in demo mode."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        # Explicitly use demo mode with no config
        report = run_benchmark(cases_file, data_dir, mode="demo", config=None)

        assert report.mode == "demo"
        assert report.aggregate.total_cases > 0


class TestReportGeneration:
    """Tests for report generation."""

    def test_json_report_generation(self, tmp_path):
        """Test JSON report generation."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        report = run_benchmark(cases_file, data_dir, mode="demo")

        # Generate JSON report
        json_path = tmp_path / "test_report.json"
        generate_json_report(report, json_path)

        assert json_path.exists()

        # Load and validate JSON
        with open(json_path, "r") as f:
            data = json.load(f)

        assert data["mode"] == "demo"
        assert "aggregate" in data
        assert "results" in data
        assert len(data["results"]) > 0

    def test_markdown_report_generation(self, tmp_path):
        """Test Markdown report generation."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        report = run_benchmark(cases_file, data_dir, mode="demo")

        # Generate Markdown report
        md_path = tmp_path / "test_report.md"
        generate_markdown_report(report, md_path)

        assert md_path.exists()

        # Check content
        content = md_path.read_text(encoding="utf-8")

        assert "# OpsPilot Evaluation Benchmark Report" in content
        assert "## Aggregate Metrics" in content
        assert "## Per-Case Results" in content
        assert "## Metric Definitions" in content

    def test_json_report_deterministic(self, tmp_path):
        """Test that JSON report is deterministic."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        report = run_benchmark(cases_file, data_dir, mode="demo")

        # Generate twice
        json_path1 = tmp_path / "report1.json"
        json_path2 = tmp_path / "report2.json"

        generate_json_report(report, json_path1)
        generate_json_report(report, json_path2)

        # Content should be identical
        content1 = json_path1.read_text()
        content2 = json_path2.read_text()

        assert content1 == content2


class TestCitationValidity:
    """Tests for citation validity checking."""

    def test_citations_validated_in_benchmark(self):
        """Test that citations are validated against available evidence."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        report = run_benchmark(cases_file, data_dir, mode="demo")

        # Check that citation validity is computed
        for result in report.results:
            # Citation validity should be between 0 and 1
            assert 0.0 <= result.metrics.citation_validity <= 1.0

            # If citations exist, validity should be computed
            if result.cited_evidence_ids:
                # Validity is ratio of valid citations
                assert isinstance(result.metrics.citation_validity, float)


class TestRejectedClaims:
    """Tests for rejected claim handling."""

    def test_rejected_claims_tracked(self):
        """Test that rejected claims are tracked."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        report = run_benchmark(cases_file, data_dir, mode="demo")

        # Check that rejected claim rate is computed
        for result in report.results:
            # Rate should be between 0 and 1
            assert 0.0 <= result.metrics.rejected_claim_rate <= 1.0

            # Rejected concepts should be a list
            assert isinstance(result.rejected_concepts, list)


class TestErrorHandling:
    """Tests for error handling in benchmark."""

    def test_malformed_case_handled_safely(self, tmp_path):
        """Test that malformed benchmark case is handled safely."""
        # Create malformed cases file
        malformed_cases = [
            {
                "case_id": "bad_case",
                "name": "Bad Case",
                "description": "Test",
                # Missing required fields
            }
        ]

        cases_file = tmp_path / "bad_cases.json"
        with open(cases_file, "w") as f:
            json.dump(malformed_cases, f)

        # Should raise validation error, not crash
        with pytest.raises(Exception):
            load_benchmark_cases(cases_file)

    def test_missing_incident_file_handled(self):
        """Test that missing incident file is handled safely."""
        from src.opspilot.evaluation.executor import load_incident

        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"

        # Try to load non-existent incident
        with pytest.raises(FileNotFoundError):
            load_incident("INC-NONEXISTENT", data_dir)


class TestMetricDefinitions:
    """Tests for metric definition compliance."""

    def test_severity_accuracy_definition(self):
        """Test that severity accuracy matches definition."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        report = run_benchmark(cases_file, data_dir, mode="demo")

        # Manual calculation
        correct_count = sum(
            1 for r in report.results if r.metrics.severity_correct
        )
        expected_accuracy = correct_count / report.aggregate.total_cases

        # Should match reported accuracy
        assert report.aggregate.severity_accuracy == expected_accuracy

    def test_aggregate_metrics_are_averages(self):
        """Test that aggregate metrics are computed as averages."""
        project_root = Path(__file__).parent.parent
        cases_file = project_root / "data" / "evaluation" / "benchmark_cases.json"
        data_dir = project_root / "data"

        if not cases_file.exists():
            pytest.skip("Benchmark cases file not found")

        report = run_benchmark(cases_file, data_dir, mode="demo")

        # Manual calculation of average service precision
        avg_precision = sum(
            r.metrics.service_metrics.precision for r in report.results
        ) / len(report.results)

        # Should match reported average
        assert report.aggregate.avg_service_precision == pytest.approx(avg_precision)
