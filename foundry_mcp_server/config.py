"""Runtime binding and fail-closed settings for the development console."""
import math
import os
import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit
from pydantic import AnyHttpUrl


def https_origin(value, variable, *, issuer=False):
    """Validate canonical origins; issuer spelling includes exactly one slash."""
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == 'https' and parsed.hostname and
                 parsed.username is None and parsed.password is None and
                 parsed.path == ('/' if issuer else '') and
                 not parsed.query and not parsed.fragment and
                 not any(c.isspace() or ord(c) < 32 for c in value) and
                 not any(c in value for c in ('\\', '?', '#', '%')) and
                 (parsed.port is None or 1 <= parsed.port <= 65535))
        if not valid: raise ValueError
        canonical = str(AnyHttpUrl(value))
        if value != (canonical if issuer else canonical.removesuffix('/')):
            raise ValueError
    except ValueError:
        raise ValueError(f'{variable} must be an HTTPS origin' + (' ending in /' if issuer else ' without a path')) from None
    return value


def allowlist(value, variable):
    values = tuple(part.strip() for part in value.split(','))
    if not all(values) or any(any(c.isspace() for c in part) for part in values):
        raise ValueError(f'{variable} requires nonempty comma-separated exact identifiers')
    return values


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
    public_url: str = ''
    oauth_provider: str = ''
    oauth_issuer: str = ''
    oauth_allowed_subjects: tuple[str, ...] = ()
    oauth_allowed_client_ids: tuple[str, ...] = ()

    @property
    def production_auth(self):
        """Browser/PDF production trust; never selects multiple MCP methods."""
        return self.auth_mode in {'basic', 'oauth'}

    @property
    def resource_url(self):
        return self.public_url + '/mcp/mcp'

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
            public_url=os.getenv('FOUNDRY_MCP_PUBLIC_URL', ''),
            oauth_provider=os.getenv('FOUNDRY_MCP_OAUTH_PROVIDER', ''),
            oauth_issuer=os.getenv('FOUNDRY_MCP_OAUTH_ISSUER', ''),
            oauth_allowed_subjects=allowlist(os.environ['FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS'], 'FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS') if os.getenv('FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS') else (),
            oauth_allowed_client_ids=allowlist(os.environ['FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS'], 'FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS') if os.getenv('FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS') else (),
        )
        if not math.isfinite(settings.timeout) or not 0 < settings.timeout <= 120:
            raise ValueError("Execution timeout must be between 0 and 120 seconds")
        if settings.development and (not settings.mcp_token or not settings.browser_token):
            raise ValueError("Development execution requires caller and browser credentials")
        if settings.auth_mode not in {"none", "basic", "oauth"}:
            raise ValueError("FOUNDRY_MCP_AUTH_MODE must be none, basic or oauth")
        oauth_names = {key for key, value in os.environ.items() if value and key.startswith('FOUNDRY_MCP_OAUTH_')}
        known = {'FOUNDRY_MCP_OAUTH_' + suffix for suffix in ('PROVIDER', 'ISSUER', 'ALLOWED_SUBJECTS', 'ALLOWED_CLIENT_IDS')}
        if oauth_names - known:
            raise ValueError('Unknown OAuth settings: ' + ', '.join(sorted(oauth_names - known)))
        if settings.auth_mode != 'oauth' and (oauth_names or settings.public_url):
            raise ValueError('OAuth settings and FOUNDRY_MCP_PUBLIC_URL require FOUNDRY_MCP_AUTH_MODE=oauth')
        if settings.auth_mode == 'oauth':
            if settings.basic_username or settings.basic_password:
                raise ValueError('OAuth conflicts with FOUNDRY_MCP_BASIC_USERNAME and FOUNDRY_MCP_BASIC_PASSWORD')
            if settings.development or not settings.bridge_token:
                raise ValueError('OAuth requires FOUNDRY_MCP_BRIDGE_TOKEN and development execution disabled')
            if settings.oauth_provider != 'auth0':
                raise ValueError('FOUNDRY_MCP_OAUTH_PROVIDER must be auth0')
            if not settings.oauth_allowed_subjects or not settings.oauth_allowed_client_ids:
                raise ValueError('OAuth requires FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS and FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS')
            https_origin(settings.public_url, 'FOUNDRY_MCP_PUBLIC_URL')
            https_origin(settings.oauth_issuer, 'FOUNDRY_MCP_OAUTH_ISSUER', issuer=True)
        if settings.auth_mode == "basic":
            if (settings.development or not settings.basic_username or ":" in settings.basic_username
                or not settings.basic_password or not settings.bridge_token):
                raise ValueError("Production authentication requires a username without colons, password, browser credential, and development execution disabled")
        elif settings.auth_mode == 'none' and any((settings.basic_username, settings.basic_password, settings.bridge_token)):
            raise ValueError("Production credentials require FOUNDRY_MCP_AUTH_MODE=basic")
        return settings


settings = Settings.from_env()
