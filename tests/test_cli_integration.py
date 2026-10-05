"""CLI integration tests that run OpsPilot commands as subprocesses."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestBenchmarkCLI:
    """Tests for benchmark CLI command executed as subprocess."""

    def test_benchmark_cli_runs_successfully(self):
        """Test that benchmark CLI command executes successfully."""
        project_root = Path(__file__).parent.parent

        # Run benchmark command as subprocess (no pytest sys.path modifications)
        result = subprocess.run(
            [sys.executable, "-m", "opspilot.evaluation.runner"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Check exit code
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Check console output
        assert "OpsPilot Evaluation Benchmark" in result.stdout
        assert "DEMO MODE" in result.stdout
        assert "Total Cases:" in result.stdout
        assert "Aggregate Metrics:" in result.stdout
        assert "Benchmark completed successfully!" in result.stdout

    def test_benchmark_generates_json_report(self):
        """Test that benchmark generates valid JSON report."""
        project_root = Path(__file__).parent.parent

        # Run benchmark
        result = subprocess.run(
            [sys.executable, "-m", "opspilot.evaluation.runner"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0

        # Check JSON report exists
        json_path = project_root / "evaluation_results" / "benchmark_demo.json"
        assert json_path.exists(), "JSON report not generated"

        # Validate JSON structure
        with open(json_path, "r") as f:
            data = json.load(f)

        assert "mode" in data
        assert data["mode"] == "demo"
        assert "aggregate" in data
        assert "results" in data
        assert len(data["results"]) >= 4

    def test_benchmark_generates_markdown_report(self):
        """Test that benchmark generates Markdown report."""
        project_root = Path(__file__).parent.parent

        # Run benchmark
        result = subprocess.run(
            [sys.executable, "-m", "opspilot.evaluation.runner"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0

        # Check Markdown report exists
        md_path = project_root / "evaluation_results" / "benchmark_demo.md"
        assert md_path.exists(), "Markdown report not generated"

        # Check content
        content = md_path.read_text(encoding="utf-8")
        assert "# OpsPilot Evaluation Benchmark Report" in content
        assert "## Aggregate Metrics" in content
        assert "## Per-Case Results" in content

    def test_benchmark_offline_mode_works_without_api_key(self):
        """Test that benchmark works in offline mode without API key."""
        import os

        project_root = Path(__file__).parent.parent

        # Run with environment that explicitly has no API key
        env = os.environ.copy()
        env["OPSPILOT_MODE"] = "demo"
        env.pop("OPENAI_API_KEY", None)  # Remove API key if present

        result = subprocess.run(
            [sys.executable, "-m", "opspilot.evaluation.runner"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

        # Should succeed even without API key
        assert result.returncode == 0
        assert "DEMO MODE" in result.stdout

    def test_benchmark_console_output_format(self):
        """Test that benchmark console output is properly formatted."""
        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "opspilot.evaluation.runner"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0

        output = result.stdout

        # Check for expected sections
        assert "Total Cases:" in output
        assert "Successful:" in output
        assert "Aggregate Metrics:" in output
        assert "Severity Accuracy:" in output
        assert "Service Precision:" in output
        assert "Service Recall:" in output
        assert "Service F1:" in output
        assert "Diagnosis Precision:" in output
        assert "Diagnosis Recall:" in output
        assert "Citation Validity:" in output
        assert "Rejected Claim Rate:" in output
        assert "Per-Case Summary:" in output

        # Check for case results
        assert "case_001_connection_pool:" in output
        assert "case_002_http_503:" in output
        assert "case_003_container_crashloop:" in output
        assert "case_004_insufficient_evidence:" in output

        # Check for output file paths
        assert "Demo results saved:" in output
        assert "JSON:" in output
        assert "Markdown:" in output

    def test_benchmark_exit_code_zero_on_success(self):
        """Test that benchmark exits with code 0 on success."""
        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "opspilot.evaluation.runner"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Exit code should be 0 for successful execution
        assert result.returncode == 0

        # Should not have stderr errors
        assert "Error" not in result.stderr
        assert "Traceback" not in result.stderr
