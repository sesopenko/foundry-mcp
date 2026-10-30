#!/usr/bin/env python3
"""Bounded read-only public OAuth checks; no credentials or tenant mutations.

Usage: .venv/bin/python scripts/oauth-validate.py https://mcp.example.com https://tenant.auth0.com/
Four requests maximum, 64 KiB per response, five-second HTTP timeout and a
25-second total deadline. No redirects, tokens, private settings or bodies print.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx2 as httpx
from foundry_mcp_server.config import https_origin


async def validate(origin, issuer, transport=None):
    https_origin(origin, 'public URL')
    https_origin(issuer, 'issuer', issuer=True)
    resource = origin + '/mcp/mcp'
    metadata_url = origin + '/.well-known/oauth-protected-resource/mcp/mcp'
    errors = []
    async with httpx.AsyncClient(timeout=5, follow_redirects=False, transport=transport) as client:
        async def get(url):
            async with client.stream('GET', url) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 65536: raise ValueError('response size limit')
                return response, bytes(body)
        response, body = await get(metadata_url)
        response.raise_for_status()
        metadata = json.loads(body)
        for field, expected in (('resource', resource), ('authorization_servers', [issuer])):
            if metadata.get(field) != expected: errors.append('resource metadata: ' + field)
        if 'foundry:gm' not in metadata.get('scopes_supported', []): errors.append('resource metadata: scopes_supported')
        response, _ = await get(resource)
        challenge = response.headers.get('www-authenticate', '')
        if response.status_code != 401 or not challenge.startswith('Bearer ') or 'Basic' in challenge:
            errors.append('MCP must reject anonymous requests with only a Bearer challenge')
        if f'resource_metadata="{metadata_url}"' not in challenge: errors.append('Bearer challenge metadata URL')
        for suffix in ('.well-known/openid-configuration', '.well-known/oauth-authorization-server'):
            response, body = await get(issuer + suffix)
            response.raise_for_status()
            metadata = json.loads(body)
            if metadata.get('issuer') != issuer: errors.append(suffix + ': issuer')
            for field, expected in (('code_challenge_methods_supported', 'S256'),
                                    ('token_endpoint_auth_methods_supported', 'client_secret_post'),
                                    ('scopes_supported', 'offline_access')):
                if expected not in metadata.get(field, []): errors.append(suffix + ': ' + field)
            for field, path in (('authorization_endpoint', 'authorize'), ('token_endpoint', 'oauth/token')):
                if metadata.get(field) != issuer + path: errors.append(suffix + ': ' + field)
            if metadata.get('authorization_response_iss_parameter_supported') is not True:
                errors.append(suffix + ': enable issuer identification in authorization responses')
    return {'resource': resource, 'issuer': issuer, 'metadata_url': metadata_url, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('public_url')
    parser.add_argument('issuer')
    args = parser.parse_args()
    try:
        result = asyncio.run(asyncio.wait_for(validate(args.public_url, args.issuer), 25))
    except (ValueError, TypeError, AttributeError, httpx.HTTPError, TimeoutError):
        print('FAIL: invalid configuration, unreachable endpoint or malformed/oversized metadata', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
