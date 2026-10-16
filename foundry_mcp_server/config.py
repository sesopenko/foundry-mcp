"""Runtime binding and fail-closed settings for the development console."""
import math
import os
import ipaddress
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    development: bool = False
    mcp_token: str = ""
    browser_token: str = ""
    timeout: float = 15.0
    max_code_bytes: int = 32768
    max_response_bytes: int = 65536
    trace_path: str | None = None

    @classmethod
    def from_env(cls):
        host = os.getenv("FOUNDRY_MCP_HOST", "127.0.0.1").strip()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r"(?=.{1,253}\Z)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.?", host):
                raise ValueError("FOUNDRY_MCP_HOST must be a bind hostname or IP address, without scheme or port") from None
        try:
            port = int(os.getenv("FOUNDRY_MCP_PORT", "8000"))
        except ValueError as exc:
            raise ValueError("FOUNDRY_MCP_PORT must be an integer between 1 and 65535") from exc
        if not 1 <= port <= 65535:
            raise ValueError("FOUNDRY_MCP_PORT must be between 1 and 65535")
        enabled = os.getenv("FOUNDRY_MCP_DEV_EXECUTION", "false")
        if enabled not in {"true", "false"}:
            raise ValueError("FOUNDRY_MCP_DEV_EXECUTION must be true or false")
        settings = cls(
            host=host,
            port=port,
            development=enabled == "true",
            mcp_token=os.getenv("FOUNDRY_MCP_CALLER_TOKEN", ""),
            browser_token=os.getenv("FOUNDRY_MCP_BROWSER_TOKEN", ""),
            timeout=float(os.getenv("FOUNDRY_MCP_EXECUTION_TIMEOUT", "15")),
            trace_path=os.getenv("FOUNDRY_MCP_TRACE_PATH") or None,
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
