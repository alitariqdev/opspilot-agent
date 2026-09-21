"""Tests for configuration management."""

import os
from unittest.mock import patch

import pytest

from src.opspilot.config import OpsPilotConfig, get_config


def test_default_mode_is_demo():
    """Verify that the default operating mode is 'demo'."""
    config = OpsPilotConfig()
    assert config.opspilot_mode == "demo"


def test_api_key_optional_in_demo_mode():
    """Verify that API key is optional when in demo mode."""
    config = OpsPilotConfig(opspilot_mode="demo")
    assert config.openai_api_key is None
    assert config.opspilot_mode == "demo"


def test_custom_mode_from_env():
    """Verify that mode can be set via environment variable."""
    with patch.dict(os.environ, {"OPSPILOT_MODE": "live"}):
        config = OpsPilotConfig()
        assert config.opspilot_mode == "live"


def test_api_key_from_env():
    """Verify that API key can be loaded from environment."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
        config = OpsPilotConfig()
        assert config.openai_api_key == "sk-test-key"


def test_custom_model_from_env():
    """Verify that model can be configured via environment."""
    with patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4"}):
        config = OpsPilotConfig()
        assert config.openai_model == "gpt-4"


def test_default_model():
    """Verify the default OpenAI model."""
    config = OpsPilotConfig()
    assert config.openai_model == "gpt-4o-mini"


def test_get_config_returns_valid_config():
    """Verify that get_config() returns a valid configuration object."""
    config = get_config()
    assert isinstance(config, OpsPilotConfig)
    assert config.opspilot_mode in ["demo", "live"]
