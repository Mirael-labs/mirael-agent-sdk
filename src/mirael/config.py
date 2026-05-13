"""
Central configuration via Pydantic Settings.

All config is loaded from environment variables (prefixed MIRAEL_) or a .env
file at process startup. Missing required values raise ``ConfigurationError``
immediately — fail fast rather than at first use.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mirael.exceptions import ConfigurationError


class MiraelSettings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All variables are prefixed with ``MIRAEL_``.
    Example: ``MIRAEL_ANTHROPIC_API_KEY=sk-ant-...``
    """

    model_config = SettingsConfigDict(
        env_prefix="MIRAEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    anthropic_api_key: SecretStr = Field(description="Anthropic API key for claude-sonnet-4-5")
    llm_model: str = Field(default="claude-sonnet-4-5", description="Anthropic model identifier")
    llm_max_tokens: int = Field(default=4096, ge=1, le=8192)

    # ── Embeddings ────────────────────────────────────────────────────────────
    openai_api_key: SecretStr = Field(description="OpenAI API key for text-embedding-3-large")
    embedding_model: str = Field(default="text-embedding-3-large")
    embedding_dimensions: int = Field(default=3072, ge=256, le=3072)

    # ── Vector Store ──────────────────────────────────────────────────────────
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: SecretStr | None = Field(default=None)
    qdrant_collection: str = Field(default="mirael_docs")

    # ── Hyperliquid ───────────────────────────────────────────────────────────
    hl_network: Literal["mainnet", "testnet"] = Field(default="mainnet")
    hl_wallet_address: str | None = Field(default=None)

    # ── App ───────────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    environment: Literal["development", "staging", "production"] = Field(default="development")

    @model_validator(mode="after")
    def validate_secrets(self) -> MiraelSettings:
        """Raise ConfigurationError immediately if required secrets are blank."""
        errors: list[str] = []
        if not self.anthropic_api_key.get_secret_value().strip():
            errors.append("MIRAEL_ANTHROPIC_API_KEY is required")
        if not self.openai_api_key.get_secret_value().strip():
            errors.append("MIRAEL_OPENAI_API_KEY is required")
        if errors:
            raise ConfigurationError(
                "Missing required configuration: " + "; ".join(errors),
                code="CONFIG_MISSING_SECRETS",
            )
        return self


def load_settings() -> MiraelSettings:
    """
    Load and validate settings from environment.

    Raises:
        ConfigurationError: if required secrets are missing or values are invalid.
    """
    try:
        return MiraelSettings()
    except Exception as exc:
        # Re-raise pydantic ValidationError as ConfigurationError for consistent handling
        if not isinstance(exc, ConfigurationError):
            raise ConfigurationError(str(exc), code="CONFIG_VALIDATION_ERROR") from exc
        raise
