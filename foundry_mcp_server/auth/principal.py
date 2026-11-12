"""Trusted per-request identities for private image snapshots.

FastMCP4.1.4 public get_http_request/get_access_token APIs, checked against pinned
source and https://gofastmcp.com/docs/servers/authorization on2026-11-11.
No raw credentials, request headers or session IDs become identity keys.
"""
from dataclasses import dataclass
import time

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token, get_http_request

from foundry_mcp_server.config import settings
from .policy import GM_SCOPE

_PROOF = object()
_SCOPE_KEY = 'foundry_mcp.validated_image_principal'


@dataclass(frozen=True)
class Principal:
    mode: str
    issuer: str
    subject: str
    client_id: str


def denied():
    return ToolError('AuthenticatedContextRequired: use this authenticated HTTP MCP endpoint as an authorized GM; reconnect and retry. In-memory/anonymous invocation cannot stage or use image snapshots.')


def stamp_principal(scope, config):
    """Called only AFTER existing Basic/development credential verification.

    The proof lives in server-created ASGI scope, never an inbound header.
    OAuth is supplied by FastMCP's verified token context instead.
    """
    scope = dict(scope)
    scope.pop(_SCOPE_KEY, None)
    if config.auth_mode == 'basic':
        scope[_SCOPE_KEY] = (_PROOF, Principal('basic', '', config.basic_username, 'configured-account'))
    elif config.development:
        scope[_SCOPE_KEY] = (_PROOF, Principal('development', '', 'configured-caller', 'local-development'))
    return scope


def current_principal(config=None):
    """Return verified stable identity, failing closed without a live HTTP call.

    OAuth issuer/sub/client identify a principal across access-token refreshes.
    Authentication/signature remains owned by the configured provider; repeat
    exact policy/expiry checks here before snapshot use after long async work.
    """
    config = config or settings
    try:
        request = get_http_request()
    except RuntimeError:
        raise denied() from None
    if config.auth_mode == 'oauth':
        token = get_access_token()
        if token is None:
            raise denied()
        claims = token.claims
        issuer, subject, client = claims.get('iss'), claims.get('sub'), claims.get('client_id')
        expiry = claims.get('exp')
        if (issuer != config.oauth_issuer or subject not in config.oauth_allowed_subjects or client not in config.oauth_allowed_client_ids
                or token.client_id != client or token.subject != subject or GM_SCOPE not in token.scopes
                or type(expiry) not in (int,float) or not time.time() < expiry):
            raise denied()
        return Principal('oauth', issuer, subject, client)
    marker = request.scope.get(_SCOPE_KEY)
    if (not isinstance(marker, tuple) or len(marker) != 2 or marker[0] is not _PROOF or not isinstance(marker[1], Principal)):
        raise denied()
    principal = marker[1]
    if config.auth_mode == 'basic' and principal == Principal('basic', '', config.basic_username, 'configured-account'):
        return principal
    if config.development and principal == Principal('development', '', 'configured-caller', 'local-development'):
        return principal
    raise denied()
