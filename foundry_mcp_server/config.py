"""Fail-closed settings for the local development console."""
import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    development: bool = False
    mcp_token: str = ""
    browser_token: str = ""
    timeout: float = 15.0
    max_code_bytes: int = 32768
    max_response_bytes: int = 65536

    @classmethod
    def from_env(cls):
        enabled = os.getenv("FOUNDRY_MCP_DEV_EXECUTION", "false")
        if enabled not in {"true", "false"}:
            raise ValueError("FOUNDRY_MCP_DEV_EXECUTION must be true or false")
        settings = cls(
            development=enabled == "true",
            mcp_token=os.getenv("FOUNDRY_MCP_CALLER_TOKEN", ""),
            browser_token=os.getenv("FOUNDRY_MCP_BROWSER_TOKEN", ""),
            timeout=float(os.getenv("FOUNDRY_MCP_EXECUTION_TIMEOUT", "15")),
        )
        if not math.isfinite(settings.timeout) or not 0 < settings.timeout <= 120:
            raise ValueError("Execution timeout must be between 0 and 120 seconds")
        if settings.development and (
            len(settings.mcp_token) < 32 or len(settings.browser_token) < 32
            or settings.mcp_token == settings.browser_token
        ):
            raise ValueError("Development execution requires distinct caller/browser tokens of at least 32 characters")
        return settings


settings = Settings.from_env()
