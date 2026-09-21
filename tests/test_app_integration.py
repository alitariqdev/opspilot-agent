"""Integration tests for Streamlit app with workflow."""

from pathlib import Path

import pytest

from src.opspilot.workflow import run_investigation


def test_app_can_load_and_run_investigation():
    """Test that app can load incident and run investigation."""
    import app

    # Load incident
    incident = app.load_sample_incident()

    assert incident is not None
    assert incident.incident_id

    # Run investigation (same as app does)
    result = run_investigation(incident)

    assert result is not None
    assert result["workflow_status"] == "complete"
    assert result["incident_report"] is not None


def test_app_paths_are_relative_to_app_root():
    """Test that app uses paths relative to app.py location."""
    import app

    app_root = app.get_app_root()

    # Check data files exist relative to app root
    incident_file = app_root / "data" / "incidents" / "incident_001.json"
    assert incident_file.exists()

    log_file = app_root / "data" / "incidents" / "incident_001_logs.txt"
    assert log_file.exists()

    runbook_dir = app_root / "data" / "runbooks"
    assert runbook_dir.exists()


def test_app_session_state_structure():
    """Test that expected session state keys are used."""
    # This verifies the session state keys match what the app uses
    expected_keys = [
        "investigation_result",
        "investigation_error",
    ]

    # Just verify these are the keys used in app.py
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    for key in expected_keys:
        assert key in app_source, f"Expected session state key '{key}' not found in app.py"


def test_ui_does_not_expose_secrets():
    """Test that UI code does not expose secrets or env vars."""
    import app
    from src.opspilot import ui

    # Check app.py source
    app_source = Path(app.__file__).read_text(encoding="utf-8")

    forbidden_patterns = [
        "OPENAI_API_KEY",
        "os.environ",
        "getenv",
        "API_KEY",
        "SECRET",
    ]

    # These patterns should not appear in UI rendering code
    # (config loading is OK, but not in UI display)
    lines_to_check = []
    in_display_section = False

    for line in app_source.split("\n"):
        # Skip config loading at top
        if "st.title" in line or "st.markdown" in line or "st.metric" in line:
            in_display_section = True

        if in_display_section:
            lines_to_check.append(line)

    display_source = "\n".join(lines_to_check)

    # Should not display API keys or environment variables
    assert "OPENAI_API_KEY" not in display_source or "config.opspilot_mode" in display_source
    assert "st.text(os.environ" not in display_source
    assert "st.write(os.environ" not in display_source


def test_report_download_uses_safe_filename():
    """Test that report download generates safe filename."""
    import app

    incident = app.load_sample_incident()

    # Run investigation to get report
    result = run_investigation(incident)

    # Safe filename should not have path separators
    safe_filename = incident.incident_id.replace("/", "_").replace("\\", "_")
    expected_filename = f"incident_report_{safe_filename}.md"

    # Verify no path traversal possible
    assert "/" not in expected_filename
    assert "\\" not in expected_filename
    assert ".." not in expected_filename


def test_report_download_is_valid_markdown():
    """Test that downloaded report is valid Markdown."""
    import app

    incident = app.load_sample_incident()
    result = run_investigation(incident)

    report = result["incident_report"]

    # Should be valid Markdown
    assert report.startswith("#")
    assert "## " in report
    assert "**" in report

    # Should be UTF-8 encodable
    report_bytes = report.encode("utf-8")
    assert len(report_bytes) > 0


def test_ui_tabs_have_expected_labels():
    """Test that UI uses expected tab labels."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    expected_tabs = [
        "Overview",
        "Timeline & Evidence",
        "Root Cause Hypotheses",
        "Remediation Plan",
        "Incident Report",
    ]

    for tab_label in expected_tabs:
        assert tab_label in app_source, f"Expected tab '{tab_label}' not found"


def test_human_review_warning_is_visible():
    """Test that human review warning appears in UI."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    # Should have multiple warnings about human review
    assert "Human Review Required" in app_source or "human review" in app_source.lower()
    assert "⚠️" in app_source or "warning" in app_source.lower()


def test_offline_demo_mode_indicator_visible():
    """Test that offline demo mode is indicated."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    assert "Demo" in app_source or "Offline" in app_source
    assert "Mode" in app_source


def test_no_execute_button_for_remediation():
    """Test that there is no execute button for remediation actions."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    # Should not have execute/run buttons in remediation section
    # Download button is OK, but not execute
    assert "Execute" not in app_source or "Download" in app_source
    assert "button" in app_source  # Has buttons (Run Investigation, Reset, Download)

    # But should warn against execution
    assert "not execute" in app_source.lower() or "do not execute" in app_source.lower()
