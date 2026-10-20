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
    auth_mode: str = "none"
    basic_username: str = ""
    basic_password: str = ""
    bridge_token: str = ""
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
            auth_mode=os.getenv("FOUNDRY_MCP_AUTH_MODE", "none"),
            basic_username=os.getenv("FOUNDRY_MCP_BASIC_USERNAME", ""),
            basic_password=os.getenv("FOUNDRY_MCP_BASIC_PASSWORD", ""),
            bridge_token=os.getenv("FOUNDRY_MCP_BRIDGE_TOKEN", ""),
            development=enabled == "true",
            mcp_token=os.getenv("FOUNDRY_MCP_CALLER_TOKEN", ""),
            browser_token=os.getenv("FOUNDRY_MCP_BROWSER_TOKEN", ""),
            timeout=float(os.getenv("FOUNDRY_MCP_EXECUTION_TIMEOUT", "15")),
            trace_path=os.getenv("FOUNDRY_MCP_TRACE_PATH") or None,
        )
        if not math.isfinite(settings.timeout) or not 0 < settings.timeout <= 120:
            raise ValueError("Execution timeout must be between 0 and 120 seconds")
        if settings.development and (not settings.mcp_token or not settings.browser_token):
            raise ValueError("Development execution requires caller and browser credentials")
        if settings.auth_mode not in {"none", "basic"}:
            raise ValueError("FOUNDRY_MCP_AUTH_MODE must be none or basic")
        if settings.auth_mode == "basic":
            if (settings.development or not settings.basic_username or ":" in settings.basic_username
                or not settings.basic_password or not settings.bridge_token):
                raise ValueError("Production authentication requires a username without colons, password, browser credential, and development execution disabled")
        elif any((settings.basic_username, settings.basic_password, settings.bridge_token)):
            raise ValueError("Production credentials require FOUNDRY_MCP_AUTH_MODE=basic")
        return settings


settings = Settings.from_env()
