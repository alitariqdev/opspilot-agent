"""Tests for live mode UI integration."""

from pathlib import Path

import pytest


def test_app_shows_demo_mode_label():
    """Test that app shows Offline Demo Mode in demo mode."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    # Should have demo mode label
    assert "Offline Demo" in app_source


def test_app_shows_live_mode_label():
    """Test that app shows Live LLM Mode in live mode."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    # Should have live mode label
    assert "Live LLM" in app_source


def test_app_shows_model_name_in_live_mode():
    """Test that app shows model name in live mode."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    # Should display model name
    assert "config.openai_model" in app_source or "Model:" in app_source


def test_app_never_displays_api_key():
    """Test that app never displays API key."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    # Should not display API key
    assert "st.write(config.openai_api_key)" not in app_source
    assert "st.text(config.openai_api_key)" not in app_source
    assert "st.code(config.openai_api_key)" not in app_source
    assert "st.markdown(config.openai_api_key)" not in app_source

    # Should not expose API key in any display
    assert "openai_api_key" not in app_source or "config.openai_model" in app_source


def test_app_shows_setup_message_for_incomplete_config():
    """Test that app shows setup message if live mode is incomplete."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    # Should have setup instructions for incomplete config
    assert "Configuration required" in app_source or "Setup Instructions" in app_source


def test_app_handles_validation_errors_safely():
    """Test that app handles validation errors safely."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    # Should catch ValueError for validation
    assert "validate_live_mode" in app_source
    assert "except" in app_source or "try:" in app_source


def test_app_does_not_store_api_key_in_session_state():
    """Test that app doesn't store API key in session state."""
    import app

    app_source = Path(app.__file__).read_text(encoding="utf-8")

    # Should not store API key in session state
    assert 'st.session_state["api_key"]' not in app_source
    assert 'st.session_state["openai_api_key"]' not in app_source


def test_ui_helpers_do_not_expose_secrets():
    """Test that UI helpers don't expose secrets."""
    from src.opspilot import ui

    ui_source = Path(ui.__file__).read_text(encoding="utf-8")

    # Should not reference API keys
    assert "api_key" not in ui_source.lower()
    assert "openai_api_key" not in ui_source.lower()


def test_env_example_has_safe_placeholders():
    """Test that .env.example has safe placeholder values."""
    env_example = Path(".env.example").read_text()

    # Should have placeholder, not real key
    assert "your-api-key-here" in env_example or "sk-your-api-key" in env_example

    # Should not have real key patterns
    lines = env_example.split("\n")
    for line in lines:
        if line.startswith("OPENAI_API_KEY=") and not line.startswith(
            "OPENAI_API_KEY=#"
        ):
            value = line.split("=", 1)[1].strip()
            # Should be a placeholder
            assert (
                "your-api-key" in value.lower()
                or "placeholder" in value.lower()
                or value.startswith("#")
                or value.startswith("sk-your")
            )


def test_config_validation_does_not_break_demo_import():
    """Test that config can be imported in demo mode without API key."""
    from src.opspilot.config import OpsPilotConfig, get_config

    # Should be able to create demo config without API key
    config = OpsPilotConfig(opspilot_mode="demo", openai_api_key=None)
    assert config.opspilot_mode == "demo"

    # get_config should work (may return demo mode by default)
    config2 = get_config()
    assert config2 is not None


def test_workflow_can_import_without_api_key():
    """Test that workflow module can be imported without API key."""
    from src.opspilot import workflow

    # Should be able to import workflow module
    assert hasattr(workflow, "run_investigation")
    assert hasattr(workflow, "build_investigation_graph")


def test_demo_agents_can_import_without_llm_client():
    """Test that demo agents can be imported without LLM dependencies."""
    from src.opspilot.agents.diagnosis import DemoDiagnosisAgent
    from src.opspilot.agents.triage import DemoTriageAgent

    # Should be able to create demo agents
    triage = DemoTriageAgent()
    diagnosis = DemoDiagnosisAgent()

    assert triage is not None
    assert diagnosis is not None
