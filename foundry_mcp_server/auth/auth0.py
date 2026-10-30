"""Direct Auth0 resource server on FastMCP 4.1.4, never an OAuth proxy.

Upstream contract: https://gofastmcp.com/integrations/auth0
Discovery has a 10-second timeout. JWTVerifier owns its one-hour key cache,
30-second refresh throttle (including failures), and 10-second JWKS timeout.
"""
from urllib.parse import urlsplit

from fastmcp.server.auth.oidc_proxy import OIDCConfiguration
from fastmcp.server.auth.providers.auth0 import Auth0MCPProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from pydantic import AnyHttpUrl

from .policy import GM_SCOPE, GMTokenVerifier


def validate_discovery(metadata, issuer):
    """Fail closed on issuer drift or incompatible manual-client metadata."""
    if str(metadata.issuer) != issuer:
        raise ValueError('Auth0 discovery issuer differs from FOUNDRY_MCP_OAUTH_ISSUER')
    origin = urlsplit(issuer).netloc
    for name in ('jwks_uri', 'authorization_endpoint', 'token_endpoint'):
        url = urlsplit(str(getattr(metadata, name)))
        if (url.scheme != 'https' or url.netloc != origin or url.username or
            url.password or url.query or url.fragment):
            raise ValueError(f'Auth0 discovery {name} must use the configured HTTPS issuer origin')
    for name, required in (
        ('code_challenge_methods_supported', 'S256'),
        ('token_endpoint_auth_methods_supported', 'client_secret_post'),
        ('response_types_supported', 'code'),
        ('scopes_supported', 'offline_access'),
    ):
        if required not in (getattr(metadata, name) or []):
            raise ValueError(f'Auth0 discovery {name} must advertise {required}')


class DirectAuth0Provider(Auth0MCPProvider):
    """Use provider-generated resource metadata; Auth0 serves AS discovery."""
    def get_routes(self, mcp_path=None):
        return [route for route in super().get_routes(mcp_path)
                if route.path != '/.well-known/oauth-authorization-server']


def create_auth0(settings):
    config_url = settings.oauth_issuer + '.well-known/openid-configuration'
    metadata = OIDCConfiguration.get_oidc_configuration(
        AnyHttpUrl(config_url), strict=None, timeout_seconds=10)
    validate_discovery(metadata, settings.oauth_issuer)
    verifier = GMTokenVerifier(JWTVerifier(
        jwks_uri=str(metadata.jwks_uri), issuer=settings.oauth_issuer,
        audience=settings.resource_url, algorithm='RS256', required_scopes=[]),
        settings.oauth_allowed_subjects, settings.oauth_allowed_client_ids)
    provider = DirectAuth0Provider(
        config_url=config_url, base_url=settings.public_url,
        token_verifier=verifier, required_scopes=[GM_SCOPE],
        scopes_supported=[GM_SCOPE], resource_name='Foundry GM bridge', timeout_seconds=10)
    # Explicitly retain exact configured issuer (upstream strips its slash).
    provider.authorization_servers = [AnyHttpUrl(settings.oauth_issuer)]
    return provider
