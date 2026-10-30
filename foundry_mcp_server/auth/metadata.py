"""Discovery hints for OAuth clients; transport policy remains authoritative."""
from fastmcp.server.middleware import Middleware
from .policy import GM_SCOPE


class OAuthToolMetadata(Middleware):
    """Publish OpenAI's documented _meta compatibility field.

    FastMCP4/MCP2 protocol models omit unknown top-level fields. Use supported
    metadata rather than patching framework serializers. ChatGPT acceptance
    of this compatibility field remains part of the live connection gate.
    https://developers.openai.com/plugins/reference
    """
    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        return [tool.model_copy(update={'meta': {
            **(tool.meta or {}),
            'securitySchemes': [{'type': 'oauth2', 'scopes': [GM_SCOPE]}],
        }}) for tool in tools]
