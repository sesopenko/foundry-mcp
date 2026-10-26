"""Read-only four-call check that deferred PF2e afflictions are not selectable.

No Foundry document is loaded, read, created or changed. Invalid filter calls
use nonexistent placeholder selectors and must reject at the server boundary.
"""
import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180


def has_affliction_selector(schema):
    """Inspect every nested enum/const, including unions and shared definitions."""
    if isinstance(schema, dict):
        if schema.get('const') == 'affliction' or 'affliction' in schema.get('enum', []):
            return True
        return any(has_affliction_selector(value) for value in schema.values())
    return isinstance(schema, list) and any(has_affliction_selector(value) for value in schema)


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


def invalid_filter_response(response):
    """Accept only input/schema rejection, never missing documents or bridge errors."""
    if not response.is_error:
        return False
    for block in response.content:
        text = getattr(block, 'text', '')
        try:
            value = json.loads(text)
        except (TypeError, ValueError):
            value = None
        if isinstance(value, dict) and value.get('code') == 'InvalidRequest':
            return True
        lower = text.lower()
        if 'affliction' in lower and any(term in lower for term in ('input validation', 'validation error', 'literal_error')):
            return True
    return False


async def verify(client, report=None):
    """PF2e-specific deferred-type interface proof, at most four MCP calls."""
    requested, completed, stage = 0, 0, 'discovery'
    result = report if report is not None else {}
    result.update(passed=False)

    def counts():
        result.update(mcp_calls=completed, requested_calls=requested, completed_calls=completed)

    async def call(name, arguments, **kwargs):
        nonlocal requested, completed
        requested += 1
        counts()
        response = await client.call_tool(name, arguments, **kwargs)
        completed += 1
        counts()
        return response

    try:
        requested += 1
        counts()
        tools = await client.list_tools()
        completed += 1
        counts()
        assert tools and not any(has_affliction_selector(tool.inputSchema) for tool in tools)
        assert not any('affliction' in tool.name.lower() for tool in tools)
        descriptions = {tool.name: tool.description.lower() for tool in tools}
        requirements = {
            'get_actor_types': ('no dedicated affliction reader', 'in_scope false'),
            'read_actor': ('affliction_reading_unsupported', 'dedicated affliction items have no reader'),
            'read_item': ('affliction', 'deferred outside current delivery scope'),
            'list_actor_items': ('dedicated affliction items have no reader', 'cannot be selected in types'),
            'search_compendium_actors': ('dedicated affliction items have no reader', 'excluded from filters'),
        }
        for name, phrases in requirements.items():
            assert all(phrase in descriptions[name] for phrase in phrases)
        stage = 'registry'
        registry = payload(await call('get_actor_types', {}))
        entries = [row for row in registry['item_types'] if row['type'] == 'affliction']
        assert len(entries) == 1
        row = entries[0]
        assert all(row[flag] is False for flag in ('in_scope', 'source_supported', 'mapped_supported', 'effective_supported'))
        limitations = ' '.join(row['limitations']).lower()
        assert 'deferred' in limitations and ('upstream' in limitations or 'production' in limitations or '8.6.1' in limitations)
        stage = 'owned_item_filter_rejection'
        owned = await call('list_actor_items', dict(actor_uuid='Actor.MCPNoSuchActor00', types=['affliction']), raise_on_error=False)
        assert invalid_filter_response(owned)
        stage = 'pack_item_filter_rejection'
        pack = await call('search_compendium_actors', dict(pack_ids=['mcp.no-such-pack'], query='interface check',
                                                         document_type='Item', types=['affliction']), raise_on_error=False)
        assert invalid_filter_response(pack)
        result.update(passed=True, tools_checked=len(tools), schemas_exclude_deferred_type=True,
                      registry_deferred=True, invalid_filters_rejected=2, documents_read=0)
    except Exception as error:
        result.update(failure_stage=stage, exception_type=type(error).__name__)
    result.update(mcp_calls=completed, requested_calls=requested, completed_calls=completed)
    return result


async def main():
    result = dict(passed=False)
    try:
        token = next(line.partition('=')[2].strip() for line in (Path(__file__).resolve().parents[1] / '.env.mcp').read_text().splitlines()
                     if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
        if not token:
            raise RuntimeError('Missing local caller credential')
        transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
        async with Client(transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                await verify(client, result)
    except Exception as error:
        result.update(passed=False, exception_type=type(error).__name__)
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
