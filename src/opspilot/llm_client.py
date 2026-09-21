"""LLM client abstraction for OpsPilot.

Provides a safe, testable interface for structured JSON generation
with OpenAI-compatible APIs.
"""

import json
from typing import Any, Dict, Optional, Protocol, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from src.opspilot.config import OpsPilotConfig


T = TypeVar("T", bound=BaseModel)


class LLMClientError(Exception):
    """Safe exception for LLM client errors.

    Never exposes API keys, full provider responses, or sensitive data.
    """

    pass


class LLMClient(Protocol):
    """Protocol for structured JSON generation from LLM."""

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        """Generate structured output from LLM.

        Args:
            system_prompt: System instructions for the model
            user_prompt: User content for analysis
            response_model: Pydantic model for structured output

        Returns:
            Validated Pydantic model instance

        Raises:
            LLMClientError: If generation or validation fails
        """
        ...


class OpenAICompatibleClient:
    """OpenAI-compatible LLM client with structured output.

    Supports OpenAI and OpenRouter APIs.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        timeout_seconds: int = 60,
        max_retries: int = 2,
    ):
        """Initialize OpenAI-compatible client.

        Args:
            api_key: API key for authentication
            model: Model identifier (e.g., "gpt-4o-mini")
            base_url: Optional custom base URL (for OpenRouter)
            timeout_seconds: Timeout for API calls
            max_retries: Maximum number of retries

        Note:
            No network request is made during initialization.
        """
        self.model = model

        # Create OpenAI client with optional base_url
        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout_seconds,
            "max_retries": max_retries,
        }

        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = OpenAI(**client_kwargs)

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        """Generate structured output from LLM.

        Args:
            system_prompt: System instructions for the model
            user_prompt: User content for analysis
            response_model: Pydantic model for structured output

        Returns:
            Validated Pydantic model instance

        Raises:
            LLMClientError: If generation or validation fails (safe, no secrets exposed)
        """
        try:
            # Request structured JSON output
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,  # Deterministic for consistency
            )

            # Extract JSON from response
            if not response.choices:
                raise LLMClientError("No response choices returned from API")

            content = response.choices[0].message.content
            if not content:
                raise LLMClientError("Empty response content from API")

            # Parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise LLMClientError(f"Invalid JSON in response: {str(e)}")

            # Validate with Pydantic
            try:
                return response_model(**data)
            except ValidationError as e:
                # Extract safe error information
                error_count = len(e.errors())
                raise LLMClientError(
                    f"Response validation failed: {error_count} validation error(s)"
                )

        except LLMClientError:
            # Re-raise our safe exceptions
            raise

        except Exception as e:
            # Convert any other exception to safe form
            # Never expose API keys or full provider responses
            error_type = type(e).__name__
            raise LLMClientError(
                f"LLM API call failed: {error_type}. Check configuration and network connectivity."
            )


def create_llm_client(config: OpsPilotConfig) -> OpenAICompatibleClient:
    """Create LLM client from configuration.

    Args:
        config: OpsPilot configuration

    Returns:
        Configured LLM client

    Raises:
        ValueError: If configuration is invalid for live mode
    """
    config.validate_live_mode()

    if not config.openai_api_key:
        raise ValueError("API key required for LLM client")

    return OpenAICompatibleClient(
        api_key=config.openai_api_key,
        model=config.openai_model,
        base_url=config.openai_base_url,
        timeout_seconds=config.llm_timeout_seconds,
        max_retries=config.llm_max_retries,
    )
