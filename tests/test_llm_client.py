"""Tests for LLM client abstraction."""

import pytest
from pydantic import BaseModel, Field

from src.opspilot.config import OpsPilotConfig
from src.opspilot.llm_client import LLMClientError, OpenAICompatibleClient


class SampleResponseModel(BaseModel):
    """Sample response model for structured output testing."""

    title: str = Field(description="Test title")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")


class FakeLLMClient:
    """Fake LLM client for testing without network calls."""

    def __init__(self, response_data: dict):
        """Initialize fake client with canned response.

        Args:
            response_data: Data to return as structured output
        """
        self.response_data = response_data
        self.calls = []

    def generate_structured(self, system_prompt: str, user_prompt: str, response_model):
        """Record call and return canned response.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            response_model: Expected response model

        Returns:
            Validated response model instance
        """
        self.calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "response_model": response_model,
        })

        return response_model(**self.response_data)


def test_fake_client_returns_structured_output():
    """Test that fake client returns structured output."""
    fake_client = FakeLLMClient({"title": "Test", "confidence": 0.8})

    result = fake_client.generate_structured(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SampleResponseModel,
    )

    assert result.title == "Test"
    assert result.confidence == 0.8
    assert len(fake_client.calls) == 1


def test_fake_client_records_calls():
    """Test that fake client records calls."""
    fake_client = FakeLLMClient({"title": "Test", "confidence": 0.5})

    fake_client.generate_structured(
        system_prompt="Sys prompt",
        user_prompt="User prompt",
        response_model=SampleResponseModel,
    )

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["system_prompt"] == "Sys prompt"
    assert fake_client.calls[0]["user_prompt"] == "User prompt"


def test_llm_client_error_does_not_expose_secrets():
    """Test that LLM client error messages don't expose secrets."""
    error = LLMClientError("Test error message")

    error_str = str(error)

    # Should not contain common secret patterns
    assert "sk-" not in error_str
    assert "api_key" not in error_str.lower()
    assert "token" not in error_str.lower()


def test_config_validation_requires_api_key_for_live_mode():
    """Test that live mode requires API key."""
    config = OpsPilotConfig(opspilot_mode="live", openai_api_key=None)

    with pytest.raises(ValueError, match="Live mode requires OPENAI_API_KEY"):
        config.validate_live_mode()


def test_config_validation_passes_with_api_key():
    """Test that live mode validation passes with API key."""
    config = OpsPilotConfig(
        opspilot_mode="live",
        openai_api_key="sk-test-key",
        openai_model="gpt-4o-mini",
    )

    # Should not raise
    config.validate_live_mode()


def test_demo_mode_does_not_require_api_key():
    """Test that demo mode doesn't require API key."""
    config = OpsPilotConfig(opspilot_mode="demo", openai_api_key=None)

    # Should not raise (validation not needed for demo mode)
    assert config.opspilot_mode == "demo"


def test_invalid_mode_rejected():
    """Test that invalid mode values are rejected."""
    with pytest.raises(ValueError, match="Invalid mode"):
        OpsPilotConfig(opspilot_mode="invalid")


def test_timeout_bounds_validated():
    """Test that timeout is bounded."""
    # Too low
    with pytest.raises(ValueError):
        OpsPilotConfig(llm_timeout_seconds=5)

    # Too high
    with pytest.raises(ValueError):
        OpsPilotConfig(llm_timeout_seconds=500)

    # Valid
    config = OpsPilotConfig(llm_timeout_seconds=60)
    assert config.llm_timeout_seconds == 60


def test_max_retries_bounded():
    """Test that max retries is bounded."""
    # Too high
    with pytest.raises(ValueError):
        OpsPilotConfig(llm_max_retries=10)

    # Valid
    config = OpsPilotConfig(llm_max_retries=2)
    assert config.llm_max_retries == 2
