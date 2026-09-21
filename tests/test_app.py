"""Tests for Streamlit application."""

import json
from pathlib import Path

import pytest


def test_app_imports_successfully():
    """Test that app.py can be imported without errors."""
    try:
        import app

        assert app is not None
    except ImportError as e:
        pytest.fail(f"Failed to import app.py: {e}")


def test_app_has_main_function():
    """Test that app.py has a main function."""
    import app

    assert hasattr(app, "main")
    assert callable(app.main)


def test_app_has_load_sample_incident():
    """Test that app has incident loading function."""
    import app

    assert hasattr(app, "load_sample_incident")
    assert callable(app.load_sample_incident)


def test_load_sample_incident_returns_valid_incident():
    """Test that sample incident can be loaded."""
    import app

    incident = app.load_sample_incident()

    assert incident is not None
    assert incident.incident_id
    assert incident.title
    assert incident.description
    assert isinstance(incident.symptoms, list)
    assert isinstance(incident.affected_services, list)


def test_app_root_is_valid_path():
    """Test that app root path resolution works."""
    import app

    app_root = app.get_app_root()

    assert app_root.exists()
    assert app_root.is_dir()
    assert (app_root / "app.py").exists()


def test_ui_module_imports_successfully():
    """Test that UI module imports successfully."""
    try:
        from src.opspilot import ui

        assert ui is not None
    except ImportError as e:
        pytest.fail(f"Failed to import ui module: {e}")


def test_ui_module_has_required_functions():
    """Test that UI module has required helper functions."""
    from src.opspilot import ui

    required_functions = [
        "format_severity_badge",
        "format_hypothesis_status",
        "render_timeline_table",
        "render_evidence_table",
        "render_hypothesis_card",
        "render_remediation_action",
        "render_workflow_sidebar",
    ]

    for func_name in required_functions:
        assert hasattr(ui, func_name), f"Missing function: {func_name}"
        assert callable(getattr(ui, func_name))


def test_incident_data_file_exists():
    """Test that incident data file exists."""
    project_root = Path(__file__).parent.parent
    incident_file = project_root / "data" / "incidents" / "incident_001.json"

    assert incident_file.exists(), f"Incident file not found: {incident_file}"


def test_incident_data_is_valid_json():
    """Test that incident data is valid JSON."""
    project_root = Path(__file__).parent.parent
    incident_file = project_root / "data" / "incidents" / "incident_001.json"

    with open(incident_file, "r") as f:
        data = json.load(f)

    assert "incident_id" in data
    assert "title" in data
    assert "description" in data
    assert "symptoms" in data
    assert "affected_services" in data


def test_log_file_exists():
    """Test that log file exists."""
    project_root = Path(__file__).parent.parent
    log_file = project_root / "data" / "incidents" / "incident_001_logs.txt"

    assert log_file.exists(), f"Log file not found: {log_file}"


def test_runbook_directory_exists():
    """Test that runbook directory exists."""
    project_root = Path(__file__).parent.parent
    runbook_dir = project_root / "data" / "runbooks"

    assert runbook_dir.exists(), f"Runbook directory not found: {runbook_dir}"
    assert runbook_dir.is_dir()


def test_runbook_files_exist():
    """Test that runbook files exist."""
    project_root = Path(__file__).parent.parent
    runbook_dir = project_root / "data" / "runbooks"

    runbooks = list(runbook_dir.glob("*.md"))
    assert len(runbooks) > 0, "No runbook files found"
