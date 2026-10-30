"""Local GM policy applied only after RS256 signature/issuer/audience validation."""
import logging
import math

from fastmcp.server.auth import TokenVerifier
from fastmcp.utilities.auth import decode_jwt_header
from joserfc.jwt import JWTClaimsRegistry
from joserfc.errors import JoseError

GM_SCOPE = 'foundry:gm'


class GMTokenVerifier(TokenVerifier):
    """Compose the public JWTVerifier API with RFC9068 and exact local policy.

    Zero clock skew throughout (including FastMCP transport expiry). Permissions
    and scp never substitute for granted scope. Missing scope reaches transport
    as an empty scope list, producing 403 rather than a new login challenge.
    """
    def __init__(self, verifier, subjects, clients):
        super().__init__(required_scopes=[GM_SCOPE])
        self.verifier = verifier
        self.subjects = frozenset(subjects)
        self.clients = frozenset(clients)
        # The upstream verifier logs attacker-controlled claims on rejection.
        # Keep that instance silent, including under DEBUG; never log claims.
        verifier.logger = logging.Logger('foundry_mcp.oauth.verifier', level=logging.CRITICAL + 1)
        verifier.logger.propagate = False

    async def verify_token(self, token):
        try:
            accepted = await self.verifier.verify_token(token)
        except OverflowError:
            # The framework converts exp to int before applying our strict type
            # policy; a nonfinite JSON numeric value must also fail closed.
            return None
        if accepted is None:
            return None
        claims = accepted.claims
        try:
            if decode_jwt_header(token).get('typ') not in {'at+jwt', 'application/at+jwt'}:
                return None
            for name in ('exp', 'iat', 'nbf'):
                value = claims.get(name)
                if name == 'nbf' and name not in claims:
                    continue
                if type(value) not in (int, float) or not math.isfinite(value):
                    return None
            JWTClaimsRegistry(leeway=0, exp={'essential': True}, iat={'essential': True}).validate(claims)
            subject, client = claims.get('sub'), claims.get('client_id')
            if (not isinstance(subject, str) or subject not in self.subjects or
                not isinstance(client, str) or client not in self.clients or
                subject.endswith('@clients') or claims.get('gty') == 'client-credentials' or
                not isinstance(claims.get('jti'), str) or not claims['jti']):
                return None
            scope = claims.get('scope', '')
            if not isinstance(scope, str):
                return None
        except (JoseError, ValueError, TypeError, KeyError):
            return None
        accepted.scopes = scope.split()
        accepted.client_id = client
        accepted.subject = subject
        return accepted
