"""Construct exactly one selected OAuth stack; no discovery in other modes."""


def create_auth(settings):
    if settings.auth_mode != 'oauth':
        return None
    from .auth0 import create_auth0
    return create_auth0(settings)
