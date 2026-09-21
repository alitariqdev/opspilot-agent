"""Configuration management for OpsPilot using Pydantic."""

import os
from typing import Optional

from pydantic import ConfigDict, Field
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
        description="OpenAI API key (optional in demo mode)"
    )

    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model identifier"
    )


def get_config() -> OpsPilotConfig:
    """Load and return the application configuration.

    Returns:
        OpsPilotConfig: Validated configuration object
    """
    return OpsPilotConfig()
