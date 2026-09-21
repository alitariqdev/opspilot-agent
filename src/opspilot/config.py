"""Configuration management for OpsPilot using Pydantic."""

from typing import Optional

from pydantic import ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings


class OpsPilotConfig(BaseSettings):
    """Configuration model for OpsPilot application.

    Loads settings from environment variables with safe defaults.
    Supports both demo and live modes.
    """

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    opspilot_mode: str = Field(
        default="demo",
        description="Operating mode: 'demo' or 'live'"
    )

    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (optional in demo mode, required in live mode)"
    )

    openai_base_url: Optional[str] = Field(
        default=None,
        description="OpenAI-compatible API base URL (optional, for OpenRouter compatibility)"
    )

    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model identifier for live mode"
    )

    llm_timeout_seconds: int = Field(
        default=60,
        description="LLM API call timeout in seconds",
        ge=10,
        le=300
    )

    llm_max_retries: int = Field(
        default=2,
        description="Maximum number of LLM API retries",
        ge=0,
        le=3
    )

    @field_validator("opspilot_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate that mode is either demo or live.

        Args:
            v: Mode value

        Returns:
            Validated mode

        Raises:
            ValueError: If mode is invalid
        """
        if v.lower() not in ["demo", "live"]:
            raise ValueError(f"Invalid mode: {v}. Must be 'demo' or 'live'")
        return v.lower()

    def validate_live_mode(self) -> None:
        """Validate configuration for live mode.

        Raises:
            ValueError: If live mode configuration is invalid
        """
        if self.opspilot_mode == "live":
            if not self.openai_api_key:
                raise ValueError(
                    "Live mode requires OPENAI_API_KEY to be set. "
                    "Please configure your API key in the .env file or environment variables."
                )
            if not self.openai_model:
                raise ValueError(
                    "Live mode requires OPENAI_MODEL to be set"
                )


def get_config() -> OpsPilotConfig:
    """Load and return the application configuration.

    Returns:
        OpsPilotConfig: Validated configuration object
    """
    return OpsPilotConfig()
